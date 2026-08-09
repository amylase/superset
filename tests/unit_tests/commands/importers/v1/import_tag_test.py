# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Tests for ``superset.commands.importers.v1.utils.import_tag``.

The conflict these tests exercise happens when a competing import commits the
same ``tagged_object`` row between this import's existence check and its own
INSERT. SQLite allows a single writer, so the losing writer is rejected with a
lock error rather than a unique violation and a genuinely concurrent
reproduction needs PostgreSQL. Instead, the row that loses the race is written
on the import's own connection just before the flush, which raises the same
``IntegrityError`` from the same ``uix_tagged_object`` constraint at the same
point in ``import_tag``. That proves the recovery behaviour (the session stays
usable, the remaining tags are still imported and previously staged work
survives); it does not prove anything about database-level isolation or
locking under real concurrency.
"""

from typing import Any, Callable, Iterator

import pytest
from pytest_mock import MockerFixture
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from superset.tags.models import ObjectType, Tag, TaggedObject

OBJECT_ID = 1
OBJECT_TYPE = "chart"


@pytest.fixture
def engine() -> Engine:
    engine = create_engine("sqlite://", future=True)
    Tag.metadata.create_all(
        engine, tables=[Tag.__table__, TaggedObject.__table__], checkfirst=True
    )
    return engine


@pytest.fixture
def db_session(engine: Engine, mocker: MockerFixture) -> Iterator[Session]:
    session = sessionmaker(bind=engine, future=True)()
    mocker.patch("superset.db.session", session)
    mocker.patch(
        "superset.commands.importers.v1.utils.feature_flag_manager.is_feature_enabled",
        return_value=True,
    )
    yield session
    session.close()


@pytest.fixture
def losing_race_for_tag() -> Callable[[Session, str], None]:
    """Write the association behind the ORM's back, so its INSERT conflicts.

    The row is inserted right before the flush that writes the import's own
    association, emulating a competing import that committed first.
    """

    def register(session: Session, tag_name: str) -> None:
        state = {"fired": False}

        @event.listens_for(session, "before_flush")
        def before_flush(
            session: Session, _flush_context: Any, _instances: Any
        ) -> None:
            if state["fired"] or not any(
                isinstance(obj, TaggedObject) for obj in session.new
            ):
                return
            state["fired"] = True

            connection = session.connection()
            tag_id = connection.execute(
                select(Tag.id).where(Tag.name == tag_name)
            ).scalar()
            connection.execute(
                TaggedObject.__table__.insert().values(
                    tag_id=tag_id,
                    object_id=OBJECT_ID,
                    object_type=ObjectType.chart,
                )
            )

    return register


def test_import_tag_survives_conflicting_association(
    db_session: Session,
    losing_race_for_tag: Callable[[Session, str], None],
) -> None:
    """A conflict on one tag must not poison the session or abort the import."""
    from superset.commands.importers.v1.utils import import_tag

    db_session.add_all(
        [
            Tag(name="tag1", type="custom"),
            Tag(name="tag2", type="custom"),
        ]
    )
    db_session.commit()

    # unrelated work staged in the same import, before the conflict
    db_session.add(Tag(name="staged", type="custom"))

    losing_race_for_tag(db_session, "tag1")

    tag_ids = import_tag(["tag1", "tag2"], {}, OBJECT_ID, OBJECT_TYPE, db_session)

    expected_ids = {
        tag_id
        for (tag_id,) in db_session.query(Tag.id).filter(Tag.name.in_(["tag1", "tag2"]))
    }
    # the conflicting tag is still reported, so it is not pruned as stale
    assert set(tag_ids) == expected_ids

    # the association exists exactly once for each tag
    associations = (
        db_session.query(TaggedObject)
        .filter_by(object_id=OBJECT_ID, object_type=OBJECT_TYPE)
        .all()
    )
    assert sorted(assoc.tag_id for assoc in associations) == sorted(expected_ids)

    # unrelated work staged before the conflict was not discarded
    assert db_session.query(Tag).filter_by(name="staged").one_or_none() is not None


def test_import_tag_creates_tags_and_removes_stale_associations(
    db_session: Session,
) -> None:
    """The happy path still creates missing tags and prunes stale associations."""
    from superset.commands.importers.v1.utils import import_tag

    stale_tag = Tag(name="stale", type="custom")
    db_session.add(stale_tag)
    db_session.flush()
    db_session.add(
        TaggedObject(
            tag_id=stale_tag.id, object_id=OBJECT_ID, object_type=ObjectType.chart
        )
    )
    db_session.commit()

    tag_ids = import_tag(["fresh"], {}, OBJECT_ID, OBJECT_TYPE, db_session)

    fresh_tag = db_session.query(Tag).filter_by(name="fresh").one()
    assert tag_ids == [fresh_tag.id]

    associations = (
        db_session.query(TaggedObject)
        .filter_by(object_id=OBJECT_ID, object_type=OBJECT_TYPE)
        .all()
    )
    assert [assoc.tag_id for assoc in associations] == [fresh_tag.id]

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

import logging
from typing import Any

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from superset.common.query_object import QueryObject
from superset.exceptions import InvalidPostProcessingError
from superset.utils.pandas_postprocessing import pivot
from superset.utils.pandas_postprocessing.utils import drop_unsupported_options


@pytest.fixture
def df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "country": ["UK", "UK", "US", "US"],
            "gender": ["boy", "girl", "boy", "girl"],
            "num": [1, 2, 3, 4],
        }
    )


def _query_object(post_processing: list[dict[str, Any] | None]) -> QueryObject:
    return QueryObject(post_processing=post_processing)


def test_exec_post_processing_drops_removed_options(
    df: pd.DataFrame, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Options removed from an operation in a later version of Superset, but still
    present in a stored `query_context`, are ignored instead of raising a
    `TypeError`.
    """
    query_object = _query_object(
        [
            {
                "operation": "pivot",
                "options": {
                    "index": ["country"],
                    "columns": ["gender"],
                    "aggregates": {"num": {"operator": "sum"}},
                    # removed when flattening became its own operation
                    "flatten_columns": True,
                    "reset_index": True,
                },
            }
        ]
    )

    with caplog.at_level(logging.WARNING):
        result = query_object.exec_post_processing(df)

    expected = pivot(
        df,
        index=["country"],
        columns=["gender"],
        aggregates={"num": {"operator": "sum"}},
    )

    assert_frame_equal(result, expected)
    assert "flatten_columns, reset_index" in caplog.text


def test_exec_post_processing_keeps_supported_options(df: pd.DataFrame) -> None:
    """
    Valid, current options are unaffected.
    """
    options = {
        "index": ["country"],
        "columns": ["gender"],
        "aggregates": {"num": {"operator": "sum"}},
    }
    with_stale = _query_object(
        [{"operation": "pivot", "options": {**options, "flatten_columns": True}}]
    ).exec_post_processing(df)
    without_stale = _query_object(
        [{"operation": "pivot", "options": options}]
    ).exec_post_processing(df)

    assert_frame_equal(with_stale, without_stale)


def test_exec_post_processing_still_validates_options(df: pd.DataFrame) -> None:
    """
    Dropping unknown options doesn't mask validation of the supported ones.
    """
    query_object = _query_object(
        [
            {
                "operation": "pivot",
                "options": {
                    "index": ["invalid_column"],
                    "aggregates": {"num": {"operator": "sum"}},
                    "flatten_columns": True,
                },
            }
        ]
    )
    with pytest.raises(InvalidPostProcessingError):
        query_object.exec_post_processing(df)


def test_drop_unsupported_options() -> None:
    def operation(df: pd.DataFrame, foo: int, bar: int = 1) -> pd.DataFrame:
        return df

    assert drop_unsupported_options(operation, {"foo": 1, "bar": 2}) == (
        {"foo": 1, "bar": 2},
        [],
    )
    assert drop_unsupported_options(operation, {"foo": 1, "baz": 2}) == (
        {"foo": 1},
        ["baz"],
    )
    # the DataFrame is passed positionally, so it can never be an option
    assert drop_unsupported_options(operation, {"df": 1}) == ({}, ["df"])


def test_drop_unsupported_options_with_kwargs() -> None:
    def operation(df: pd.DataFrame, **kwargs: int) -> pd.DataFrame:
        return df

    assert drop_unsupported_options(operation, {"anything": 1}) == ({"anything": 1}, [])

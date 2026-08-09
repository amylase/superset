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
import inspect

import pytest
from pandas import DataFrame

from superset.exceptions import InvalidPostProcessingError
from superset.utils.pandas_postprocessing import (
    aggregate,
    compare,
    contribution,
    cum,
    diff,
    escape_separator,
    pivot,
    rename,
    rolling,
    select,
    sort,
    unescape_separator,
)
from superset.utils.pandas_postprocessing.utils import validate_column_args


def test_escape_separator():
    assert escape_separator(r" hell \world ") == r" hell \world "
    assert unescape_separator(r" hell \world ") == r" hell \world "

    escape_string = escape_separator("hello, world")
    assert escape_string == r"hello\, world"
    assert unescape_separator(escape_string) == "hello, world"

    escape_string = escape_separator("hello,world")
    assert escape_string == r"hello\,world"
    assert unescape_separator(escape_string) == "hello,world"


def test_validate_column_args_preserves_function_identity():
    @validate_column_args("columns")
    def dummy(df: DataFrame, columns: list[str]) -> DataFrame:
        """Dummy docstring."""
        return df

    assert dummy.__name__ == "dummy"
    assert dummy.__doc__ == "Dummy docstring."
    assert list(inspect.signature(dummy).parameters) == ["df", "columns"]


@pytest.mark.parametrize(
    "func,name",
    [
        (aggregate, "aggregate"),
        (compare, "compare"),
        (contribution, "contribution"),
        (cum, "cum"),
        (diff, "diff"),
        (pivot, "pivot"),
        (rename, "rename"),
        (rolling, "rolling"),
        (select, "select"),
        (sort, "sort"),
    ],
)
def test_decorated_postprocessing_functions_keep_identity(func, name):
    assert func.__name__ == name
    assert func.__doc__ is not None
    assert "df" in inspect.signature(func).parameters
    assert "options" not in inspect.signature(func).parameters


def test_validate_column_args_still_validates():
    @validate_column_args("columns")
    def dummy(df: DataFrame, columns: list[str]) -> DataFrame:
        """Dummy docstring."""
        return df

    df = DataFrame({"a": [1, 2]})
    assert dummy(df, columns=["a"]) is df
    with pytest.raises(InvalidPostProcessingError):
        dummy(df, columns=["b"])

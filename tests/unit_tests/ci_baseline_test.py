# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Baseline probe for this fork's CI.

This fork is used for an autonomous remediation experiment. Remediation pull
requests are opened by Devin sessions and must be judged on Superset's own CI.
Some jobs in that CI depend on secrets a fork does not have (coverage upload,
image push), so a red check does not necessarily mean the code is wrong.

This file exists only so that a pull request touching Python triggers the same
job set a remediation PR will, establishing which checks are green on a fork
before any remediation lands. It asserts nothing about Superset.
"""


def test_ci_baseline() -> None:
    assert True

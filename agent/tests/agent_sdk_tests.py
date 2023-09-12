# vim:fenc=utf-8
#
# Copyright (C) 2023 dbpunk.com Author imotai <codego.me@gmail.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

""" """

import os
import pytest
import asyncio
import logging
from octopus_agent.agent_sdk import AgentSDK

logger = logging.getLogger(__name__)
api_base = "127.0.0.1:9528"
api_key = "ZCeI9cYtOCyLISoi488BgZHeBkHWuFUH"


@pytest.fixture
def agent_sdk():
    sdk = AgentSDK(api_base, api_key)
    sdk.connect()
    yield sdk
    sdk.close()


@pytest.mark.asyncio
async def test_upload_smoke_test(agent_sdk):
    sdk = agent_sdk
    await sdk.add_kernel(api_key, "127.0.0.1:9527")
    path = os.path.abspath(__file__)
    await sdk.upload_file(path, "agent_sdk_tests.py")
    try:
        responds = []
        async for respond in sdk.prompt("write a hello world in python"):
            responds.append(respond)
        assert len(responds) > 0, "no responds for the prompt"
    except Exception as ex:
        assert 0, str(ex)
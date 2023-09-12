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

import discord
import asyncio
import logging
import json
import sys
import os
import click
from dotenv import dotenv_values
from octopus_proto import common_pb2
from octopus_agent.agent_sdk import AgentSDK

LOG_LEVEL = logging.INFO
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class OctopusDiscordBot(discord.Client):

    def __init__(self, octopus_sdk, filedir, **kwargs):
        discord.Client.__init__(self, **kwargs)
        self.octopus_sdk = octopus_sdk
        self.filedir = filedir

    def handle_action_start(self, respond):
        """Run on agent action."""
        segments = []
        if not respond.on_agent_action:
            return segments
        action = respond.on_agent_action
        if not action.input:
            return segments
        logger.info("handle action start return")
        arguments = json.loads(action.input)
        if action.tool == "execute_python_code" and action.input:
            explanation = arguments["explanation"]
            code = arguments["code"]
            mk = f"""{explanation}\n
```python
{code}
```"""
            segments.append(mk)
        elif action.tool == "execute_ts_code" and action.input:
            explanation = arguments["explanation"]
            code = arguments["code"]
            mk = f"""{explanation}\n
```typescript
{code}
```"""
            segments.append(mk)
        elif action.tool == "execute_shell_code" and action.input:
            explanation = arguments["explanation"]
            code = arguments["code"]
            mk = f"""{explanation}\n
```shell
{code}
```"""
            segments.append(mk)
        elif action.tool == "print_code" and action.input:
            explanation = arguments["explanation"]
            code = arguments["code"]
            language = arguments["language"]
            mk = f"""{explanation}\n
```shell
{code}
```"""
            segments.append(mk)
        elif action.tool == "print_final_answer" and action.input:
            mk = """%s""" % (arguments["answer"])
            segments.append(mk)
        return segments

    def handle_final_answer(self, respond):
        segments = []
        if not respond.final_respond:
            return segments
        answer = respond.final_respond.answer
        if not answer:
            return segments
        state = "token:%s iteration:%s model:%s" % (
            respond.token_usage,
            respond.iteration,
            respond.model_name,
        )
        segments.append("%s\n%s" % (answer, state))
        return segments

    def handle_action_output(self, respond, saved_images, output_images):
        segments = []
        if not respond.on_agent_action_end:
            return segments
        mk = respond.on_agent_action_end.output
        if not mk:
            return segments
        output_images.extend(respond.on_agent_action_end.output_files)
        segments.append(mk)
        return segments

    async def download_files(self, images):
        for image in images:
            await self.octopus_sdk.download_file(image, self.filedir)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message):
        # we do not want the bot to reply to itself
        try:
            if message.author.id == self.user.id:
                return
            await message.channel.send("working...")
            files = []
            for att in message.attachments:

                async def generate_chunk(att):
                    # TODO split
                    chunk = await att.read()
                    yield common_pb2.FileChunk(buffer=chunk, filename=att.filename)

                await sdk.upload_binary(generate_chunk(att), att.filename)
                files.append("uploaded " + att.filename)
            if files:
                prompt = message.content + "\n" + "\n".join(files)
            else:
                prompt = message.content
            try:
                async for respond in self.octopus_sdk.prompt(prompt):
                    if not respond:
                        break
                    logger.info(f"{respond}")
                    if respond.on_agent_action_end:
                        saved_images = []
                        output_images = []
                        segments = self.handle_action_output(
                            respond, saved_images, output_images
                        )
                        msg = "".join(segments)
                        logger.info(f"action output {msg}")
                        if msg:
                            if output_images:
                                await self.download_files(output_images)
                                for filename in output_images:
                                    fullpath = "%s/%s" % (self.filedir, filename)
                                    await message.channel.send(
                                        msg, file=discord.File(fullpath)
                                    )
                                    break
                            else:
                                await message.channel.send(msg)
                    if respond.on_agent_action:
                        segments = self.handle_action_start(respond)
                        msg = "".join(segments)
                        logger.info(f"action start {msg}")
                        if msg:
                            await message.channel.send(msg)
                    if respond.final_respond:
                        segments = self.handle_final_answer(respond)
                        msg = "".join(segments)
                        logger.info(f"final answer {msg}")
                        if msg:
                            await message.channel.send(msg)
            except Exception as ex:
                logger.error(f"fail to get file {ex}")
                await message.channel.send("I am sorry for the internal error")
        except Exception as ex:
            logging.error(f"fail to process message {ex}")


async def app():
    octopus_discord_bot_dir = "~/.octopus_discord_bot"
    if octopus_discord_bot_dir.find("~") == 0:
        real_octopus_dir = octopus_discord_bot_dir.replace("~", os.path.expanduser("~"))
    else:
        real_octopus_dir = octopus_discord_bot_dir
    if not os.path.exists(real_octopus_dir):
        os.mkdir(real_octopus_dir)
    octopus_config = dotenv_values(real_octopus_dir + "/config")
    filedir = real_octopus_dir + "/data"
    if not os.path.exists(filedir):
        os.mkdir(filedir)
    sdk = AgentSDK(octopus_config["endpoint"], octopus_config["api_key"])
    sdk.connect()
    intents = discord.Intents.default()
    intents.message_content = True
    client = OctopusDiscordBot(sdk, filedir, intents=intents)
    await client.start(octopus_config["discord_bot_token"])


def run_app():
    asyncio.run(app())
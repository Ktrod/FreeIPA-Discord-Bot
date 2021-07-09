import os
import re
import sys
import typing
import asyncio
import signal
import logging


from core.config import ConfigManager

import discord

from aiohttp import ClientSession

from discord.ext import commands, tasks
from discord import Member, Intents

from dotenv import load_dotenv



logging.basicConfig(level=logging.INFO)

#email_re = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

class LdapBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="^", intents=intents)

        self._connected = asyncio.Event()


        self._session = None

        self.config = ConfigManager(self)
        self.config.populate_cache()

        self._startup()

    def _startup(self):
        self.load_extension("cogs.ldap")


    async def on_ready(self):
        await self.wait_for_connected()

    @property
    def guild(self) -> typing.Optional[discord.Guild]:
        return discord.utils.get(self.guilds, id=self.config["discord_guild"])

    @property
    def token(self) -> str:
        token = self.config["discord_token"]

        return token
    
    @property
    def session(self) -> ClientSession:
        if self._session is None:
            self._session = ClientSession(loop=self.loop)
        return self._session


    
    async def wait_for_connected(self) -> None:
        await self.wait_until_ready()
        await self._connected.wait()
        await self.config.wait_until_ready()
    
    def run(self):
        loop = self.loop

        try:
            loop.add_signal_handler(signal.SIGINT, lambda: loop.stop())
            loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
        except NotImplementedError:
            pass
        
        async def runner():
            try:
                retry_intents = False
                try:
                    await self.start(self.token)
                except discord.PrivilegedIntentsRequired:
                    retry_intents = True
                if retry_intents:
                    await self.http.close()

                    if self.ws is not None and self.ws.open:
                        await self.ws.close(code=1000)
                    
                    self._ready.clear()
                    intents = discord.Intents.default()
                    intents.members = True

                    self._connection._intents = intents

                    await self.start(self.token)
            except discord.PrivilegedIntentsRequired:
                print("Privleged intents need to be enabled in discord bot dash")
            finally:
                if not self.is_closed():
                    await self.close()
                if self._session:
                    await self._session.close()
        def stop_loop_on_completion(f):
            loop.stop()
        
        def _cancel_tasks():
            if sys.version_info < (3, 8):
                task_retriever = asyncio.Task.all_tasks
            else:
                task_retriever = asyncio.all_tasks

            tasks = {t for t in task_retriever(loop=loop) if not t.done()}

            if not tasks:
                return
            
            for task in tasks:
                task.cancel()

            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))

            for task in tasks:
                if task.cancelled():
                    continue
                if task.exception() is not None:
                    loop.call_exception_handler(
                        {
                            "message": "Unhandled exception during Client.run shutdown.",
                            "exception": task.exception(),
                            "task": task,
                        }
                    )
        future = asyncio.ensure_future(runner(), loop=loop)
        future.add_done_callback(stop_loop_on_completion)
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            future.remove_done_callback(stop_loop_on_completion)
            

            try:
                _cancel_tasks()
                if sys.version_info >= (3, 6):
                    loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                
                loop.close()

        if not future.cancelled():
            try:
                return future.result()
            except KeyboardInterrupt:
                # I am unsure why this gets raised here but suppress it anyway
                return None
        
def main():
    my_bot = LdapBot()
    my_bot.run()

if __name__ == "__main__":
    main()
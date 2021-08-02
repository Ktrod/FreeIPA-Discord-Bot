import os
import typing

from copy import deepcopy

from dotenv import load_dotenv

load_dotenv()

class ConfigManager:
    public = {
        "verified_role": None,
        "unverified_role": None,
        "auth_channel": None,
        "verification_channel": None,
    }
    private = {
        "discord_token": None,
        "discord_guild": None,
        "ldap_url": None,
        "ldap_user": None,
        "ldap_pw": None,
        "owners": None,
    }

    all_keys = {**public, **private}

    def __init__(self, bot):
        self.bot = bot
        self._cache = {}

    def __repr__(self):
        return repr(self._cache)

    def __getitem__(self, key: str) -> typing.Any:
        return self._cache[key]

    def populate_cache(self) -> dict:
        data = deepcopy(self.all_keys)

        data.update({i.lower(): k for i, k in os.environ.items() if i.lower() in self.all_keys})

        self._cache = data

        return self._cache

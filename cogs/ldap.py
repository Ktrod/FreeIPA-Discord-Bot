import logging
import sys

import discord
from discord.ext import commands
from python_freeipa.exceptions import DuplicateEntry, Unauthorized

from core.config import ConfigManager

from python_freeipa import ClientMeta

logging.basicConfig(level=logging.INFO)


class LDAP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.config = ConfigManager(self)
        self.config.populate_cache()

        self.ldap = ClientMeta(self.config['ldap_url'], verify_ssl=False)

        self._startup()

    def _startup(self):
        try:
            self.ldap.login(self.config['ldap_user'], self.config['ldap_pw'])
        except Unauthorized:
            logging.log(3, 'Failed to login to LDAP. Check credentials')
            sys.exit(0)

    @commands.Cog.listener()
    async def on_ready(self):
        print('LDAP Cog is ready')

    @commands.command(name='ping')
    async def pong(self, ctx):
        await ctx.send('pong')

    @commands.command()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.error.CheckFailure):
            await ctx.send('You do not have the correct role for this command')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        print(f'{member} joined')
        guild = member.guild

        await member.send(f'{member}, please send a \U0001f44d to the bot in the verify channel to request access')
        await member.add_roles(discord.utils.get(
            guild.roles, id=int(self.config['unverified_role'])), reason=None, atomic=True)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        channel = await self.bot.fetch_channel(payload.channel_id)
        user = await self.bot.fetch_user(payload.user_id)

        guild = self.bot.guilds[0]

        print(self.bot.user)
        print(str(user))
        if channel.id == int(self.config['auth_channel']) and user != self.bot.user:
            message = await channel.fetch_message(payload.message_id)
            emoji = payload.emoji.name

            embed_author = message.embeds[0].author

            embed_fields = []

            for fields in message.embeds[0].fields:
                embed_fields.append(fields)

            if message.embeds[0].title == 'AUTH REQUEST':
                if emoji == '\U0001f44d':
                    accepted_member = guild.get_member_named(embed_author.name)

                    await accepted_member.add_roles(discord.utils.get(
                        guild.roles, id=int(self.config["verified_role"])), reason=None, atomic=True)

                    await accepted_member.remove_roles(discord.utils.get(
                        guild.roles, id=int(self.config["unverified_role"])), reason=None, atomic=True)

                    logging.log(3, f'{user} accepted {message.embeds[0].author.name} into the Discord')

                    await message.delete()
            elif message.embeds[0].title == 'LDAP REQUEST':
                if emoji == '\U0001f44d':
                    first_last = str(embed_fields[1].value[0]) + str(embed_fields[2].value)

                    self.add_user(user=f'{first_last}', first_name=str(
                        embed_fields[1].value), last_name=str(embed_fields[2].value), email=str(embed_fields[0].value))

                    logging.log(3, f'{user} accepted {message.embeds[0].author.name} into the LDAP')

                    await message.delete()
                elif emoji == '\U0001f44e':
                    logging.log(3, f'{user} rejected {message.embeds[0].author.name}')
        if channel.id == int(self.config['verification_channel']) and user != self.bot.user:
            print("here")
            message = await channel.fetch_message(payload.message_id)
            emoji = payload.emoji.name

            if emoji == '\U0001f44d':
                print(self.bot.guilds)
                awaiting_verification_channel = discord.utils.get(guild.channels, id=int(self.config["auth_channel"]))

                auth_req_embed = discord.Embed(title='AUTH REQUEST')
                auth_req_embed.set_author(name=user, icon_url=user.avatar_url)
                auth_req_embed.add_field(name='Instructions', value=f'\U0001f44d to add {user} to group', inline=False)

                sent_embed = await awaiting_verification_channel.send(embed=auth_req_embed)

                await sent_embed.add_reaction(emoji)

    @commands.command(name='add_user')
    @commands.has_role('admins')
    async def add_user_command(self, ctx, user: str, first_name: str, last_name: str, email: str, **kwargs):

        if user not in self.ldap.user_find(o_uid=user):
            new_user = self.add_user(
                a_uid=user, o_sn=last_name, o_givenname=first_name, o_cn=f'{first_name}  {last_name}', o_random=True)
            
            print(new_user)
        else:
            await ctx.send('User already exists')

    def add_user(self, user: str, first_name: str, last_name: str, email: str, **kwargs):
        if user not in self.ldap.user_find(o_uid=user):
            try:
                new_user = self.ldap.user_add(a_uid=user,
                                              o_sn=last_name,
                                              o_givenname=first_name,
                                              o_cn=f'{first_name}  {last_name}',
                                              o_mail=email,
                                              o_random=True)
                print(new_user)
            except DuplicateEntry:
                print(f'{user} already exists')
        else:
            logging.log(3, 'User already exists')

    @commands.command()
    # @commands.has_role('unverified')
    async def request_membership(self, ctx, first_name: str, last_name: str, email: str):
        def build_embed(title: str, first_name: str, last_name: str, email: str) -> discord.Embed:
            auth_req_embed = discord.Embed(title=f'{title}')
            auth_req_embed.set_author(name=user, icon_url=user.avatar_url)
            auth_req_embed.add_field(name="Email", value=f'{email}', inline=False)
            auth_req_embed.add_field(name='First Name', value=f'{first_name}', inline=True)
            auth_req_embed.add_field(name='Last Name', value=f'{last_name}', inline=True)
            auth_req_embed.add_field(name='Instructions', value=f'\U0001f44d to add {user} to group', inline=False)

            return auth_req_embed
        try:
            guild = ctx.guild
            user = ctx.message.author

            awaiting_verification_channel = discord.utils.get(guild.channels, id=int(self.config["auth_channel"]))

            auth_req_embed = build_embed(title='LDAP REQUEST', first_name=first_name, last_name=last_name, email=email)

            sent_embed = await awaiting_verification_channel.send(embed=auth_req_embed)

            await sent_embed.add_reaction('\U0001f44d')
            await sent_embed.add_reaction('\U0001f44e')

            logging.log(3, f'{user} requested membership')
        except commands.errors.CheckFailure:
            if 'verified' in user.roles:
                ctx.send('You have already been granted a membership')
            if 'awaiting_approval' in user.roles:
                ctx.send('Your request has already been sent to the administrators')

    def _get_unverified_usernames(self):
        guild = self.guilds[0]

        roles = discord.utils.get(guild.roles, id=self.config["unverified_role"])
        usernames_raw = [role for role in roles.members]

        usernames = []

        for i in usernames_raw:
            user = i.name + "#" + i.discriminator
            usernames.append(user)
        return usernames

    @commands.command()
    async def delete_user(self, ctx, user):
        pass

    @commands.command()
    async def kick_user(self, ctx, user):
        pass

    @commands.command()
    async def link_user(self, ctx, user):
        pass

    @commands.command()
    async def sync_ldap_groups(self, ctx):
        pass


def setup(bot):
    bot.add_cog(LDAP(bot))

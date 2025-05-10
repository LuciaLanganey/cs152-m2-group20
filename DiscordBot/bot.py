# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from report import Report
import pdb

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']


class ModBot(discord.Client):
    def __init__(self): 
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True # Enable reaction intents
        super().__init__(intents=intents)
        self.group_num = None
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")

        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        print(f"Message from {message.author.name}: {message.content} (Guild: {message.guild})")

        # Ignore messages from the bot 
        if message.author.id == self.user.id:
            return

        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def on_reaction_add(self, reaction, user):
        """
        Handle reactions on messages in the mod channel
        """
        if user.id == self.user.id:
            return

        guild_id = reaction.message.guild.id
        mod_channel = self.mod_channels.get(guild_id)

        if not mod_channel or reaction.message.channel.id != mod_channel.id:
            return

        emoji = str(reaction.emoji)

        if emoji == "🟢":
            await reaction.message.channel.send(f"Moderator {user.name} has confirmed this is a violation.")
            # Add escalation decision reactions to the same message
            await reaction.message.channel.send(
                "Does this content require escalation due to severity or legal concerns?\n"
                "React ✅ (Yes) or ❌ (No)."
            )
            await reaction.message.add_reaction("✅")
            await reaction.message.add_reaction("❌")

        elif emoji == "🔴":
            await reaction.message.channel.send(f"Moderator {user.name} has determined this is not a violation.")
            await reaction.message.channel.send("The user who submitted the message will be warned.")

        elif emoji == "🟡":
            await reaction.message.channel.send(
                f"Moderator {user.name} is not sure if this report is a violation. Requesting second review.\n"
                "Does this content violate the Community Standards on 'Coercion involving intimate content'?\n"
                "React 🟢 (Yes) or 🔴 (No)."
            )

        elif emoji == "✅":
            await reaction.message.channel.send(
                "Escalating to Trust & Safety or Legal Team for further investigation and potential law enforcement referral."
            )

        elif emoji == "❌":
            action_prompt = (
                "**Which type of action will you take?**\n"
                "React with one of the following:\n\n"
                "🗑️ — Delete content → Content deleted and user informed\n"
                "⚠️ — Content Labeling / Warning Banners → User informed about warning\n"
                "🫥 — Soft Interventions:\n"
                "  🫣 — Content blur\n"
                "  📵 — Temporary Messaging Block\n"
                "  📚 — Send Educational Warning\n"
                "⛔ — Disable account → Content deleted and user notified of account suspension"
            )
            await reaction.message.channel.send(action_prompt)
            await reaction.message.add_reaction("🗑️")
            await reaction.message.add_reaction("⚠️")
            await reaction.message.add_reaction("🫥")
            await reaction.message.add_reaction("⛔")
            await reaction.message.add_reaction("🫣")
            await reaction.message.add_reaction("📵")
            await reaction.message.add_reaction("📚")

        elif emoji == "🗑️":
            await reaction.message.channel.send("Content deleted and user informed.")

        elif emoji == "⚠️":
            await reaction.message.channel.send("Content labeled with a warning banner. User informed about warning.")

        elif emoji == "🫥":
            await reaction.message.channel.send(
                "Soft intervention selected. Please choose:\n"
                "🫣 — Content blur\n"
                "📵 — Temporary Messaging Block\n"
                "📚 — Send Educational Warning"
            )
            await reaction.message.add_reaction("🫣")
            await reaction.message.add_reaction("📵")
            await reaction.message.add_reaction("📚")

        elif emoji in ["🫣", "📵", "📚"]:
            await reaction.message.channel.send("Soft intervention applied. User informed about the action.")

        elif emoji == "⛔":
            await reaction.message.channel.send("Account disabled. Content deleted and user notified of account suspension.")
            
    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # Let the report class handle this message; forward all the messages it returns to us
        responses = await self.reports[author_id].handle_message(message)
        for r in responses:
            await message.channel.send(r)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            self.reports.pop(author_id)

    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return

        # Forward the message to the mod channel
        mod_channel = self.mod_channels.get(message.guild.id)
        if mod_channel:
            await mod_channel.send(f'Forwarded message:\n{message.author.name}: "{message.content}"')
            scores = self.eval_text(message.content)
            await mod_channel.send(self.code_format(scores))

    def eval_text(self, message):
        ''''
        TODO: Once you know how you want to evaluate messages in your channel, 
        insert your code here! This will primarily be used in Milestone 3. 
        '''
        return message

    def code_format(self, text):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel. 
        '''
        return "Evaluated: '" + text+ "'"


client = ModBot()
client.run(discord_token)
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from report import Report
from ai_classifier import AIClassifier
from database import DatabaseManager
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
        self.ai_classifier = None
        self.database = None
        self.pending_decisions = {}

    async def on_ready(self):
        """Called when bot connects to Discord"""
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        self._parse_group_number()
        
        # Find mod channels for each guild
        self._find_mod_channels()
        
        # Initialize AI and database
        await self._initialize_ai_and_database()

    async def _initialize_ai_and_database(self):
        try:
            print("Initializing classifier")
            self.ai_classifier = AIClassifier()
            
            print("Initializing database connection")
            self.database = DatabaseManager()
            
            print("Classifier and database systems ready")
            
        except Exception as e:
            print(f"Error initializing Classifier/Database: {e}")

    def _parse_group_number(self):
        """Extract group number from bot's name"""
        match = re.search(r'[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be 'Group # Bot'.")

    def _find_mod_channels(self):
        """Find the mod channel for each guild"""
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

        # Only handle reactions in mod channels
        if not mod_channel or reaction.message.channel.id != mod_channel.id:
            return

        await self._handle_mod_reaction(reaction, user)

    async def _handle_mod_reaction(self, reaction, user):
        """Process moderator reactions and take appropriate actions"""
        emoji = str(reaction.emoji)
        channel = reaction.message.channel
        mod_name = user.name
        message_id = str(reaction.message.id)

        # Initial violation assessment
        if emoji == "🟢":
            await channel.send(f"Moderator {mod_name} has confirmed this is a violation.")
            await self._add_escalation_reactions(reaction.message)
            await self._handle_violation_confirmation(message_id, mod_name)

        elif emoji == "🔴":
            await channel.send(f"Moderator {mod_name} has determined this is not a violation.")
            await channel.send("The user who submitted the message will be notified.")
            await self._handle_false_positive(message_id, mod_name)

        elif emoji == "🟡":
            await channel.send(
                f"Moderator {mod_name} is not sure if this report is a violation. Requesting second review.\n"
                "Does this content violate the Community Standards on 'Coercion involving intimate content'?\n"
                "React 🟢 (Yes) or 🔴 (No)."
            )

        # Escalation decisions
        elif emoji == "✅":
            await channel.send(
                "Escalating to Trust & Safety or Legal Team for further investigation and potential law enforcement referral."
            )

        elif emoji == "❌":
            await self._show_action_options(channel)

        # Moderation actions
        elif emoji in ["🗑️", "⚠️", "🫥", "⛔", "🫣", "📵", "📚"]:
            await self._handle_mod_action(emoji, channel)

        # Log moderation action to database
        if self.database:
            try:
                action_data = {
                    'moderator_id': str(user.id),
                    'moderator_username': mod_name,
                    'action_type': emoji,
                    'action_details': f'Moderator reaction: {emoji}'
                }
                await self.database.log_moderation_action(action_data)
            except Exception as e:
                print(f"Error logging moderation action: {e}")

    async def _handle_violation_confirmation(self, mod_message_id, mod_name):
        """Handle when moderator confirms a violation"""
        if mod_message_id in self.pending_decisions:
            decision_data = self.pending_decisions[mod_message_id]
            
            if self.database:
                await self.database.update_user_stats(
                    decision_data['user_id'], 
                    decision_data['guild_id'], 
                    decision_data['username'],
                    violation=True
                )
                
                # Update the flagged message record
                if decision_data.get('flagged_msg_id'):
                    await self.database.update_flagged_message_status(
                        decision_data['flagged_msg_id'], 
                        'confirmed_violation',
                        mod_name
                    )

    async def _handle_false_positive(self, mod_message_id, mod_name):
        """Handle when moderator determines it's not a violation (false positive)"""
        if mod_message_id in self.pending_decisions:
            decision_data = self.pending_decisions[mod_message_id]
            
            if self.database:
                await self.database.update_user_stats(
                    decision_data['user_id'], 
                    decision_data['guild_id'], 
                    decision_data['username'],
                    false_positive=True
                )
                
                # Update the flagged message record
                if decision_data.get('flagged_msg_id'):
                    await self.database.update_flagged_message_status(
                        decision_data['flagged_msg_id'], 
                        'false_positive',
                        mod_name
                    )

    async def _add_escalation_reactions(self, message):
        """Add escalation decision reactions"""
        await message.channel.send(
            "Does this content require escalation due to severity or legal concerns?\n"
            "React ✅ (Yes) or ❌ (No)."
        )
        await message.add_reaction("✅")
        await message.add_reaction("❌")

    async def _show_action_options(self, channel):
        """Display moderation action options"""
        action_prompt = (
            "**Which type of action will you take?**\n"
            "React with one of the following:\n\n"
            "🗑️ — Delete content → Content deleted and user informed\n"
            "⚠️ — Content Labeling / Warning Banners → User informed about warning\n"
            "🫥 — Soft Interventions:\n"
            "  🫣 — Content blur\n"
            "  📵 — Temporary Messaging Block\n"
            "  📚 — Send Educational Warning\n"
            "⛔ — Disable account → Content deleted and user notified of account suspension"
        )
        message = await channel.send(action_prompt)
        
        # Add all action reactions
        actions = ["🗑️", "⚠️", "🫥", "⛔", "🫣", "📵", "📚"]
        for action in actions:
            await message.add_reaction(action)

    async def _handle_mod_action(self, emoji, channel):
        """Handle specific moderation actions"""
        actions = {
            "🗑️": "Content deleted and user informed.",
            "⚠️": "Content labeled with a warning banner. User informed about warning.",
            "🫣": "Soft intervention applied. User informed about the action.",
            "📵": "Soft intervention applied. User informed about the action.",
            "📚": "Soft intervention applied. User informed about the action.",
            "⛔": "Account disabled. Content deleted and user notified of account suspension."
        }

        if emoji == "🫥":
            await channel.send(
                "Soft intervention selected. Please choose:\n"
                "🫣 — Content blur\n"
                "📵 — Temporary Messaging Block\n"
                "📚 — Send Educational Warning"
            )
            for soft_action in ["🫣", "📵", "📚"]:
                await channel.add_reaction(soft_action)
        else:
            await channel.send(actions.get(emoji, "Action taken."))

    async def handle_dm(self, message):
        """Handle direct messages (reporting flow)"""
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply = ("Use the `report` command to begin the reporting process.\n"
                    "Use the `cancel` command to cancel the report process.\n")
            await message.channel.send(reply)
            return

        author_id = message.author.id

        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return

        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)

        # Let the report class handle this message; forward all the messages it returns to us
        responses = await self.reports[author_id].handle_message(message)
        for response in responses:
            await message.channel.send(response)

        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            self.reports.pop(author_id)

    async def handle_channel_message(self, message):
        """Handle messages in guild channels"""
        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return

        # Update user statistics for total messages
        if self.database:
            await self.database.update_user_stats(
                str(message.author.id), 
                str(message.guild.id), 
                message.author.name
            )

        # Evaluate message content (placeholder for AI integration)
        evaluation = await self.eval_text(message.content, message)
        
        # Only send to mod channel if flagged for review
        if isinstance(evaluation, dict) and evaluation.get('is_violation', False):
            # Update user stats for flagged message
            if self.database:
                await self.database.update_user_stats(
                    str(message.author.id), 
                    str(message.guild.id), 
                    message.author.name,
                    flagged=True
                )
            
            mod_channel = self.mod_channels.get(message.guild.id)
            if mod_channel:
                await mod_channel.send(f'**Flagged Message** from {message.author.name}:\n"{message.content}"')
                await mod_channel.send(self.code_format(evaluation))
                
                # Add reaction options for flagged messages
                sent_message = await mod_channel.send(
                    "**Moderator Actions:** Does this content violate Community Standards?\n"
                    "-React 🟢 if this is a violation\n"
                    "-React 🔴 if this is not a violation\n"
                    "-React 🟡 if you are unsure"
                )
                await sent_message.add_reaction("🟢")
                await sent_message.add_reaction("🔴")
                await sent_message.add_reaction("🟡")
                
                # Store decision tracking data
                flagged_msg_id = evaluation.get('db_record_id')
                self.pending_decisions[str(sent_message.id)] = {
                    'user_id': str(message.author.id),
                    'guild_id': str(message.guild.id),
                    'username': message.author.name,
                    'message_content': message.content,
                    'flagged_msg_id': flagged_msg_id
                }

    async def eval_text(self, message_content, message_obj=None):
        ''''
        TODO: Once you know how you want to evaluate messages in your channel, 
        insert your code here! This will primarily be used in Milestone 3. 
        '''
        if self.ai_classifier:
            try:
                # Get user statistics for context
                user_stats = None
                if self.database and message_obj:
                    user_stats = await self.database.get_user_stats(
                        str(message_obj.author.id), 
                        str(message_obj.guild.id)
                    )
                
                # Use enhanced classification with user context
                if user_stats and hasattr(self.ai_classifier, 'classify_message_with_user_context'):
                    ai_result = await self.ai_classifier.classify_message_with_user_context(
                        message_content, user_stats
                    )
                else:
                    # Fallback to basic classification
                    ai_result = await self.ai_classifier.classify_message(message_content)
                
                # Log to database if flagged
                if ai_result['is_violation'] and self.database and message_obj:
                    message_data = {
                        'message_id': str(message_obj.id),
                        'guild_id': str(message_obj.guild.id),
                        'channel_id': str(message_obj.channel.id),
                        'user_id': str(message_obj.author.id),
                        'username': message_obj.author.name,
                        'content': message_content,
                        'timestamp': message_obj.created_at,
                        'source': 'ai_detection',
                        'ai_scores': ai_result['ai_scores'],
                        'final_classification': ai_result['final_classification'],
                        'moderation_status': 'pending',
                        'user_context_used': user_stats is not None
                    }
                    # Store the database record ID in the result
                    db_record_id = await self.database.log_flagged_message(message_data)
                    ai_result['db_record_id'] = db_record_id
                
                return ai_result
            except Exception as e:
                print(f"Classifier evaluation failed: {e}")
                return message_content
        return message_content

    def code_format(self, text):
        ''''
        TODO: Once you know how you want to show that a message has been 
        evaluated, insert your code here for formatting the string to be 
        shown in the mod channel. 
        '''
        if isinstance(text, dict) and 'ai_scores' in text:
            ai_scores = text['ai_scores']
            details = text['analysis_details']
            
            formatted_output = f"**Classifier Analysis Results:**\n"
            formatted_output += f"-Combined Score: {ai_scores['combined_score']}%"
            
            # Show if user context influenced the score
            if 'user_risk_adjustment' in ai_scores:
                original_score = ai_scores.get('original_combined_score', ai_scores['combined_score'])
                adjustment = ai_scores['user_risk_adjustment']
                if adjustment != 0:
                    formatted_output += f" (Original: {original_score}%, Adjusted: {'+' if adjustment > 0 else ''}{adjustment}%)"
                formatted_output += f"\n"
            else:
                formatted_output += f"\n"
                
            formatted_output += f"-Classification: {text['final_classification']}\n"
            formatted_output += f"-Confidence Level: {text['confidence_level']}\n"
            
            # Show user context if available
            user_context = details.get('user_context')
            if user_context:
                formatted_output += f"\n**User Context:**\n"
                formatted_output += f"-Risk Level: {user_context['risk_level']}\n"
                formatted_output += f"-Total Messages: {user_context['total_messages']}\n"
                formatted_output += f"-Violation Rate: {user_context['violation_rate']:.1%}\n"
                formatted_output += f"-False Positive Rate: {user_context['false_positive_rate']:.1%}\n"
            
            formatted_output += f"\n**Detailed Scores:**\n"
            formatted_output += f"-Gemini: {ai_scores['gemini_confidence']}% ({ai_scores['gemini_classification']})\n"
            formatted_output += f"-Natural Language: {ai_scores['natural_language_confidence']:.1f}%\n"
            
            if details['gemini_risk_indicators']:
                formatted_output += f"\n**Risk Indicators:**\n"
                for indicator in details['gemini_risk_indicators']:
                    formatted_output += f"-{indicator}\n"
            
            if details['nl_threat_patterns']:
                formatted_output += f"\n**Threat Patterns:**\n"
                for pattern in details['nl_threat_patterns']:
                    formatted_output += f"-{pattern}\n"
            
            if text['is_violation']:
                formatted_output += f"\n**Flagged for Review** (Score > 75%)\n"
            else:
                formatted_output += f"\n**Below violation threshold**\n"
            
            return formatted_output
        else:
            return f"Evaluated: '{text}'"


def main():
    """Main function to run the bot"""
    client = ModBot()
    client.run(discord_token)


if __name__ == "__main__":
    main()
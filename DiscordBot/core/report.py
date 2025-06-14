from enum import Enum, auto
import discord
import re


class State(Enum):
    """Report flow states"""
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    AWAITING_REPORT_TYPE = auto()
    AWAITING_REPORT_SUBTYPE = auto()
    CONTINUING_BULLYING_AND_UNWANTED_FLOW = auto()
    AWAITING_THREAT_DETAILS = auto()
    AWAITING_BLOCK_DECISION = auto()
    AWAITING_DETAILS = auto()
    REPORT_COMPLETE = auto()


class Report:
    """Handles the user reporting flow through DMs"""
    
    # Command keywords
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    
    # Report type mapping
    REPORT_TYPES = {
        "1": "Sexual Coercion/Sextortion",
        "2": "Harassment or Bullying", 
        "3": "Violence",
        "4": "Deceptive Content",
        "5": "False Information"
    }
    
    # Harassment subtypes
    HARASSMENT_SUBTYPES = {
        "1": "Repeated unwanted messages",
        "2": "Insults or slurs",
        "3": "Threats of harm"
    }
    
    # Violence subtypes
    VIOLENCE_SUBTYPES = {
        "1": "Hate Speech",
        "2": "Terrorism and Extremism", 
        "3": "Incitement to Violence"
    }
    
    # Deceptive content subtypes
    DECEPTIVE_SUBTYPES = {
        "1": "Illegal Sale",
        "2": "Fraud",
        "3": "Scam"
    }
    
    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        
        # Report data
        self.reported_message = None
        self.message_object = None
        self.selected_type = None
        self.selected_subtype = None
        self.additional_details = []
        self.ai_evaluation = None
    
    async def handle_message(self, message):
        """Main message handler for the reporting flow"""
        self.message_object = message
        
        # Handle cancel at any time
        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]
        
        # Handle help at any time
        if message.content == self.HELP_KEYWORD:
            return [self._get_help_text()]
        
        # Route to appropriate handler based on current state
        handlers = {
            State.REPORT_START: self._handle_start,
            State.AWAITING_MESSAGE: self._handle_message_link,
            State.AWAITING_REPORT_TYPE: self._handle_report_type,
            State.AWAITING_REPORT_SUBTYPE: self._handle_report_subtype,
            State.CONTINUING_BULLYING_AND_UNWANTED_FLOW: self._handle_bullying_flow,
            State.AWAITING_THREAT_DETAILS: self._handle_threat_details,
            State.AWAITING_BLOCK_DECISION: self._handle_block_decision,
            State.AWAITING_DETAILS: self._handle_additional_details
        }
        
        handler = handlers.get(self.state)
        if handler:
            return await handler(message)
        
        return []
    
    def _get_help_text(self):
        """Return help text for users"""
        return ("Reporting Help:\n"
                "- Type `report` to start a new report\n"
                "- Type `cancel` at any time to cancel your report\n"
                "- Follow the prompts to complete your report")
    
    async def _handle_start(self, message):
        """Handle the initial report start"""
        reply = ("Thank you for starting the reporting process. "
                "Say `help` at any time for more information.\n\n"
                "Please copy paste the link to the message you want to report.\n\n"
                "You can obtain this link by right-clicking the message and clicking `Copy Message Link`.")
        
        self.state = State.AWAITING_MESSAGE
        return [reply]
    
    async def _handle_message_link(self, message):
        """Parse and validate the message link"""
        # Extract IDs from Discord message link
        match = re.search(r'/(\d+)/(\d+)/(\d+)', message.content)
        if not match:
            return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
        
        guild_id, channel_id, message_id = match.groups()
        
        # Validate guild
        guild = self.client.get_guild(int(guild_id))
        if not guild:
            return ["I cannot accept reports of messages from guilds that I'm not in. "
                   "Please have the guild owner add me to the guild and try again."]
        
        # Validate channel
        channel = guild.get_channel(int(channel_id))
        if not channel:
            return ["It seems this channel was deleted or never existed. "
                   "Please try again or say `cancel` to cancel."]
        
        # Fetch the actual message
        try:
            reported_message = await channel.fetch_message(int(message_id))
            self.reported_message = reported_message
            
            # Evaluate the message with AI first
            await self._evaluate_message_with_ai()
            
            return await self._show_message_and_types(reported_message)
        except discord.errors.NotFound:
            return ["It seems this message was deleted or never existed. "
                   "Please try again or say `cancel` to cancel."]
    
    async def _evaluate_message_with_ai(self):
        if self.client.ai_classifier and self.reported_message:
            try:
                print(f"Evaluating reported message with classifier")
                self.ai_evaluation = await self.client.ai_classifier.classify_message(
                    self.reported_message.content
                )
                print(f"AI evaluation complete. Score: {self.ai_evaluation.get('ai_scores', {}).get('combined_score', 'N/A')}%")
                
                # Log to database if flagged
                if self.ai_evaluation.get('is_violation', False) and self.client.database:
                    message_data = {
                        'message_id': str(self.reported_message.id),
                        'guild_id': str(self.reported_message.guild.id),
                        'channel_id': str(self.reported_message.channel.id),
                        'user_id': str(self.reported_message.author.id),
                        'username': self.reported_message.author.name,
                        'content': self.reported_message.content,
                        'timestamp': self.reported_message.created_at,
                        'source': 'user_report',
                        'ai_scores': self.ai_evaluation['ai_scores'],
                        'final_classification': self.ai_evaluation['final_classification'],
                        'moderation_status': 'pending',
                        'reporter_id': str(self.message_object.author.id),
                        'reporter_username': self.message_object.author.name
                    }
                    db_record_id = await self.client.database.log_flagged_message(message_data)
                    self.ai_evaluation['db_record_id'] = db_record_id
                    
            except Exception as e:
                print(f"Error evaluating reported message with AI: {e}")
                self.ai_evaluation = None
    
    async def _show_message_and_types(self, message):
        """Display the found message and report type options"""
        self.state = State.MESSAGE_IDENTIFIED
        
        reply = (f"I found this message:\n```{message.author.name}: {message.content}```\n"
                "What is wrong with this content? Please respond with a number.\n\n"
                "1. Sexual Coercion/Sextortion\n"
                "2. Harassment or Bullying\n" 
                "3. Violence\n"
                "4. Deceptive Content\n"
                "5. False Information\n")
        
        self.state = State.AWAITING_REPORT_TYPE
        return [reply]
    
    async def _handle_report_type(self, message):
        """Handle report type selection"""
        selection = message.content.strip()
        
        if selection not in self.REPORT_TYPES:
            return ["Please enter a number between 1 and 5 to select a report type."]
        
        self.selected_type = self.REPORT_TYPES[selection]
        
        # Handle different types
        if selection == "1":  # Sexual Coercion/Sextortion
            reply = ("You selected Sexual Coercion/Sextortion.\n\n"
                    "Are you under 18 years old? Please respond with 'yes' or 'no'.")
            
            self.state = State.CONTINUING_BULLYING_AND_UNWANTED_FLOW
            return [reply]
        
        elif selection == "2":  # Harassment or Bullying
            return self._show_harassment_subtypes()
        
        elif selection == "3":  # Violence
            return self._show_violence_subtypes()
        
        elif selection == "4":  # Deceptive Content
            return self._show_deceptive_subtypes()
        
        elif selection == "5":  # False Information
            reply = ("You selected False Information.\n\n"
                    "Do you want to block this user? Please respond with 'yes' or 'no'.")
            
            self.state = State.AWAITING_BLOCK_DECISION
            return [reply]
    
    def _show_violence_subtypes(self):
        """Show violence subtype options"""
        reply = ("You selected Violence. Which type of violence? Please respond with a number.\n"
                "1. Hate Speech\n"
                "2. Terrorism and Extremism\n"
                "3. Incitement to Violence\n")
        
        self.state = State.AWAITING_REPORT_SUBTYPE
        return [reply]
    
    def _show_deceptive_subtypes(self):
        """Show deceptive content subtype options"""
        reply = ("You selected Deceptive Content. Which type of deceptive content? "
                "Please respond with a number.\n\n"
                "1. Illegal Sale\n"
                "2. Fraud\n" 
                "3. Scam\n")
        
        self.state = State.AWAITING_REPORT_SUBTYPE
        return [reply]
    
    def _show_harassment_subtypes(self):
        """Show harassment subtype options"""
        reply = ("You selected Harassment or Bullying. Which type of content? Please respond with a number.\n"
                "1. Repeated unwanted messages\n"
                "2. Insults or slurs\n"
                "3. Threats of harm\n")
        
        self.state = State.AWAITING_REPORT_SUBTYPE
        return [reply]
    
    async def _handle_report_subtype(self, message):
        """Handle report subtype selection"""
        selection = message.content.strip()
        
        if self.selected_type == "Harassment or Bullying":
            return await self._handle_harassment_subtype(selection)
        elif self.selected_type == "Violence":
            return await self._handle_violence_subtype(selection)
        elif self.selected_type == "Deceptive Content":
            return await self._handle_deceptive_subtype(selection)
        
        return ["Invalid selection. Please try again."]
    
    async def _handle_harassment_subtype(self, selection):
        """Handle harassment subtype selection"""
        if selection not in self.HARASSMENT_SUBTYPES:
            return ["Please enter a number between 1 and 3 to select a harassment subtype."]
        
        self.selected_subtype = self.HARASSMENT_SUBTYPES[selection]
        
        reply = (f"You selected {self.selected_subtype}.\n\n"
                "Do you want to block this user? Please respond with 'yes' or 'no'.")
        
        self.state = State.AWAITING_BLOCK_DECISION
        return [reply]
    
    async def _handle_violence_subtype(self, selection):
        """Handle violence subtype selection"""
        if selection not in self.VIOLENCE_SUBTYPES:
            return ["Please enter a number between 1 and 3 to select a violence subtype."]
        
        self.selected_subtype = self.VIOLENCE_SUBTYPES[selection]
        
        reply = (f"You selected {self.selected_subtype}.\n\n"
                "Do you want to block this user? Please respond with 'yes' or 'no'.")
        
        self.state = State.AWAITING_BLOCK_DECISION
        return [reply]
    
    async def _handle_deceptive_subtype(self, selection):
        """Handle deceptive content subtype selection"""
        if selection not in self.DECEPTIVE_SUBTYPES:
            return ["Please enter a number between 1 and 3 to select a deceptive content subtype."]
        
        self.selected_subtype = self.DECEPTIVE_SUBTYPES[selection]
        
        reply = (f"You selected {self.selected_subtype}.\n\n"
                "Do you want to block this user? Please respond with 'yes' or 'no'.")
        
        self.state = State.AWAITING_BLOCK_DECISION
        return [reply]
    
    async def _handle_bullying_flow(self, message):
        """Handle the flow for sexual coercion/sextortion"""
        response = message.content.lower().strip()
        
        if response not in ["yes", "no"]:
            return ["Please respond with 'yes' or 'no'."]
        
        # Record age information
        age_info = "User is under 18" if response == "yes" else "User is 18 or older"
        self.additional_details = [age_info]
        
        reply = ("Thank you for this information.\n\n"
                "Did the user threaten to share sensitive content outside of the platform? Please respond with 'yes' or 'no'.")
        
        self.state = State.AWAITING_THREAT_DETAILS
        return [reply]
    
    async def _handle_threat_details(self, message):
        """Handle threat details question"""
        response = message.content.lower().strip()
        
        if response not in ["yes", "no"]:
            return ["Please respond with 'yes' or 'no'."]
        
        # Record threat information
        threat_info = ("User threatened to share sensitive content" if response == "yes" 
                    else "User did not threaten to share sensitive content")
        self.additional_details.append(threat_info)
        
        reply = ("Thank you for this information.\n\n"
                "Do you want to block this user? Please respond with 'yes' or 'no'.")
        
        self.state = State.AWAITING_BLOCK_DECISION
        return [reply]
        
    async def _handle_block_decision(self, message):
        """Handle the user's decision to block or not"""
        response = message.content.lower().strip()
        
        if response not in ["yes", "no"]:
            return ["Please respond with 'yes' or 'no'."]
        
        # Record block decision
        block_info = "User wants to block sender" if response == "yes" else "User does not want to block sender"
        self.additional_details.append(block_info)
        
        return await self._complete_detailed_report()
    
    async def _handle_additional_details(self, message):
        """Handle additional details for 'Other' reports"""
        self.additional_details.append(message.content)
        return await self._complete_detailed_report()
    
    async def _complete_detailed_report(self):
        """Complete a detailed report with additional information"""
        reply = ("Thank you for your report. You will receive a notification as soon as we review your report.\n\n"
                "To block this user, please go to their profile and click `Block User`.\n\n"
                "To access the community standards, please say `community standards`.\n\n"
                "If you would like to report something else, please say `report`.\n")
        
        self.state = State.REPORT_COMPLETE
        await self._send_to_mod_channel()
        return [reply]
    
    async def _send_to_mod_channel(self):
        """Send the completed report to moderators"""
        if not self.reported_message:
            print("No message to report")
            return
        
        # Send to all mod channels
        for guild in self.client.guilds:
            mod_channel = self.client.mod_channels.get(guild.id)
            if mod_channel:
                try:
                    summary = self._build_report_summary()
                    mod_msg = await mod_channel.send(summary)
                    
                    # Add AI evaluation if available
                    ai_msg = None
                    if self.ai_evaluation:
                        ai_summary = self._build_ai_evaluation_summary()
                        ai_msg = await mod_channel.send(ai_summary)
                    
                    # Add reaction options
                    reaction_target = ai_msg if ai_msg else mod_msg
                    await reaction_target.add_reaction("🟢")
                    await reaction_target.add_reaction("🔴")  
                    await reaction_target.add_reaction("🟡")
                    
                    # Store decision tracking data for user reports
                    if self.ai_evaluation and self.ai_evaluation.get('db_record_id'):
                        self.client.pending_decisions[str(reaction_target.id)] = {
                            'user_id': str(self.reported_message.author.id),
                            'guild_id': str(self.reported_message.guild.id),
                            'username': self.reported_message.author.name,
                            'message_content': self.reported_message.content,
                            'flagged_msg_id': self.ai_evaluation.get('db_record_id'),
                            'source': 'user_report',
                            'reporter_id': str(self.message_object.author.id)
                        }
                    
                    print(f"Report sent to mod channel in guild {guild.name}")
                    return
                    
                except Exception as e:
                    print(f"Error sending report to mod channel: {e}")
    
    def _build_report_summary(self):
        """Build the report summary for moderators"""
        summary = f"**New Report** from {self.message_object.author.name}\n\n"
        summary += f"**Reported Message:** from {self.reported_message.author.name}\n"
        summary += f"```{self.reported_message.content}```\n"
        summary += f"**Report Type:** {self.selected_type}\n"
        
        if self.selected_subtype:
            summary += f"**Subtype:** {self.selected_subtype}\n"
        
        if self.additional_details:
            summary += f"**Additional Details:** {', '.join(self.additional_details)}\n"
        
        return summary
    
    def _build_ai_evaluation_summary(self):
        """Build AI evaluation summary for moderators"""
        if not self.ai_evaluation:
            return "Not available"
        
        ai_scores = self.ai_evaluation.get('ai_scores', {})
        details = self.ai_evaluation.get('analysis_details', {})
        
        summary = f"**Classifier Results:**\n"
        summary += f"- Combined Score: {ai_scores.get('combined_score', 'N/A')}%\n"
        summary += f"- Classification: {self.ai_evaluation.get('final_classification', 'N/A')}\n"
        summary += f"-AI Assessment: {'FLAGGED' if self.ai_evaluation.get('is_violation', False) else 'Not Flagged'}\n"
        
        summary += f"\n**AI Scores:**\n"
        summary += f"-Gemini: {ai_scores.get('gemini_confidence', 'N/A')}% ({ai_scores.get('gemini_classification', 'N/A')})\n"
        summary += f"-Natural Language: {ai_scores.get('natural_language_confidence', 'N/A'):.1f}%\n"
        
        if details.get('gemini_risk_indicators'):
            summary += f"\n**Risk Indicators:**\n"
            for indicator in details['gemini_risk_indicators']:
                summary += f"-{indicator}\n"
        
        summary += f"\n**Human Moderator Review Required:**\n"
        summary += f"Does this content violate the Community Standards involving {self.selected_type}?\n"
        summary += "-React '🟢' if this is a violation\n"
        summary += "-React '🔴' if this is not a violation\n" 
        summary += "-React '🟡' if you are unsure\n"
        
        return summary
    
    def report_complete(self):
        """Check if the report is complete"""
        return self.state == State.REPORT_COMPLETE
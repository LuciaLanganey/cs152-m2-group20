# report.py
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
        "1": "Disinformation",
        "2": "Violence", 
        "3": "Deceptive Content",
        "4": "Bullying and Unwanted Contact",
        "5": "Other"
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
    
    # Bullying subtypes
    BULLYING_SUBTYPES = {
        "1": "Coersion involving intimate content",
        "2": "Bullying",
        "3": "Stalking"
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
        
        # Flow flags
        self.violence_subtype_flag = False
        self.deceptive_subtype_flag = False
        self.bullying_subtype_flag = False
        self.other_type_flag = False
    
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
            return await self._show_message_and_types(reported_message)
        except discord.errors.NotFound:
            return ["It seems this message was deleted or never existed. "
                   "Please try again or say `cancel` to cancel."]
    
    async def _show_message_and_types(self, message):
        """Display the found message and report type options"""
        self.state = State.MESSAGE_IDENTIFIED
        
        reply = (f"I found this message:\n```{message.author.name}: {message.content}```\n"
                "What is wrong with this content? Please respond with a number.\n\n"
                "1. Disinformation\n"
                "2. Violence\n" 
                "3. Deceptive Content\n"
                "4. Bullying and Unwanted Contact\n"
                "5. Other\n")
        
        self.state = State.AWAITING_REPORT_TYPE
        return [reply]
    
    async def _handle_report_type(self, message):
        """Handle report type selection"""
        selection = message.content.strip()
        
        if selection not in self.REPORT_TYPES:
            return ["Please enter a number between 1 and 5 to select a report type."]
        
        self.selected_type = self.REPORT_TYPES[selection]
        
        # Handle different types
        if selection == "1":  # Disinformation
            return await self._complete_simple_report()
        
        elif selection == "2":  # Violence
            self.violence_subtype_flag = True
            return self._show_violence_subtypes()
        
        elif selection == "3":  # Deceptive Content
            self.deceptive_subtype_flag = True
            return self._show_deceptive_subtypes()
        
        elif selection == "4":  # Bullying and Unwanted Contact
            self.bullying_subtype_flag = True
            return self._show_bullying_subtypes()
        
        elif selection == "5":  # Other
            self.other_type_flag = True
            self.state = State.AWAITING_DETAILS
            return ["You selected Other. Please provide details."]
    
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
    
    def _show_bullying_subtypes(self):
        """Show bullying subtype options"""
        reply = ("You selected Bullying and Unwanted Contact. Which type of unwanted content? "
                "Please respond with a number.\n\n"
                "1. Coersion involving intimate content\n"
                "2. Bullying\n"
                "3. Stalking\n")
        
        self.state = State.AWAITING_REPORT_SUBTYPE
        return [reply]
    
    async def _handle_report_subtype(self, message):
        """Handle report subtype selection"""
        selection = message.content.strip()
        
        if self.violence_subtype_flag:
            return await self._handle_violence_subtype(selection)
        elif self.deceptive_subtype_flag:
            return await self._handle_deceptive_subtype(selection)
        elif self.bullying_subtype_flag:
            return await self._handle_bullying_subtype(selection)
        
        return ["Invalid selection. Please try again."]
    
    async def _handle_violence_subtype(self, selection):
        """Handle violence subtype selection"""
        if selection not in self.VIOLENCE_SUBTYPES:
            return ["Please enter a number between 1 and 3 to select a violence subtype."]
        
        self.selected_subtype = self.VIOLENCE_SUBTYPES[selection]
        return await self._complete_simple_report()
    
    async def _handle_deceptive_subtype(self, selection):
        """Handle deceptive content subtype selection"""
        if selection not in self.DECEPTIVE_SUBTYPES:
            return ["Please enter a number between 1 and 3 to select a deceptive content subtype."]
        
        self.selected_subtype = self.DECEPTIVE_SUBTYPES[selection]
        return await self._complete_simple_report()
    
    async def _handle_bullying_subtype(self, selection):
        """Handle bullying subtype selection"""
        if selection not in self.BULLYING_SUBTYPES:
            return ["Please enter a number between 1 and 3 to select a bullying and unwanted contact subtype."]
        
        self.selected_subtype = self.BULLYING_SUBTYPES[selection]
        
        # Special flow for coercion involving intimate content
        if selection == "1":
            reply = ("You selected Coersion involving intimate content. We will be reporting this as "
                    "Coersion involving intimate content.\n\n"
                    "We need to ask you a few more questions to help us understand the situation.\n\n"
                    "Are you under 18 years old? Please respond with 'yes' or 'no'.\n")
            
            self.state = State.CONTINUING_BULLYING_AND_UNWANTED_FLOW
            return [reply]
        else:
            return await self._complete_simple_report()
    
    async def _handle_bullying_flow(self, message):
        """Handle the extended bullying flow for intimate content coercion"""
        response = message.content.lower().strip()
        
        if response not in ["yes", "no"]:
            return ["Please respond with 'yes' or 'no'."]
        
        # Record age information
        age_info = "User is under 18" if response == "yes" else "User is 18 or older"
        self.additional_details = [age_info]
        
        reply = ("Thank you for this information.\n\n"
                "Did the abuser threaten to distribute sensitive information on or off of the platform? "
                "Please respond with 'yes' or 'no'.\n")
        
        self.state = State.AWAITING_THREAT_DETAILS
        return [reply]
    
    async def _handle_threat_details(self, message):
        """Handle threat details question"""
        response = message.content.lower().strip()
        
        if response not in ["yes", "no"]:
            return ["Please respond with 'yes' or 'no'."]
        
        # Record threat information
        threat_info = ("Abuser threatened to distribute sensitive information" if response == "yes" 
                      else "Abuser did not threaten to distribute sensitive information")
        self.additional_details.append(threat_info)
        
        return await self._complete_detailed_report()
    
    async def _handle_additional_details(self, message):
        """Handle additional details for 'Other' reports"""
        self.additional_details.append(message.content)
        return await self._complete_detailed_report()
    
    async def _complete_simple_report(self):
        """Complete a simple report without additional questions"""
        reply = (f"You selected {self.selected_subtype or self.selected_type}. "
                f"We will be reporting this as {self.selected_subtype or self.selected_type}. "
                "Thank you for your report.\n\n"
                "If you would like to report something else, please say `report`.\n\n"
                "To block this user, please go to their profile and click `Block User`.\n\n"
                "To access the community standards, please say `community standards`.\n")
        
        self.state = State.REPORT_COMPLETE
        await self._send_to_mod_channel()
        return [reply]
    
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
                    
                    # Add reaction options for moderators
                    await mod_msg.add_reaction("🟢")  # Violation
                    await mod_msg.add_reaction("🔴")  # Not a violation  
                    await mod_msg.add_reaction("🟡")  # Unsure
                    
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
        
        summary += f"\n**Moderator Actions:** Does this content violate the Community Standards involving {self.selected_type}?\n"
        summary += "- React '🟢' if this is a violation\n"
        summary += "- React '🔴' if this is not a violation\n" 
        summary += "- React '🟡' if you are unsure\n"
        
        return summary
    
    def report_complete(self):
        """Check if the report is complete"""
        return self.state == State.REPORT_COMPLETE
from enum import Enum, auto
import discord
import re

class State(Enum):
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
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    
    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
        self.VIOLENCE_SUBTYPE_FLAG = False
        self.DECEPETIVE_SUBTYPE_FLAG = False
        self.BULLYING_AND_UNWANTED_SUBTYPE_FLAG = False
        self.OTHER_TYPE_FLAG = False
        self.MESSAGE_OBJECT = None
        self.reported_message = None
        self.selected_type = None
        self.selected_subtype = None
        self.additional_details = []
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states.
        '''
        self.MESSAGE_OBJECT = message
        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]
        
        if message.content == self.HELP_KEYWORD:
            reply = "Reporting Help:\n"
            reply += "- Type `report` to start a new report\n"
            reply += "- Type `cancel` at any time to cancel your report\n"
            reply += "- Follow the prompts to complete your report\n"
            return [reply]
        
        if self.state == State.REPORT_START:
            reply = "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]
        
        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                reported_message = await channel.fetch_message(int(m.group(3)))
                self.reported_message = reported_message
                return await self.handleAwaitMessage(reported_message)
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]
        
        if self.state == State.AWAITING_REPORT_TYPE:
            return await self.handleGetReportType(message)
        
        if self.state == State.AWAITING_REPORT_SUBTYPE:
            return await self.handleGetReportSubtype(message)

        if self.state == State.CONTINUING_BULLYING_AND_UNWANTED_FLOW:
            return await self.handleBullyingAndUnwantedFlow(message)
        
        if self.state == State.AWAITING_THREAT_DETAILS:
            return await self.handleThreatDetails(message)
            
        if self.state == State.AWAITING_DETAILS:
            self.additional_details.append(message.content)
            return await self.handleAwaitingDetails()
        
        return []        
    
    async def handleAwaitMessage(self, message):
        self.state = State.MESSAGE_IDENTIFIED
        self.message = message
        
        reply = "I found this message:\n```" + message.author.name + ": " + message.content + "```\n"
        reply += "What is wrong with this content? Please respond with a number.\n\n"
        reply += "1. Disinformation\n"
        reply += "2. Violence\n"
        reply += "3. Deceptive Content\n"
        reply += "4. Bullying and Unwanted Contact\n"
        reply += "5. Other\n"

        self.state = State.AWAITING_REPORT_TYPE
        return [reply]
    
    async def handleGetReportType(self, message):
        if message.content == "1":
            self.selected_type = "Disinformation"
            reply = "You selected Disinformation. We will be reporting this as disinformation. Thank you for your report.\n\n"
            reply += "If you would like to report something else, please say `report`.\n\n"
            reply += "To block this user, please go to their profile and click `Block User`.\n\n"
            reply += "To access the community standards, please say `community standards`.\n\n"

            self.state = State.REPORT_COMPLETE
            await self.sendToModChannel()
            return [reply]
            
        elif message.content == "2":
            self.selected_type = "Violence"
            reply = "You selected Violence. Which type of violence? Please respond with a number.\n"
            reply += "1. Hate Speech\n"
            reply += "2. Terrorism and Extremism\n"
            reply += "3. Incitement to Violence\n"

            self.VIOLENCE_SUBTYPE_FLAG = True
            self.state = State.AWAITING_REPORT_SUBTYPE
            return [reply]
            
        elif message.content == "3":
            self.selected_type = "Deceptive Content"
            reply = "You selected Deceptive Content. Which type of deceptive content? Please respond with a number.\n\n"
            reply += "1. Illegal Sale\n"
            reply += "2. Fraud\n"
            reply += "3. Scam\n"

            self.DECEPETIVE_SUBTYPE_FLAG = True
            self.state = State.AWAITING_REPORT_SUBTYPE
            return [reply]
            
        elif message.content == "4":
            self.selected_type = "Bullying and Unwanted Contact"
            reply = "You selected Bullying and Unwanted Contact. Which type of unwanted content? Please respond with a number.\n\n"
            reply += "1. Coersion involving intimate content\n"
            reply += "2. Bullying\n"
            reply += "3. Stalking\n"
                
            self.BULLYING_AND_UNWANTED_SUBTYPE_FLAG = True
            self.state = State.AWAITING_REPORT_SUBTYPE
            return [reply]
        
        elif message.content == "5":
            self.selected_type = "Other"
            reply = "You selected Other. Please provide details.\n\n"
            self.OTHER_TYPE_FLAG = True
            self.state = State.AWAITING_DETAILS
            return [reply]
        else:
            return ["Please enter a number between 1 and 5 to select a report type."]

    async def handleGetReportSubtype(self, message):
        if self.VIOLENCE_SUBTYPE_FLAG:
            if message.content == "1":
                self.selected_subtype = "Hate Speech"
                reply = "You selected Hate Speech. We will be reporting this as hate speech. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                await self.sendToModChannel()
                return [reply]
            
            elif message.content == "2":
                self.selected_subtype = "Terrorism and Extremism"
                reply = "You selected Terrorism and Extremism. We will be reporting this as Terrorism and Extremism. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                await self.sendToModChannel()
                return [reply]
            
            elif message.content == "3":
                self.selected_subtype = "Incitement to Violence"
                reply = "You selected Incitement to Violence. We will be reporting this as Incitement to Violence. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                await self.sendToModChannel()
                return [reply]
            else:
                return ["Please enter a number between 1 and 3 to select a violence subtype."]
            
        elif self.DECEPETIVE_SUBTYPE_FLAG:
            if message.content == "1":
                self.selected_subtype = "Illegal Sale"
                reply = "You selected Illegal Sale. We will be reporting this as Illegal Sale. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                await self.sendToModChannel()
                return [reply]
            
            elif message.content == "2":
                self.selected_subtype = "Fraud"
                reply = "You selected Fraud. We will be reporting this as Fraud. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                await self.sendToModChannel()
                return [reply]
            
            elif message.content == "3":
                self.selected_subtype = "Scam"
                reply = "You selected Scam. We will be reporting this as Scam. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                await self.sendToModChannel()
                return [reply]
            else:
                return ["Please enter a number between 1 and 3 to select a deceptive content subtype."]
        
        elif self.BULLYING_AND_UNWANTED_SUBTYPE_FLAG:
            if message.content == "1":
                self.selected_subtype = "Coersion involving intimate content"
                reply = "You selected Coersion involving intimate content. We will be reporting this as Coersion involving intimate content.\n\n"
                reply += "We need to ask you a few more questions to help us understand the situation.\n\n"
                reply += "Are you under 18 years old? Please respond with 'yes' or 'no'.\n\n"
                self.state = State.CONTINUING_BULLYING_AND_UNWANTED_FLOW
                return [reply]
            
            elif message.content == "2":
                self.selected_subtype = "Bullying"
                reply = "You selected Bullying. We will be reporting this as Bullying. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                await self.sendToModChannel()
                return [reply]
            
            elif message.content == "3":
                self.selected_subtype = "Stalking"
                reply = "You selected Stalking. We will be reporting this as Stalking. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                await self.sendToModChannel()
                return [reply]
            else:
                return ["Please enter a number between 1 and 3 to select a bullying and unwanted contact subtype."]
        
        return ["Invalid selection. Please try again."]
        
    async def handleBullyingAndUnwantedFlow(self, message):
        if message.content.lower() == "yes":
            self.additional_details = ["User is under 18"]
            reply = "Thank you for this information.\n\n"
            reply += "Did the abuser threaten to distribute sensitive information on or off of the platform? Please respond with 'yes' or 'no'.\n\n"
            self.state = State.AWAITING_THREAT_DETAILS
            return [reply]
            
        elif message.content.lower() == "no":
            self.additional_details = ["User is 18 or older"]
            reply = "Thank you for this information.\n\n"
            reply += "Did the abuser threaten to distribute sensitive information on or off of the platform? Please respond with 'yes' or 'no'.\n\n"
            self.state = State.AWAITING_THREAT_DETAILS
            return [reply]
        else:
            return ["Please respond with 'yes' or 'no'."]
    
    async def handleThreatDetails(self, message):
        if message.content.lower() == "yes":
            self.additional_details.append("Abuser threatened to distribute sensitive information")
            return await self.handleAwaitingDetails()
            
        elif message.content.lower() == "no":
            self.additional_details.append("Abuser did not threaten to distribute sensitive information")
            return await self.handleAwaitingDetails()
        else:
            return ["Please respond with 'yes' or 'no'."]

    async def handleAwaitingDetails(self):
        reply = "Thank you for your report. You will receive a notification as soon as we review your report.\n\n"
        reply += "To block this user, please go to their profile and click `Block User`.\n\n"
        reply += "To access the community standards, please say `community standards`.\n\n"
        reply += "If you would like to report something else, please say `report`.\n\n"
        self.state = State.REPORT_COMPLETE
        
        await self.sendToModChannel()
        print("Report sent to mod channel.")
        return [reply]
    
    async def sendToModChannel(self):
        """Send the report to the mod channel for evaluation by moderators"""
        if not self.message:
            print("No message to report")
            return
            
        for guild in self.client.guilds:
            mod_channel = self.client.mod_channels.get(guild.id)
            if mod_channel:
                summary = f"**New Report** from {self.MESSAGE_OBJECT.author.name}\n\n"
                summary += f"**Reported Message:** from {self.message.author.name}\n"
                summary += f"```{self.message.content}```\n"
                summary += f"**Report Type:** {self.selected_type}\n"
                if self.selected_subtype:
                    summary += f"**Subtype:** {self.selected_subtype}\n"
                if self.additional_details:
                    summary += f"**Additional Details:** {', '.join(self.additional_details)}\n"
                
                summary += f"\n**Moderator Actions:** Does this content violate the Community Standards involving {self.selected_type}?\n"
                summary += "- React '🟢' if this is a violation\n"
                summary += "- React '🔴' if this is not a violation\n"
                summary += "- React '🟡' if you are unsure\n"
                
                try:
                    mod_msg = await mod_channel.send(summary)
                    await mod_msg.add_reaction("🟢")
                    await mod_msg.add_reaction("🔴")
                    await mod_msg.add_reaction("🟡")

                    print(f"Report sent to mod channel in guild {guild.name}")
                    return
                except Exception as e:
                    print(f"Error sending report to mod channel: {e}")
                    
    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
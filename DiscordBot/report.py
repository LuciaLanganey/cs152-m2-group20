from enum import Enum, auto
import discord
import re

# MY COMMENT
class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    AWAITING_REPORT_TYPE = auto()
    AWAITING_REPORT_SUBTYPE = auto()
    CONTINUING_BULLYING_AND_UNWANTED_FLOW = auto()
    AWAITING_DETAILS = auto()
    REPORT_COMPLETE = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    VIOLENCE_SUBTYPE_FLAG = None
    DECEPETIVE_SUBTYPE_FLAG = None
    BULLYING_AND_UNWANTED_SUBTYPE_FLAG = None
    OTHER_TYPE_FLAG = None

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]
        
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
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
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]
            return self.handleAwaitMessage(message)
        
        if self.state == State.AWAITING_REPORT_TYPE:
            return self.handleGetReportType(message)
        
        if self.state == State.AWAITING_REPORT_SUBTYPE:
            return self.handleGetReportSubtype(message)

        if self.state == State.CONTINUING_BULLYING_AND_UNWANTED_FLOW:
            return self.handleBullyingAndUnwantedFlow(message)
        
        if self.state == State.AWAITING_DETAILS:
            return self.handleAwaitingDetails()
        return []        
    
    def handleAwaitMessage(self, message):
        # Here we've found the message - it's up to you to decide what to do next!
        self.state = State.MESSAGE_IDENTIFIED
        reply = "I found this message:\n```" + message.author.name + ": " + message.content + "```\n"
        reply += "What is wrong with this content? Please respond with a number.\n\n"
        reply += "1. Disinformation\n"
        reply += "2. Violence\n"
        reply += "3. Deceptive Content\n"
        reply += "4. Bullying and Unwanted Contact\n"
        reply += "5. Other\n"

        self.state = State.AWAITING_REPORT_TYPE
        return [reply]
    
    def handleGetReportType(self, message):
        if message.content == "1":
            reply = "You selected Disinformation. We will be reporting this as disinformation. Thank you for your report.\n\n"
            reply += "If you would like to report something else, please say `report`.\n\n"
            reply += "To block this user, please go to their profile and click `Block User`.\n\n"
            reply += "To access the community standards, please say `community standards`.\n\n"

            self.state = State.REPORT_COMPLETE
            return [reply]
            
        elif message.content == "2":
            reply = "You selected Violence. Which type of violence? Please respond with a number.\n"
            reply += "1. Hate Speech\n"
            reply += "2. Terrorism and Extremism\n"
            reply += "3. Incitement to Violence\n"

            self.VIOLENCE_SUBTYPE_FLAG = True
            self.state = State.AWAITING_REPORT_SUBTYPE
            return [reply]
            
        elif message.content == "3":
            reply = "You selected Deceptive Content. Which type of deceptive content? Please respond with a number.\n\n"
            reply += "1. Illegal Sale\n"
            reply += "2. Fraud\n"
            reply += "3. Scam\n"

            self.DECEPETIVE_SUBTYPE_FLAG = True
            self.state = State.AWAITING_REPORT_SUBTYPE
            return [reply]
            
        elif message.content == "4":
            reply = "You selected Bullying and Unwanted Contact. Which type of unwanted content? Please respond with a number.\n\n"
            reply += "1. Coersion involving intimate content\n"
            reply += "2. Bullying\n"
            reply += "3. Stalking\n"
                
            self.BULLYING_AND_UNWANTED_SUBTYPE_FLAG = True
            self.state = State.AWAITING_REPORT_SUBTYPE
            return [reply]
        
        elif message.content == "5":
            reply = "You selected Other. Please provide details.\n\n"
            self.OTHER_TYPE_FLAG = True
            self.state = State.AWAITING_DETAILS
            return [reply]
        return []

    def handleGetReportSubtype(self, message):
        if self.VIOLENCE_SUBTYPE_FLAG:
            if message.content == "1":
                reply = "You selected Hate Speech. We will be reporting this as hate speech. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                return [reply]
            
            elif message.content == "2":
                reply = "You selected Terrorism and Extremism. We will be reporting this as Terrorism and Extremism. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                return [reply]
            
            elif message.content == "3":
                reply = "You selected Incitement to Violence. We will be reporting this as Incitement to Violence. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                return [reply]
            
        elif self.DECEPETIVE_SUBTYPE_FLAG:
            if message.content == "1":
                reply = "You selected Illegal Sale. We will be reporting this as Illegal Sale. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                return [reply]
            
            elif message.content == "2":
                reply = "You selected Fraud. We will be reporting this as Fraud. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                return [reply]
            
            elif message.content == "3":
                reply = "You selected Scam. We will be reporting this as Scam. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                return [reply]
        
        elif self.BULLYING_AND_UNWANTED_SUBTYPE_FLAG:
            if message.content == "1":
                reply = "You selected Coersion involving intimate content. We will be reporting this as Coersion involving intimate content.\n\n"
                reply += "We need to ask you a few more questions to help us understand the situation.\n\n"
                reply += "Are you under 18 years old? Please respond with 'yes' or 'no'.\n\n"
                self.state = State.CONTINUING_BULLYING_AND_UNWANTED_FLOW
                return [reply]
            
            elif message.content == "2":
                reply = "You selected Bullying. We will be reporting this as Bullying. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                return [reply]
            
            elif message.content == "3":
                reply = "You selected Stalking. We will be reporting this as Stalking. Thank you for your report.\n\n"
                reply += "If you would like to report something else, please say `report`.\n\n"
                reply += "To block this user, please go to their profile and click `Block User`.\n\n"
                reply += "To access the community standards, please say `community standards`.\n\n"
                self.state = State.REPORT_COMPLETE
                return [reply]
            return []
        return []
        
    def handleBullyingAndUnwantedFlow(self, message):
        if message.content.lower() == "yes":
            reply = "Thank you for your report. We will be reporting this as Coersion involving intimate content and the user is under 18.\n\n"
            reply += "Please provide more details about the case.\n\n"
            self.state = State.AWAITING_DETAILS
            return [reply]
            
        elif message.content.lower() == "no":
            reply = "Thank you for your report. We will be reporting this as Coersion involving intimate content and the user is 18 or older.\n\n"
            reply += "Please provide more details about the case.\n\n"
            self.state = State.AWAITING_DETAILS
            return [reply]
        return []

    def handleAwaitingDetails(self):
        reply = "Thank you for your report. You will recieve a notification as soon as we review your report.\n\n"
        reply += "To block this user, please go to their profile and click `Block User`.\n\n"
        reply += "To access the community standards, please say `community standards`.\n\n"
        reply += "If you would like to report something else, please say `report`.\n\n"
        self.state = State.REPORT_COMPLETE

        return [reply]
    
    

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE

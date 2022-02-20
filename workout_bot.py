import os
import json
import config
import logging

from telegram import User, Update, Chat, ChatMember, ParseMode, ChatMemberUpdated
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import CallbackContext
from telegram.ext import ChatMemberHandler

# Enable logging
logging.basicConfig(filename=config.LOG_FILEPATH, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkoutBot():
    def __init__(self):
        self.chatgroups = {}
        self.db = {}

        if os.stat(config.DB_FILEPATH).st_size != 0:
            with open(config.DB_FILEPATH) as f:
                self.db = json.load(f)

        self.updater = Updater(config.API_KEY)
        self.dp = self.updater.dispatcher

        # default welcome and help messages
        self.dp.add_handler(CommandHandler("start", self.welcome_message))
        self.dp.add_handler(CommandHandler("help", self.help_message))
        self.dp.add_handler(CommandHandler("show_updates", self.show_updates))

        # add handlers for workout command tags
        self.dp.add_handler(CommandHandler("join", self.process_join))
        self.dp.add_handler(CommandHandler("field", self.process_field_workout))
        self.dp.add_handler(CommandHandler("track", self.process_track_workout))
        self.dp.add_handler(CommandHandler("gym", self.process_gym_workout))
        self.dp.add_handler(CommandHandler("leaderboard", self.process_leaderboard))
        self.dp.add_error_handler(self.error_message)

        # Keep track of which chats the bot is in
        self.dp.add_handler(ChatMemberHandler(self.track_chats, ChatMemberHandler.MY_CHAT_MEMBER))

        # Handle members joining/leaving chats.
        self.dp.add_handler(ChatMemberHandler(self.greet_chat_members, ChatMemberHandler.CHAT_MEMBER))

        self.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        self.updater.idle()

    def saveDB(self):
        with open(config.DB_FILEPATH, 'w') as f:
            json.dump(self.db, f)

    def addNewChatGroup(self, chat_title, chat_id):
        # bot added into new chatgroup. create new entry in db
        if chat_title not in self.chatgroups.keys():
            self.chatgroups[chat_title] = chat_id
            self.db[chat_id] = {}
            self.saveDB()
            logger.info(f"Added new chatgroup: {chat_title} with ID: {chat_id} to database")
        else:
            logger.info(f"Failed to add chatgroup {chat_title} with ID {chat_id} to database as it already exists")

    def removedFromChatGroup(self, chat_title, chat_id):
        # bot removed from chatgroup. delete from db
        removed_value_db = self.db.pop(self.chatgroups[chat_title], False)
        removed_value_chatgroups = self.chatgroups.pop(chat_title, False)
        self.saveDB()
        logger.info(f"Removed {chat_title} with ID: {chat_id} from database")
        
        if (not removed_value_db):
            logger.info(f"Failed to remove {chat_title} from database as it does not exist")
        
        if (not removed_value_chatgroups):
            logger.info(f"Failed to remove {removed_value_chatgroups} from chatgroups as it does not exist")
        
    def addNewUserInGroup(self, chat_title, user_id):
        if chat_title in self.chatgroups.keys():
            if self.chatgroups[chat_title] in self.db:
                self.db[self.chatgroups[chat_title]][user_id] = 0
                self.saveDB()
                logger.info(f"Added {user_id} to database")
            else:
                logger.info(f"Failed to add {user_id} to database")
        else:
            logger.info(f"Failed to add {user_id} to database")

    def removeUserInGroup(self, chat_title, user_id):
        if chat_title in self.chatgroups.keys():
            if self.chatgroups[chat_title] in self.db:
                score = self.db[self.chatgroups[chat_title]].pop(user_id, 0)
                logger.info(f"Removed user ID: {user_id} from database, score: {score}")
            else:
                logger.info(f"Failed to remove {user_id} from database")
        else:
            logger.info(f"Failed to remove {user_id} from database")

    def updateUserInGroup(self, chat_title, user_id, points, update):
        if chat_title in self.chatgroups.keys():
            if self.chatgroups[chat_title] in self.db:
                if user_id in self.db[self.chatgroups[chat_title]]:
                    self.db[self.chatgroups[chat_title]][user_id] += update
                    points = self.db[self.chatgroups[chat_title]][user_id]
                    logger.info(f"Updated user ID: {user_id} from database, score: {points}")
                else:
                    logger.info(f"Failed to update {user_id} from database")
            else:
                logger.info(f"Failed to update {user_id} from database")
        else:
            logger.info(f"Failed to update {user_id} from database")

    """
    takes a ChatMemberUpdated instance and extracts whether the 'old_chat_member' was a member of the chat and whether 
    the 'new_chat_member' is a member of the chat. returns None, if the status didn't change
    """
    def extract_status_change(self, chat_member_update: ChatMemberUpdated):
    
        status_change = chat_member_update.difference().get("status")
        old_is_member, new_is_member = chat_member_update.difference().get("is_member", (None, None))

        if status_change is None:
            return None

        old_status, new_status = status_change
        was_member = (old_status in [ChatMember.MEMBER, ChatMember.CREATOR, ChatMember.ADMINISTRATOR]
            or (old_status == ChatMember.RESTRICTED and old_is_member is True))
        
        is_member = (new_status in [ChatMember.MEMBER, ChatMember.CREATOR, ChatMember.ADMINISTRATOR]
            or (new_status == ChatMember.RESTRICTED and new_is_member is True))

    """
    tracks the chats the bot is in and updates db
    """
    def track_chats(self, update: Update, context: CallbackContext):
        result = self.extract_status_change(update.my_chat_member)
        
        if result is None:
            return

        was_member, is_member = result
        cause_name = update.effective_user.full_name
        chat = update.effective_chat

        if chat.type == Chat.PRIVATE:
            if not was_member and is_member:
                logger.info("%s started the bot", cause_name)
            elif was_member and not is_member:
                logger.info("%s blocked the bot", cause_name)
        elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            if not was_member and is_member:
                logger.info("%s added the bot to the group %s", cause_name, chat.title)
                self.addNewChatGroup(chat.title, chat.id)
                update.effective_chat.send_message(
                    "Hello there! Thanks for adding me in. To register yourself in the workout challenge, please use the command: /join\n"
                    "For more information on how to use me, use the command: /help\n"
                    "Thank you and have a nice day!")
            elif was_member and not is_member:
                logger.info("%s removed the bot from the group %s", cause_name, chat.title)
                self.removedFromChatGroup(chat.title, chat.id)

    """
    shows bot status - which chats it is inside currently and the user IDs from the current db
    """
    def show_updates(self, update: Update, context: CallbackContext):
        msg = ""        
        for key in self.db:
            msg += f"Bot is currently in the group with ID: {self.db[key]} with a total of {len(self.db[key])} users!\n"
            for user in self.db[key]:
                msg += f"User id: {user} has {self.db[key[user]]} points\n"

        update.message.reply_text(msg)


    """
    Greets new users in chats and announces when someone leaves
    """
    def greet_chat_members(self, update: Update, context: CallbackContext):
        result = self.extract_status_change(update.chat_member)
        if result is None:
            return
        
        was_member, is_member = result
        cause_name = update.chat_member.from_user.mention_html()
        member_name = update.chat_member.new_chat_member.user.mention_html()
        chat = update.effective_chat

        if not was_member and is_member:
            update.effective_chat.send_message(f"{member_name} was added by {cause_name}. Welcome! "
                "To register yourself in the workout challenge, please use the command: /join\n"
                "For more information on how to use me, use the command: /help\n", parse_mode=ParseMode.HTML)
        elif was_member and not is_member:
            update.effective_chat.send_message(f"{member_name} is no longer with us. Thanks a lot, {cause_name}...", parse_mode=ParseMode.HTML)

    """
    introduction message when bot /start
    """
    def welcome_message(self, update: Update, context: CallbackContext):
        update.message.reply_text(
            f"Hello {update.effective_user.username}, I am a bot that aims to provide a platform to facilitate your team to track your team workouts!")

    """
    Error message handler
    """
    def error_message(self, update: Update, context: CallbackContext):
        print(f"Update {update} caused error {context.error}")

    """
    help instructions when bot /help
    """
    def help_message(self, update: Update, context: CallbackContext):
        update.message.reply_text(
            "To join the challenge, use the '/join' command! "
            "Once you have joined, to register a workout, simply upload a workout selfie after your workout with the specific command tag at the start of your post.\n\n"
            "There are 3 categories of workout you may clock: \n"
            "1. FIELD workout (worth 5 points, /field) \n"
            "2. TRACK workout (worth 2 points, /track) \n"
            "3. GYM workout (worth 1 points, /gym)\n\n"
            "If done correctly, your workout will be registered! Note that putting in multiple tags will not be useful for me as I will only process the first one!\n\n"
            "Also to check the current leaderboard, simple use the '/leaderboard' command! /n/n"
            "Good luck and may the fittest win!\n\n"
            "(Also please do have patience with me! I am also still in dev phase so please do pardon me if I am buggy)")

    """
    join command to insert user into the database
    """
    def process_join(self, update: Update, context: CallbackContext):
        logger.info("Received request to join challenge.")
        user_id = update.effective_user.id
        chat = update.effective_chat
        self.addNewUserInGroup(chat.title, user_id)

        update.message.reply_text(
            f"{update.effective_user.username}, you have successfully registered in the workout challenge! Keep werking!")

    """
    process field workout command update user's points
    """
    def process_field_workout(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        chat = update.effective_chat
        points = 0
        self.updateUserInGroup(chat.title, user_id, points , 5)
        update.message.reply_text(
            f"{update.effective_user.username}, good job on completing a field workout! Your current points is at: {points}. Keep werking!")

    """
    process track workout command update user's points
    """
    def process_track_workout(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        chat = update.effective_chat
        points = 0
        self.updateUserInGroup(chat.title, user_id, points , 2)
        update.message.reply_text(
            f"{update.effective_user.username}, good job on completing a track workout! Your current points is at: {points}. Keep werking!")

    """
    process gym workout command update user's points
    """
    def process_gym_workout(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        chat = update.effective_chat
        points = 0
        self.updateUserInGroup(chat.title, user_id, points , 1)
        update.message.reply_text(
            f"{update.effective_user.username}, good job on completing a gym workout! Your current points is at: {points}. Keep werking!")

    def process_leaderboard(self, Update, context: CallbackContext):
        return


print("Workout bot started!")
WorkoutBot()
import os
import json
import config
import logging
from datetime import datetime, timedelta

from telegram import User, Update, Chat, ChatMember, ParseMode, ChatMemberUpdated
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import CallbackContext
from telegram.ext import ChatMemberHandler

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkoutBot():
    def __init__(self):
        self.db = {}
        self.chatgroups = {}

        if os.stat(config.CHAT_FILEPATH).st_size != 0:
            with open(config.CHAT_FILEPATH) as f:
                self.chatgroups = json.load(f)

        if os.stat(config.DB_FILEPATH).st_size != 0:
            with open(config.DB_FILEPATH) as f:
                self.db = json.load(f)

    def saveDB(self):
        db_output = json.dumps(self.db, indent = 4)
        with open(config.DB_FILEPATH, 'w') as f:
            f.write(db_output)

        chat_output = json.dumps(self.chatgroups, indent = 4)
        with open(config.CHAT_FILEPATH, 'w') as f:
            f.write(chat_output)

    def add_new_chat_group(self, chat_title, chat_id):
        # bot added into new chatgroup. create new entry in db
        if chat_title not in self.chatgroups.keys():
            self.chatgroups[chat_title] = chat_id
            self.db[chat_id] = {}
            self.saveDB()
            logger.info(f"Added new chatgroup: {chat_title} with ID: {chat_id} to database")
            return True
        else:
            logger.info(f"Failed to add chatgroup {chat_title} with ID {chat_id} to database as it already exists")
            return False

    def removed_from_chat_group(self, chat_title, chat_id):
        # bot removed from chatgroup. delete from db
        removed_value_db = self.db.pop(self.chatgroups[chat_title], False)
        removed_value_chatgroups = self.chatgroups.pop(chat_title, False)
        self.saveDB()
        logger.info(f"Removed {chat_title} with ID: {chat_id} from database")
        
        if (not removed_value_db):
            logger.info(f"Failed to remove {chat_title} from database as it does not exist")
        
        if (not removed_value_chatgroups):
            logger.info(f"Failed to remove {removed_value_chatgroups} from chatgroups as it does not exist")
    
    def check_group_registered(self, chat_title):
        if chat_title in self.chatgroups.keys():
            return True
        else:
            return False

    def check_user_registered(self, chat_title, user_id):
        if self.chatgroups[chat_title] in self.db:
            if user_id in self.db[self.chatgroups[chat_title]]:
                return True
            else:
                return False
        else:
            return False
   
    def add_new_user_in_group(self, chat_title, user_id, name):
        if self.chatgroups[chat_title] in self.db:
            self.db[self.chatgroups[chat_title]][user_id] = [name, 0, self.convert_datetime_to_string(datetime.now() - timedelta(days=1))]
            self.saveDB()
            logger.info(f"Added {user_id} to database")
            return True
        else:
            logger.info(f"Failed to add {user_id} to database")
            return False

    def remove_user_in_group(self, chat_title, user_id):
        if chat_title in self.chatgroups.keys():
            if self.chatgroups[chat_title] in self.db:
                entry = self.db[self.chatgroups[chat_title]].pop(user_id, [0 , 0, 0])
                self.saveDB()
                logger.info(f"Removed user ID: {user_id} from database, score: {entry[1]}")
            else:
                logger.info(f"Failed to remove {user_id} from database")
        else:
            logger.info(f"Failed to remove {user_id} from database")

    def update_user_in_group(self, chat_title, user_id, update):
        if self.chatgroups[chat_title] in self.db:
            if user_id in self.db[self.chatgroups[chat_title]]:
                self.db[self.chatgroups[chat_title]][user_id][1] += update
                self.db[self.chatgroups[chat_title]][user_id][2] = self.convert_datetime_to_string(datetime.now())
                self.saveDB()
                logger.info(f"Updated user ID: {user_id} from database, score: {self.db[self.chatgroups[chat_title]][user_id][1]}")
                return True
            else:
                logger.info(f"Failed to update {user_id} from database")
                return False
        else:
            logger.info(f"Failed to update {user_id} from database")

    """
    method should only be called if checks to ensure chatgroup and user exist in db
    """
    def check_last_update_time(self, chat_title, user_id):
        last_entry_time = self.convert_datetime_from_string(self.db[self.chatgroups[chat_title]][user_id][2])
        duration = datetime.now() - last_entry_time
        total_seconds = duration.total_seconds()
        minutes = total_seconds / 60
        
        if (minutes < 60):
            return False
        else:
            return True

    def convert_datetime_from_string(self, date_time_str):
        date_time = datetime.strptime(date_time_str, '%b %d %Y %I:%M%p')
        return date_time

    def convert_datetime_to_string(self, date_time):
        date_time_str = date_time.strftime('%b %d %Y %I:%M%p')
        return date_time_str

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
        chat_id = str(chat.id)
        chat_title = str(chat.title)

        if chat.type == Chat.PRIVATE:
            if not was_member and is_member:
                logger.info("%s started the bot", cause_name)
                context.bot_data.setdefault("user_ids", set()).add(chat_id)
            elif was_member and not is_member:
                logger.info("%s blocked the bot", cause_name)
                context.bot_data.setdefault("user_ids", set()).discard(chat_id)
        elif chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            if not was_member and is_member:
                logger.info("%s added the bot to the group %s", cause_name, chat_title)
                context.bot_data.setdefault("group_ids", set()).add(chat_id)
                self.add_new_chat_group(chat_title, chat_id)
                update.effective_chat.send_message(
                    "Hello there! Thanks for adding me in. To register yourself in the workout challenge, please use the command: /join\n"
                    "For more information on how to use me, use the command: /help\n"
                    "Thank you and have a nice day!")
            elif was_member and not is_member:
                logger.info("%s removed the bot from the group %s", cause_name, chat_title)
                context.bot_data.setdefault("group_ids", set()).discard(chat_id)
                self.removed_from_chat_group(chat_title, chat_id)

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
            f"Hello {update.effective_user.first_name}, I am a bot that aims to provide a platform to help track your team's workouts!")

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
            "To use me to track your team's workout, add me into your workout group chat and use the '/register_team' command!\n\n"
            "To join the challenge, use the '/join' command! "
            "Once you have joined, you may start registering your workouts. "
            "Simply upload a workout selfie after your workout with the specific command tag at the start of your post.\n\n"
            "There are 3 categories of workout you may clock: \n"
            "1. FIELD workout (worth 5 points, '/field') \n"
            "2. TRACK workout (worth 2 points, '/track') \n"
            "3. GYM workout (worth 1 points, '/gym')\n\n"
            "If done correctly, your workout will be registered! "
            "Note that putting in multiple tags will not be useful for me as I will only process the first one.\n\n"
            "Also to check the current leaderboard, simple use the '/leaderboard' command! \n\n"
            "Good luck and may the fittest win!\n\n"
            "(Also please do have patience with me! I am also still in dev phase so please do pardon me if I am buggy)")

    def process_register_team(self, update: Update, context: CallbackContext):
        chat = update.effective_chat
        chat_id = str(chat.id)
        chat_title = str(chat.title)
        username = update.effective_user.username
        logger.info(f"Received request from {username} to start tracking chatgroup's {chat_title} workouts.")

        if (not self.check_group_registered(chat_title)):
            self.add_new_chat_group(chat_title, chat_id)
            update.effective_chat.send_message(
                "Hello there! Thanks for using me to track your team's workouts! Your team has been successfully registered.\n\n"
                "To start using me, all competitors may kindly register yourself in the workout challenge, by using the command: '/join'\n\n"
                "For more information on how to use me, use the command: '/help'\n\n"
                "Thank you and have a nice day!")
        else:
            update.effective_chat.send_message(
                f"{update.effective_user.first_name}, I am already tracking your team's workouts!")

    """
    join command to insert user into the database
    """
    def process_join(self, update: Update, context: CallbackContext):
        chat = update.effective_chat
        chat_title = str(chat.title)
        user_id = str(update.effective_user.id)
        name = update.effective_user.first_name
        username = update.effective_user.username
        logger.info(f"Received request from {username} to join challenge.")

        if (self.check_group_registered(chat_title)):
            if (not self.check_user_registered(chat_title, user_id)):
                success = self.add_new_user_in_group(chat_title, user_id, name)
                if (success):
                    update.message.reply_text(
                        f"{update.effective_user.first_name}, you have successfully registered in the workout challenge! Keep werking!")
                else:
                    update.message.reply_text(
                        f"{update.effective_user.first_name}, you are already registered in the workout challenge!")
            else:
                update.message.reply_text(
                    f"{update.effective_user.first_name}, you are already registered in the workout challenge!")
        else:
            update.message.reply_text(
                f"{update.effective_user.first_name}, you have to register your team in the workout challenge first!")

    """
    process field workout command update user's points
    """
    def process_field_workout(self, update: Update, context: CallbackContext):
        chat = update.effective_chat
        chat_title = str(chat.title)
        user_id = str(update.effective_user.id)
        name = update.effective_user.first_name
        username = update.effective_user.username
        logger.info(f"Received request from {username} to process field workout.")

        if (self.check_group_registered(chat_title)):
            if (self.check_user_registered(chat_title, user_id)):
                if (self.check_last_update_time(chat_title, user_id)):
                    self.update_user_in_group(chat_title, user_id, 5)
                    update.message.reply_text(
                        f"{name}, good job on completing a field workout! Your current points is at {self.db[self.chatgroups[chat.title]][user_id][1]}. Keep werking!")
                else:
                    update.message.reply_text(
                        f"{name}, I cannot accept your field workout entry because your last logged workout was less than an hour ago. Please try me again in abit!")
            else:
                update.message.reply_text(
                    f"{name}, you have to register yourself in the workout challenge first!")
        else:
            update.message.reply_text(
                f"{name}, you have to register your team in the workout challenge first!")

    """
    process track workout command update user's points
    """
    def process_track_workout(self, update: Update, context: CallbackContext):
        chat = update.effective_chat
        chat_title = str(chat.title)
        user_id = str(update.effective_user.id)
        name = update.effective_user.first_name
        username = update.effective_user.username
        logger.info(f"Received request from {username} to process track workout.")

        if (self.check_group_registered(chat_title)):
            if (self.check_user_registered(chat_title, user_id)):
                if (self.check_last_update_time(chat_title, user_id)):
                    self.update_user_in_group(chat_title, user_id, 2)
                    update.message.reply_text(
                        f"{name}, good job on completing a track workout! Your current points is at {self.db[self.chatgroups[chat.title]][user_id][1]}. Keep werking!")
                else:
                    update.message.reply_text(
                        f"{name}, I cannot accept your track workout entry because your last logged workout was less than an hour ago. Please try me again in abit!")
            else:
                update.message.reply_text(
                    f"{name}, you have to register yourself in the workout challenge first!")
        else:
            update.message.reply_text(
                f"{name}, you have to register your team in the workout challenge first!")

    """
    process gym workout command update user's points
    """
    def process_gym_workout(self, update: Update, context: CallbackContext):
        chat = update.effective_chat
        chat_title = str(chat.title)
        user_id = str(update.effective_user.id)
        name = update.effective_user.first_name
        username = update.effective_user.username
        logger.info(f"Received request from {username} to process gym workout.")

        if (self.check_group_registered(chat_title)):
            if (self.check_user_registered(chat_title, user_id)):
                if (self.check_last_update_time(chat_title, user_id)):
                    self.update_user_in_group(chat_title, user_id, 1)
                    update.message.reply_text(
                        f"{name}, good job on completing a gym workout! Your current points is at {self.db[self.chatgroups[chat_title]][user_id][1]}. Keep werking!")
                else:
                    update.message.reply_text(
                        f"{name}, I cannot accept your gym workout entry because your last logged workout was less than an hour ago. Please try me again in abit!")
            else:
                update.message.reply_text(
                    f"{name}, you have to register yourself in the workout challenge first!")
        else:
            update.message.reply_text(
                f"{name}, you have to register your team in the workout challenge first!")

    def process_leaderboard(self, update: Update, context: CallbackContext):
        chat = update.effective_chat
        chat_title = str(chat.title)
        index = 1
        username = update.effective_user.username
        logger.info(f"Received request from {username} to get current leaderboard.")
        msg = "Current leaderboard: \n"
        temp_list = []

        if (self.check_group_registered(chat_title)):
            if self.chatgroups[chat_title] in self.db:
                for user in self.db[self.chatgroups[chat_title]]:
                    points = self.db[self.chatgroups[chat_title]][user][1]
                    temp_list.append((user, points))

                ordered_list = sorted(temp_list, key=lambda x :(-x[1], x[0]))
                
                for element in ordered_list:
                    msg += f"{index}. {self.db[self.chatgroups[chat_title]][element[0]][0]} - {element[1]} points\n"
                    index += 1
                
                update.message.reply_text(msg)

print("Workout bot started!")
workout_bot = WorkoutBot()

updater = Updater(config.API_KEY)
dp = updater.dispatcher

# default welcome and help messages
dp.add_handler(CommandHandler("start", workout_bot.welcome_message))
dp.add_handler(CommandHandler("help", workout_bot.help_message))
dp.add_error_handler(workout_bot.error_message)

# add handlers for workout command tags
dp.add_handler(CommandHandler("join", workout_bot.process_join))
dp.add_handler(CommandHandler("field", workout_bot.process_field_workout))
dp.add_handler(CommandHandler("track", workout_bot.process_track_workout))
dp.add_handler(CommandHandler("gym", workout_bot.process_gym_workout))
dp.add_handler(CommandHandler("leaderboard", workout_bot.process_leaderboard))
dp.add_handler(CommandHandler("register_team", workout_bot.process_register_team))

# Keep track of which chats the bot is in
# dp.add_handler(ChatMemberHandler(workout_bot.track_chats, ChatMemberHandler.MY_CHAT_MEMBER))

# Handle members joining/leaving chats.
# dp.add_handler(ChatMemberHandler(workout_bot.greet_chat_members, ChatMemberHandler.CHAT_MEMBER))

updater.start_polling(allowed_updates=Update.ALL_TYPES)
updater.idle()
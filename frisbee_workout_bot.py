import config
from telegram.ext import *

# method to introduce bot
def welcome_message(update, context):
    msg = "Hello there, I am a bot that aims to provide a platform to facilitate your team to track your team workouts!"
    update.message.reply_text(msg)

def error(update, context):
    print(f"Update {update} caused error {context.error}")

def help_message(update, context):
    msg = " Tired of working out by yourself? Or do you want to flaunt your heavy lifts to your teammates? Or more importantly, \
does your team want to encourage each other to work out more? Then I am just for you and your team's needs! \n\nTo use me, simply \
upload a photo of your workout, with a tag (!gym / !field / !track). My job here is to ensure that no cheating happens, and I will \
tabulate your scores for every workout selfie you send! At the end of every month, the winner will be proudly announced! There are \
3 kinds of workout you may clock: \n1. FIELD workout (worth 3 points, !field) \n2. TRACK workout (worth 2 points, !track) \n3. GYM \
workout (worth 1 points, !gym)\n\n Good luck and may the fittest win!\n\n\
(I am also still in dev phase so please do pardon me if I am still buggy)"

    update.message.reply_text(msg)

def identify_tag(incoming_msg):
    tags = ["!field", "!track", "!gym"]
    msg = str(incoming_msg).lower()

    appearance = {}
    for i, tag in enumerate(tags):
        if tag in msg:
            idx = msg.index(tag)
            appearance[i] = idx
    
    if (len(appearance) == 1):
        

def main():
    print("Frisbee workout bot started!")

    updater = Updater(config.API_KEY, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", welcome_message))
    dp.add_handler(CommandHandler("help", help_message))
    dp.add_error_handler(error)

    updater.start_polling()
    updater.idle()

main()
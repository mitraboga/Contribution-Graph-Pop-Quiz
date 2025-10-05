import os
from telegram import Bot

# If you already have a function that builds the daily text, import it:
# from contributions import build_daily_message
def build_daily_message():
    # Replace with your real builder
    return "🎯 Daily Commit Reminder: Keep the streak alive!"

def run():
    bot = Bot(os.environ["BOT_TOKEN"])
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    bot.send_message(chat_id=chat_id, text=build_daily_message())

if __name__ == "__main__":
    run()

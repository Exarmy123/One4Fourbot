import os
import telebot

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    bot.reply_to(message, f"👋 नमस्ते {user.first_name}! Welcome to One4FourBit Game Bot!")

if __name__ == "__main__":
    print("Bot is starting...")
    bot.infinity_polling()

# Placeholder for config.py
import os
import telebot

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    bot.reply_to(message, f"👋 नमस्ते {user.first_name}!\n\n🎰 Welcome to One4FourBit Game Bot!\n\nआप 1 USDT से गेम खेल सकते हैं और जीतने का मौका पा सकते हैं!\n\n💸 Invite friends & earn commission.\n🎯 हर 6 यूज़र में 1 जीतता है!\n\n👉 /help टाइप करें पूरी जानकारी के लिए।")

@bot.message_handler(commands=['help'])
def help_message(message):
    help_text = """
ℹ️ *One4FourBit Game Help*

🎮 Game Rules:
- हर गेम में 6 यूज़र भाग लेते हैं।
- 1 USDT में हिस्सा लें।
- एक विनर को 4 USDT मिलता है।

💰 Referral System:
- अपने referral लिंक से यूज़र जोड़ें।
- जब वो deposit करें या गेम खेलें, तो आपको 10% USDT मिलेगा।

🔐 Secure System:
- Auto payout system.
- Daily motivational messages.

🚀 Commands:
- /start – गेम शुरू करें
- /help – सहायता देखें

धन्यवाद! 🙏
"""
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

print("✅ Bot is running...")
bot.polling()

import os
import telebot

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# In-memory user data (replace with real DB in production)
users = {}
tickets = {}
referrals = {}

def calculate_commission(tickets_bought):
    # Referral commission eligibility: user must buy at least 2 tickets
    return tickets_bought >= 2

@bot.message_handler(commands=['start'])
def send_welcome(message):
    first_name = message.from_user.first_name
    user_id = message.from_user.id
    
    # Register user if new
    if user_id not in users:
        users[user_id] = {'first_name': first_name, 'tickets': 0, 'referrer': None, 'commission_earned': 0}
    
    welcome_text = f"""👋 Hello {first_name}!

🎰 Welcome to One4FourBit Game Bot!

You can play the game with just 1 USDT and stand a chance to win!

💸 Invite friends & earn commission.

🎯 1 in every 6 players wins!

👉 Type /help for more information.
"""
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def help_message(message):
    help_text = """
ℹ️ *One4FourBit Game Help*

- /buy_ticket : Buy a game ticket (1 USDT each)
- /my_tickets : Check how many tickets you have
- /referral : Get your referral link
- /balance : Check your commission balance
- Invite friends with your referral link and earn 10% commission on their tickets (minimum 2 tickets to get commission).

Good luck and have fun!
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['buy_ticket'])
def buy_ticket(message):
    user_id = message.from_user.id
    user = users.get(user_id)
    if not user:
        bot.reply_to(message, "Please /start first to register.")
        return
    
    user['tickets'] += 1
    bot.reply_to(message, f"🎟️ You bought ticket #{user['tickets']}! Good luck!")
    
    # Handle referral commission
    referrer_id = user['referrer']
    if referrer_id and calculate_commission(user['tickets']):
        commission = 0.1  # 10% commission per ticket price (assumed 1 USDT)
        if referrer_id in users:
            users[referrer_id]['commission_earned'] += commission
            bot.send_message(referrer_id, f"💰 You earned 0.1 USDT commission from your referral {user['first_name']} buying a ticket!")

@bot.message_handler(commands=['my_tickets'])
def my_tickets(message):
    user_id = message.from_user.id
    user = users.get(user_id)
    if not user:
        bot.reply_to(message, "Please /start first to register.")
        return
    
    bot.reply_to(message, f"🎟️ You currently have {user['tickets']} tickets.")

@bot.message_handler(commands=['referral'])
def referral(message):
    user_id = message.from_user.id
    ref_link = f"https://t.me/YourBotUsername?start={user_id}"
    bot.reply_to(message, f"🔗 Your referral link:\n{ref_link}\nShare it to earn commissions!")

@bot.message_handler(commands=['balance'])
def balance(message):
    user_id = message.from_user.id
    user = users.get(user_id)
    if not user:
        bot.reply_to(message, "Please /start first to register.")
        return
    
    bot.reply_to(message, f"💰 Your commission balance: {user['commission_earned']} USDT")

@bot.message_handler(commands=['start'])
def handle_start(message):
    # To capture referral parameter
    args = message.text.split()
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    if user_id not in users:
        users[user_id] = {'first_name': first_name, 'tickets': 0, 'referrer': None, 'commission_earned': 0}
    
    if len(args) > 1:
        referrer_id = int(args[1])
        if referrer_id != user_id and users.get(referrer_id):
            users[user_id]['referrer'] = referrer_id
    
    send_welcome(message)

if __name__ == '__main__':
    print("Bot is starting...")
    bot.infinity_polling()

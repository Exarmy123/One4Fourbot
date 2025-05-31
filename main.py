import os
import telebot
from supabase import create_client, Client
from datetime import datetime
import uuid

# Environment Variables
BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Fetch your bot’s real username once
BOT_USERNAME = bot.get_me().username  # e.g. "One4FourBitBot"

# Minimum tickets required to earn referral commission
MIN_TICKETS_FOR_COMMISSION = 2

# —————————————————————————————— HELPERS —————————————————————————————— #

def get_user(user_id: int):
    """Return a single user record or None."""
    resp = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return resp.data[0] if resp.data else None

def create_user(user_id: int, first_name: str, username: str, referred_by: int = None):
    """Insert a new user into Supabase."""
    data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "first_name": first_name,
        "username": username,
        "ref_by": referred_by,
        "tickets": 0,
        "wallet": None,
        "created_at": str(datetime.utcnow())
    }
    supabase.table("users").insert(data).execute()
    return get_user(user_id)

def increase_ticket(user_id: int) -> int:
    """Increment this user’s ticket count by 1 and return the new count."""
    user = get_user(user_id)
    new_count = user["tickets"] + 1
    supabase.table("users").update({"tickets": new_count}).eq("user_id", user_id).execute()
    return new_count

def pay_referral_if_eligible(user_id: int):
    """
    If this user has a valid referrer and has now bought at least MIN_TICKETS_FOR_COMMISSION,
    record a commission for the referrer.
    """
    user = get_user(user_id)
    ref_by = user["ref_by"]
    tickets_bought = user["tickets"]
    # Only pay once per user – we check if tickets_bought just reached the threshold
    if ref_by and tickets_bought == MIN_TICKETS_FOR_COMMISSION:
        commission_amount = 0.10  # 10% of the 1 USDT ticket price
        # Insert into a referrals table for record-keeping
        supabase.table("referrals").insert({
            "id": str(uuid.uuid4()),
            "referrer_id": ref_by,
            "referred_id": user_id,
            "amount": commission_amount,
            "created_at": str(datetime.utcnow())
        }).execute()
        # (Future) You could auto-payout to the referrer’s stored wallet here
        return commission_amount
    return 0.0

# —————————————————————————————— COMMAND HANDLERS —————————————————————————————— #

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id    = message.from_user.id
    first_name = message.from_user.first_name
    username   = message.from_user.username or ""
    parts = message.text.strip().split()
    
    # Check if referred_by code is provided: /start <referrer_telegram_id>
    referred_by = None
    if len(parts) == 2 and parts[1].isdigit() and int(parts[1]) != user_id:
        # Only set if that referrer actually exists in users table
        possible_ref = get_user(int(parts[1]))
        if possible_ref:
            referred_by = int(parts[1])
    
    existing = get_user(user_id)
    if not existing:
        # Create new user with optional referrer
        create_user(user_id, first_name, username, referred_by)
    
    welcome_text = (
        f"👋 Hello {first_name}!\n\n"
        "🎰 Welcome to One4FourBit Game Bot!\n\n"
        "1️⃣ Buy ticket (1 USDT)\n"
        "2️⃣ Win up to 5x reward daily!\n"
        "3️⃣ Refer & earn *10% lifetime commission* (after 2 tickets).\n\n"
        f"🔗 Your referral link:\n"
        f"https://t.me/{BOT_USERNAME}?start={user_id}\n\n"
        "💰 Use /buy_ticket to purchase a ticket\n"
        "💼 Use /wallet to set your TRC20 address\n"
        "🎯 Use /referral to check your earnings\n"
        "/help for more info."
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_handler(message):
    help_text = (
        "ℹ️ *One4FourBit Game Help*\n\n"
        "- /buy_ticket : Buy a game ticket (1 USDT each)\n"
        "- /my_tickets : Check how many tickets you have\n"
        "- /referral : Get your referral link\n"
        "- /balance : Check your commission balance\n\n"
        "Invite friends with your referral link and earn 10% commission on their tickets (requires them to buy at least 2 tickets).\n\n"
        "Good luck and have fun!"
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['buy_ticket'])
def buy_ticket_handler(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        bot.reply_to(message, "Please /start first to register.")
        return
    
    # Increase ticket count
    new_count = increase_ticket(user_id)
    bot.reply_to(message, f"🎟️ You just bought ticket #{new_count}! Good luck!")

    # Pay referral commission if the referred user just hit the threshold
    commission_paid = pay_referral_if_eligible(user_id)
    if commission_paid > 0:
        referrer_id = user["ref_by"]
        if referrer_id:
            bot.send_message(
                referrer_id,
                f"💰 You earned {commission_paid:.2f} USDT commission "
                f"because your referral {user['first_name']} just reached 2 tickets!"
            )

@bot.message_handler(commands=['my_tickets'])
def my_tickets_handler(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        bot.reply_to(message, "Please /start first to register.")
        return
    bot.reply_to(message, f"🎟️ You currently have {user['tickets']} tickets.")

@bot.message_handler(commands=['referral'])
def referral_handler(message):
    user_id = message.from_user.id
    bot.reply_to(
        message,
        f"🔗 Your referral link:\n"
        f"https://t.me/{BOT_USERNAME}?start={user_id}\n\n"
        "Share it to earn commissions when friends buy 2 or more tickets!"
    )

@bot.message_handler(commands=['balance'])
def balance_handler(message):
    user_id = message.from_user.id
    # Sum up all commission records for this user
    resp = supabase.table("referrals").select("amount").eq("referrer_id", user_id).execute()
    total_comm = sum(item["amount"] for item in resp.data) if resp.data else 0.0
    bot.reply_to(message, f"💰 Your commission balance: {total_comm:.2f} USDT")

@bot.message_handler(commands=['wallet'])
def wallet_handler(message):
    msg = bot.reply_to(message, "💼 Please send your TRC20 USDT wallet address:")
    bot.register_next_step_handler(msg, save_wallet_handler)

def save_wallet_handler(message):
    wallet_addr = message.text.strip()
    user_id = message.from_user.id
    # A rudimentary check: Tron addresses start with 'T' and are ~34–35 chars
    if wallet_addr.startswith("T") and 34 <= len(wallet_addr) <= 35:
        supabase.table("users").update({"wallet": wallet_addr}).eq("user_id", user_id).execute()
        bot.reply_to(message, "✅ Your TRC20 wallet address has been saved.")
    else:
        bot.reply_to(message, "❌ That doesn’t look like a valid TRC20 address. Try again with /wallet.")

@bot.message_handler(commands=['winners'])
def winners_handler(message):
    bot.reply_to(message, "🏆 Past winners list coming soon!")

# —————————————————————————————— MAIN —————————————————————————————— #
if __name__ == '__main__':
    print("🤖 Bot is starting...")
    bot.infinity_polling()

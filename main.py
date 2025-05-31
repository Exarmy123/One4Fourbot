import os
import telebot
from supabase import create_client, Client
from datetime import datetime
import uuid

# Environment Variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

bot = telebot.TeleBot(BOT_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Minimum tickets to be eligible for referral commission
MIN_TICKETS_FOR_COMMISSION = 2

# ----- START COMMAND -----
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username or ""
    ref_code = str(message.text).split(" ")[-1] if len(message.text.split(" ")) > 1 else None

    existing = supabase.table("users").select("id").eq("user_id", user_id).execute().data
    if not existing:
        supabase.table("users").insert({
            "user_id": user_id,
            "first_name": first_name,
            "username": username,
            "ref_by": ref_code if ref_code != str(user_id) else None,
            "tickets": 0,
            "wallet": None,
            "created_at": str(datetime.utcnow())
        }).execute()

    bot.reply_to(message, f"👋 नमस्ते {first_name}!

🎰 Welcome to *TrustWin Lottery Bot*!\n\n1️⃣ Buy ticket (1 USDT)\n2️⃣ Win up to 5x reward daily!\n3️⃣ Refer & earn *10% lifetime commission* (after 2 tickets).\n\n🔗 Your referral link:\nhttps://t.me/{bot.get_me().username}?start={user_id}\n\n💰 Use /buy to purchase ticket\n💼 Use /wallet to set TRC20 address\n🎯 Use /refer to check your earnings\n/help for more info.", parse_mode="Markdown")

# ----- HELP COMMAND -----
@bot.message_handler(commands=['help'])
def help_msg(message):
    bot.reply_to(message, """
📜 *TrustWin Help Guide*

🎟️ /buy - Buy 1 ticket (1 USDT)
💼 /wallet - Set your TRC20 address
💰 /refer - View referral earnings
🏆 /winners - View past winners
🧾 /balance - View your ticket balance

🔗 Referral link will appear after /start
Earn 10% lifetime commission after 2 tickets
""", parse_mode="Markdown")

# ----- BUY TICKET (Mock Function) -----
@bot.message_handler(commands=['buy'])
def buy_ticket(message):
    user_id = message.from_user.id
    user = supabase.table("users").select("tickets", "ref_by").eq("user_id", user_id).execute().data
    if not user:
        bot.reply_to(message, "कृपया पहले /start से रजिस्टर करें।")
        return

    # Increase ticket count
    current = user[0]["tickets"]
    supabase.table("users").update({"tickets": current + 1}).eq("user_id", user_id).execute()
    bot.reply_to(message, "🎟️ 1 टिकट खरीदा गया। धन्यवाद!")

    # Pay referral commission if eligible
    ref_by = user[0]["ref_by"]
    if ref_by:
        ref_user = supabase.table("users").select("tickets").eq("user_id", ref_by).execute().data
        if ref_user and ref_user[0]["tickets"] >= MIN_TICKETS_FOR_COMMISSION:
            supabase.table("referrals").insert({
                "referrer_id": ref_by,
                "referred_id": user_id,
                "amount": 0.1,
                "created_at": str(datetime.utcnow())
            }).execute()
            # TODO: Auto payout to wallet in future

# ----- SET WALLET -----
@bot.message_handler(commands=['wallet'])
def set_wallet(message):
    msg = bot.reply_to(message, "आपका TRC20 USDT वॉलेट ऐड्रेस भेजें:")
    bot.register_next_step_handler(msg, save_wallet)

def save_wallet(message):
    wallet = message.text.strip()
    user_id = message.from_user.id
    if wallet.startswith("T") and len(wallet) >= 30:
        supabase.table("users").update({"wallet": wallet}).eq("user_id", user_id).execute()
        bot.reply_to(message, "✅ वॉलेट ऐड्रेस सेव हो गया।")
    else:
        bot.reply_to(message, "❌ सही TRC20 ऐड्रेस भेजें।")

# ----- REFERRAL INFO -----
@bot.message_handler(commands=['refer'])
def refer_info(message):
    user_id = message.from_user.id
    data = supabase.table("referrals").select("amount").eq("referrer_id", user_id).execute().data
    total = sum([x['amount'] for x in data]) if data else 0
    bot.reply_to(message, f"💰 अब तक की कमाई: {total:.2f} USDT")

# ----- WINNER PLACEHOLDER -----
@bot.message_handler(commands=['winners'])
def winners(message):
    bot.reply_to(message, "🏆 पिछले विजेताओं की सूची जल्द आ रही है!")

# ----- BALANCE -----
@bot.message_handler(commands=['balance'])
def balance(message):
    user_id = message.from_user.id
    data = supabase.table("users").select("tickets").eq("user_id", user_id).execute().data
    if data:
        bot.reply_to(message, f"🎟️ आपके पास {data[0]['tickets']} टिकट हैं।")
    else:
        bot.reply_to(message, "⚠️ कोई डेटा नहीं मिला।")

# ----- POLLING -----
if __name__ == '__main__':
    print("🤖 Bot is starting...")
    bot.infinity_polling()

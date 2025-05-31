# One4FourBit Telegram Lottery Bot - Final Version

import os
import asyncio
import random
import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from supabase import create_client
from tronpy import Tron
from tronpy.keys import PrivateKey

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
USDT_ADDRESS = os.getenv("USDT_ADDRESS")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TRON_PRIVATE_KEY = os.getenv("TRON_PRIVATE_KEY")

# Initialize Supabase and Tron client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
tron = Tron()
private_key = PrivateKey(bytes.fromhex(TRON_PRIVATE_KEY))

# Constants
TICKET_PRICE = 1.0  # USDT
DAILY_DRAW_HOUR = 0
DAILY_DRAW_MINUTE = 1

# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ref_id = context.args[0] if context.args else None
    username = update.effective_user.username or "NoUsername"

    # Register user in Supabase
    existing = supabase.table("users").select("*").eq("user_id", user_id).execute()
    if not existing.data:
        supabase.table("users").insert({"user_id": user_id, "username": username, "referred_by": ref_id}).execute()

    await update.message.reply_text(
        f"🎉 Welcome to One4FourBit Lottery!\nEach ticket costs {TICKET_PRICE} USDT.\nUse /buy to get tickets."
    )

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Provide payment details
    await update.message.reply_text(
        f"🪙 Send {TICKET_PRICE} USDT to:
{USDT_ADDRESS}

Then send /confirm after payment."
    )

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Confirm manually (for MVP, automate later)
    supabase.table("transactions").insert({"user_id": user_id, "amount": TICKET_PRICE, "status": "pending"}).execute()
    await update.message.reply_text("✅ Payment pending confirmation. You'll receive your ticket soon.")

async def tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    result = supabase.table("transactions").select("*").eq("user_id", user_id).eq("status", "confirmed").execute()
    count = len(result.data)
    await update.message.reply_text(f"🎟️ You have {count} confirmed ticket(s)!")

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bot_username = (await context.bot.get_me()).username
    await update.message.reply_text(
        f"🔗 Share this link to refer others:\nhttps://t.me/{bot_username}?start={user_id}"
    )

# --- Admin Command ---

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 Unauthorized")
    if len(context.args) != 1:
        return await update.message.reply_text("❗Usage: /confirm_payment <user_id>")

    user_id = int(context.args[0])
    supabase.table("transactions").update({"status": "confirmed"}).eq("user_id", user_id).eq("status", "pending").execute()

    # Pay referral if exists
    user = supabase.table("users").select("*").eq("user_id", user_id).execute().data[0]
    ref_id = user.get("referred_by")
    if ref_id:
        supabase.table("transactions").insert({"user_id": ref_id, "amount": TICKET_PRICE * 0.5, "status": "referral"}).execute()
        # Optional: Send message to referrer

    await update.message.reply_text("✅ Payment confirmed and ticket issued.")

# --- Daily Draw ---

async def daily_draw(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today().isoformat()
    result = supabase.table("transactions").select("*").eq("status", "confirmed").execute()
    entries = [tx["user_id"] for tx in result.data]

    if not entries:
        return

    winner_id = random.choice(entries)
    supabase.table("transactions").insert({"user_id": winner_id, "amount": TICKET_PRICE * len(entries), "status": "win", "date": today}).execute()

    # Tron transfer to winner (manual, secure integration needed for production)
    try:
        # Replace with actual transfer logic if needed:
        context.bot.send_message(chat_id=winner_id, text=f"🎉 You won today's One4FourBit Lottery! {TICKET_PRICE * len(entries)} USDT will be sent to you.")
    except Exception as e:
        print("Error notifying winner:", e)

# --- Main ---

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("confirm", confirm))
    app.add_handler(CommandHandler("tickets", tickets))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("confirm_payment", confirm_payment))

    # Daily job for drawing
    app.job_queue.run_daily(daily_draw, time=datetime.time(hour=DAILY_DRAW_HOUR, minute=DAILY_DRAW_MINUTE))

    print("🤖 Bot running...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())

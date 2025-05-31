from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import qrcode
from io import BytesIO

# 1. Multi-ticket purchase
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Agar quantity diya hai toh validate karo, warna 1
    qty = 1
    if context.args:
        try:
            qty = int(context.args[0])
            if qty < 1 or qty > 100:
                await update.message.reply_text("❗ You can buy between 1 and 100 tickets at once.")
                return
        except:
            await update.message.reply_text("❗ Usage: /buy <number_of_tickets>")
            return

    total_cost = qty * TICKET_PRICE

    # Create QR code for payment address with amount encoded (if wallet supports it)
    # For USDT TRC20 on Tron, usually QR code is just the wallet address; amount encoding is wallet dependent
    qr_data = USDT_ADDRESS
    qr = qrcode.make(qr_data)
    bio = BytesIO()
    qr.save(bio)
    bio.seek(0)

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Confirm Payment", callback_data=f"confirm_{qty}")]])

    await update.message.reply_photo(photo=bio, caption=(
        f"🪙 Please send exactly {total_cost} USDT ({qty} tickets x {TICKET_PRICE} USDT each) to:\n\n"
        f"{USDT_ADDRESS}\n\n"
        f"After payment, tap below to confirm."
    ), reply_markup=keyboard)

# 2. CallbackQueryHandler to handle confirm payment clicks with quantity

from telegram.ext import CallbackQueryHandler

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("confirm_"):
        qty = int(data.split("_")[1])
        user_id = query.from_user.id

        user_data = supabase.table("users").select("*").eq("user_id", user_id).execute().data
        if not user_data:
            await query.edit_message_text("❗ You are not registered. Please use /start first.")
            return

        wallet = user_data[0].get("wallet_address")
        if not wallet:
            await query.edit_message_text("❗ You have not set your TRON wallet address yet. Please set it with /setwallet.")
            return

        # Insert qty pending transactions
        for _ in range(qty):
            supabase.table("transactions").insert({
                "user_id": user_id,
                "amount": TICKET_PRICE,
                "status": "pending",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }).execute()

        await query.edit_message_text(f"✅ Payment pending confirmation by admin for {qty} ticket(s).")

# 3. Instant referral commission payment on admin confirm_payment command

async def confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 You are not authorized.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("❗ Usage: /confirm_payment <user_id>")
        return

    try:
        user_id = int(context.args[0])
    except:
        await update.message.reply_text("❗ Invalid user_id.")
        return

    pending_txs = supabase.table("transactions").select("*").eq("user_id", user_id).eq("status", "pending").execute()
    if not pending_txs.data:
        await update.message.reply_text("❗ No pending transactions for this user.")
        return

    count = len(pending_txs.data)
    supabase.table("transactions").update({"status": "confirmed"}).eq("user_id", user_id).eq("status", "pending").execute()

    # Referral commission
    user = supabase.table("users").select("*").eq("user_id", user_id).execute().data[0]
    ref_id = user.get("referred_by")
    if ref_id:
        ref_amount = TICKET_PRICE * 0.5 * count
        # Insert referral commission transaction
        supabase.table("transactions").insert({
            "user_id": ref_id,
            "amount": ref_amount,
            "status": "referral",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }).execute()

        # Send USDT instantly to referrer wallet
        ref_user = supabase.table("users").select("*").eq("user_id", ref_id).execute().data
        if ref_user:
            wallet = ref_user[0].get("wallet_address")
            if wallet:
                tx_res = send_usdt(wallet, ref_amount)
                if tx_res is None:
                    await update.message.reply_text(f"⚠️ Failed to send referral commission to user {ref_id} wallet.")
                else:
                    await update.message.reply_text(f"✅ Referral commission {ref_amount} USDT sent to user {ref_id}.")

    await update.message.reply_text(f"✅ Confirmed {count} tickets for user {user_id}.")

# 4. Leaderboard command

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get top 10 users by confirmed tickets count
    confirmed = supabase.table("transactions").select("user_id,count(*)").eq("status", "confirmed").execute()
    if not confirmed.data:
        await update.message.reply_text("No ticket sales yet.")
        return

    # Count tickets per user manually (since supabase SQL agg support is limited here)
    from collections import Counter
    counts = Counter(tx["user_id"] for tx in confirmed.data)
    top10 = counts.most_common(10)

    text = "🏆 Top Ticket Buyers:\n"
    for rank, (uid, count) in enumerate(top10, start=1):
        user = supabase.table("users").select("username").eq("user_id", uid).execute()
        username = user.data[0]["username"] if user.data else "Unknown"
        text += f"{rank}. @{username} - {count} tickets\n"

    await update.message.reply_text(text)

# 5. Daily motivational messages (job)

async def daily_message_job(context: ContextTypes.DEFAULT_TYPE):
    users = supabase.table("users").select("user_id").execute()
    if not users.data:
        return
    for user in users.data:
        try:
            await context.bot.send_message(
                chat_id=user["user_id"],
                text="💡 Daily motivation: Believe in your luck! Buy more tickets and increase your chance to win!"
            )
        except Exception as e:
            print(f"Failed to send daily message to {user['user_id']}: {e}")

# --- Add handlers and job queue in main ---

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setwallet", set_wallet))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("confirm_payment", confirm_payment))
    app.add_handler(CommandHandler("tickets", tickets))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("leaderboard", leaderboard))

    app.job_queue.run_daily(daily_draw, time=datetime.time(hour=DAILY_DRAW_HOUR, minute=DAILY_DRAW_MINUTE))
    app.job_queue.run_daily(daily_message_job, time=datetime.time(hour=9, minute=0))  # Every day 9:00 AM

    print("🤖 Bot started with advanced features...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())

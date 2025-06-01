import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from datetime import datetime, timedelta
from supabase import create_client, Client
from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.keys import PrivateKey
import random

# Env variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TRON_PRIVATE_KEY = os.getenv("TRON_PRIVATE_KEY")
TRON_NODE = os.getenv("TRON_NODE", "https://api.trongrid.io")

# Tron config
tron = Tron(HTTPProvider(TRON_NODE))
priv_key = PrivateKey(bytes.fromhex(TRON_PRIVATE_KEY))
usdt_contract = tron.get_contract('TXLAQ63Xg1NAzckPwKHvzw7CSEmLMEqcdj')  # USDT TRC-20

# Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Wallet utils
async def transfer_usdt(to_address, amount):
    txn = (
        usdt_contract.functions.transfer(to_address, int(amount * 1_000_000))
        .with_owner(priv_key.public_key.to_base58check_address())
        .fee_limit(5_000_000)
        .build()
        .sign(priv_key)
        .broadcast()
    )
    return txn.txid

# Start command
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    ref_id = message.get_args()
    user_id = message.from_user.id
    supabase.table('users').upsert({"id": user_id, "ref": ref_id or None}).execute()
    await message.answer("🎉 Welcome to TrustWin Lottery!\n\n🎟 Buy ticket by sending /buy\n💸 Daily draw: 12:01AM IST")

# Buy ticket
@dp.message_handler(commands=['buy'])
async def buy_ticket(message: types.Message):
    user_id = message.from_user.id
    user_data = supabase.table('users').select("*").eq("id", user_id).execute().data
    if not user_data or not user_data[0].get("wallet"):
        await message.answer("🔐 Please send your TRC-20 wallet address first using:\n/wallet YOUR_WALLET")
        return
    supabase.table('tickets').insert({"user": user_id, "time": datetime.utcnow().isoformat()}).execute()

    # Referral reward
    ref_id = user_data[0].get("ref")
    if ref_id:
        ref_wallet_data = supabase.table("users").select("*").eq("id", ref_id).execute().data
        if ref_wallet_data and ref_wallet_data[0].get("wallet"):
            try:
                await transfer_usdt(ref_wallet_data[0]["wallet"], 0.5)  # 50% of 1 USDT
                await bot.send_message(ref_id, "💰 You've earned 0.5 USDT from referral!")
            except:
                pass

    await message.answer("✅ Ticket purchased for tonight's draw!")

# Set wallet
@dp.message_handler(commands=['wallet'])
async def set_wallet(message: types.Message):
    wallet = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    if not wallet or not wallet.startswith("T"):
        await message.answer("❌ Invalid wallet. Must start with 'T'")
        return
    supabase.table("users").update({"wallet": wallet}).eq("id", message.from_user.id).execute()
    await message.answer("✅ Wallet address updated.")

# Fake winners display
@dp.message_handler(commands=['winners'])
async def fake_winners(message: types.Message):
    names = ["Ravi", "Priya", "Amit", "Sneha", "Ankit"]
    txt = "🏆 Past Winners:\n\n"
    for i in range(5):
        txt += f"{random.choice(names)} - 1 USDT\n"
    await message.answer(txt)

# Send daily message
async def send_daily_reminder():
    users = supabase.table("users").select("id").execute().data
    for user in users:
        try:
            await bot.send_message(user["id"], "🎯 Don't forget to buy your ticket! Use /buy")
        except:
            continue

# Daily draw
async def daily_draw():
    today = datetime.utcnow().date()
    tickets = supabase.table("tickets").select("*").execute().data
    today_tickets = [t for t in tickets if datetime.fromisoformat(t["time"]).date() == today]
    if not today_tickets:
        return
    winner = random.choice(today_tickets)
    winner_id = winner["user"]
    user_wallet = supabase.table("users").select("wallet").eq("id", winner_id).execute().data[0]["wallet"]
    try:
        txid = await transfer_usdt(user_wallet, 1.0)
        await bot.send_message(winner_id, f"🎉 You won 1 USDT! TxID: {txid}")
    except Exception as e:
        await bot.send_message(ADMIN_ID, f"❌ Failed to send prize: {str(e)}")

# Scheduler
async def scheduler():
    while True:
        now = datetime.now()
        target = datetime.combine(now.date() + timedelta(days=1), datetime.strptime("00:01", "%H:%M").time())
        await asyncio.sleep((target - now).total_seconds())
        await daily_draw()
        await send_daily_reminder()

# Run bot
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())
    executor.start_polling(dp, skip_updates=True)

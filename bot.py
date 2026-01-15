import random
from typing import Dict, Any, Tuple

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# 🔐 BOT TOKEN (এখানে বসান)
# =========================
BOT_TOKEN = "7352884661:AAFIvyPBsVA8U_VyJYfSWwOXx3MuhvvSpuw"


# -----------------------------
# SAFE DEMO PROFILE DATABASE
# -----------------------------
MOCK_PROFILES: Dict[str, Dict[str, str]] = {
    "5853684": {
        "info": "MASTERCARD – DEBIT (DEMO)",
        "bank": "BANCO SANTANDER MEXICO SA INSTITUCION DE BANCA MULTIPLE GRUPO FINANC",
        "country": "Mexico 🇲🇽",
    },
}

# -----------------------------
# Helpers
# -----------------------------
def rand_mm() -> str:
    return f"{random.randint(1, 12):02d}"

def rand_yyyy() -> str:
    return str(random.randint(2026, 2035))

def rand_ref3() -> str:
    # REF = reference code (NOT CVV)
    return f"{random.randint(0, 999):03d}"

def rand_digits(n: int) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(n))

def parse_gen_args(arg_text: str) -> Tuple[str, int]:
    arg_text = (arg_text or "").strip()
    if not arg_text:
        raise ValueError("Missing args")

    parts = arg_text.split()
    prefix = parts[0].strip()

    if not prefix.isdigit():
        raise ValueError("Prefix must be digits")

    amount = 15
    if len(parts) >= 2:
        if not parts[1].isdigit():
            raise ValueError("Amount must be a number")
        amount = int(parts[1])
        if amount < 1:
            amount = 1
        if amount > 50:
            amount = 50

    return prefix, amount

def format_info_block(prefix: str) -> str:
    p: Dict[str, Any] = MOCK_PROFILES.get(prefix, {})
    info = p.get("info", "DEMO PROFILE – REFERENCE CODES")
    bank = p.get("bank", "—")
    country = p.get("country", "—")

    return (
        "──────────────\n"
        f"|  𝗜𝗻𝗳𝗼: {info}\n"
        f"|  𝗕𝗮𝗻𝗸: {bank}\n"
        f"|  𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {country}\n"
    )

def make_reference_lines(prefix: str, amount: int) -> str:
    need = max(0, 17 - len(prefix))
    lines = []
    for _ in range(amount):
        code17 = prefix + rand_digits(need)
        lines.append(f"{code17}|{rand_mm()}|{rand_yyyy()}|{rand_ref3()}")
    return "\n".join(lines)

# -----------------------------
# Commands
# -----------------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fname = (update.message.from_user.first_name if update.message else "") or "User"
    msg = (
        f"Hello {fname}!\n\n"
        "Commands:\n"
        "• /gen <prefix> [amount]\n\n"
        "Example:\n"
        "• /gen 5853684\n"
        "• /gen 5853684 15"
    )
    await update.message.reply_text(msg)

async def gen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = " ".join(context.args)
        prefix, amount = parse_gen_args(args)

        lines = make_reference_lines(prefix, amount)
        info_block = format_info_block(prefix)
        fname = (update.message.from_user.first_name if update.message else "") or "User"

        reply = (
            f"𝗡 ⇾ {prefix}\n"
            f"Amount {amount}\n\n"
            f"{lines}\n\n"
            f"{info_block}\n"
            f"Request by: {fname}"
        )
        await update.message.reply_text(reply)

    except Exception:
        await update.message.reply_text(
            "Usage:\n"
            "/gen 5853684\n"
            "/gen 5853684 15"
        )

# -----------------------------
# Main
# -----------------------------
def main():
    if not BOT_TOKEN or "PASTE_YOUR_BOT_TOKEN_HERE" in BOT_TOKEN:
        raise RuntimeError("Please set your BOT_TOKEN inside the code.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("gen", gen_cmd))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

import re
import random
import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# =========================
# 🔐 BOT TOKEN (PASTE HERE)
# =========================
BOT_TOKEN = "PASTE_YOUR_BOT_TOKEN_HERE"

# =========================
# Settings
# =========================
DB_PATH = "codes.db"
MAX_AMOUNT = 50
DEFAULT_AMOUNT = 15
# The numeric reference code length (not a card; just a fixed-length reference)
REF_CODE_LEN = 17

# Conversation states
ASK_AMOUNT = 1

# -------------------------
# Database (global uniqueness)
# -------------------------
def db_init():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS generated_codes (
            code TEXT PRIMARY KEY
        )
        """
    )
    con.commit()
    con.close()

def db_has(code: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT 1 FROM generated_codes WHERE code = ?", (code,))
    row = cur.fetchone()
    con.close()
    return row is not None

def db_add(code: str) -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("INSERT OR IGNORE INTO generated_codes(code) VALUES(?)", (code,))
    con.commit()
    con.close()

# -------------------------
# Parsing
# -------------------------
@dataclass
class GenRequest:
    pattern: str               # e.g. "559888065125xxxx" or "559888065125"
    mm: Optional[str] = None   # "08"
    yyyy: Optional[str] = None # "2029"

def normalize_year(y: str) -> str:
    y = y.strip()
    if len(y) == 2 and y.isdigit():
        return "20" + y
    return y

def rand_mm() -> str:
    return f"{random.randint(1,12):02d}"

def rand_yyyy() -> str:
    return str(random.randint(2026, 2035))

def rand_ref3() -> str:
    return f"{random.randint(0,999):03d}"

def parse_gen_input(text: str) -> GenRequest:
    """
    Supported:
      /gen <pattern>
      /gen <pattern>|MM|YYYY
      /gen <pattern>|MM|YY

    pattern can contain digits and 'x' wildcard (lower/upper).
    Examples:
      559888065125xxxx
      559888065125
    """
    t = (text or "").strip()
    if not t:
        raise ValueError("Missing")

    # Only take first argument string after /gen
    # We will join args in handler.
    first = t.split()[0].strip()

    if "|" in first:
        bits = [b.strip() for b in first.split("|")]
        if len(bits) != 3:
            raise ValueError("Bad pipe format. Use: /gen PATTERN|MM|YYYY")
        pattern, mm, y = bits
        yyyy = normalize_year(y)

        if not re.fullmatch(r"[0-9xX]+", pattern):
            raise ValueError("Pattern must contain only digits and x.")
        if not (mm.isdigit() and 1 <= int(mm) <= 12):
            raise ValueError("Month must be 01-12.")
        if not (yyyy.isdigit() and len(yyyy) == 4):
            raise ValueError("Year must be YYYY or YY.")

        return GenRequest(pattern=pattern.lower(), mm=f"{int(mm):02d}", yyyy=yyyy)

    # no pipes
    if not re.fullmatch(r"[0-9xX]+", first):
        raise ValueError("Pattern must contain only digits and x.")
    return GenRequest(pattern=first.lower())

# -------------------------
# Code generation (reference/demo)
# -------------------------
def build_ref_code(pattern: str) -> str:
    """
    Turn pattern into a REF_CODE_LEN digit string.
    Rules:
    - 'x' positions become random digits.
    - If pattern has fewer than REF_CODE_LEN chars, append random digits.
    - If pattern has more than REF_CODE_LEN chars, truncate to REF_CODE_LEN.
    """
    out = []
    for ch in pattern:
        if ch == "x":
            out.append(str(random.randint(0,9)))
        else:
            out.append(ch)

    s = "".join(out)

    if len(s) < REF_CODE_LEN:
        s += "".join(str(random.randint(0,9)) for _ in range(REF_CODE_LEN - len(s)))
    elif len(s) > REF_CODE_LEN:
        s = s[:REF_CODE_LEN]

    # Ensure it is digits only
    if not s.isdigit():
        raise ValueError("Generated reference code is not numeric.")
    return s

def generate_unique_codes(req: GenRequest, amount: int) -> str:
    """
    Creates `amount` unique reference lines:
      <REF17>|<MM>|<YYYY>|<REF3>
    Uniqueness is enforced on the REF17 part globally via SQLite.
    """
    lines = []
    mm = req.mm if req.mm else rand_mm()
    yyyy = req.yyyy if req.yyyy else rand_yyyy()

    # If user didn't provide MM/YYYY, randomize per line
    per_line_date = (req.mm is None) or (req.yyyy is None)

    attempts_limit = 200000  # safety cap
    attempts = 0

    while len(lines) < amount:
        attempts += 1
        if attempts > attempts_limit:
            raise RuntimeError("Unable to generate more unique codes for this pattern.")

        ref17 = build_ref_code(req.pattern)

        # Global uniqueness
        if db_has(ref17):
            continue

        # reserve it immediately
        db_add(ref17)

        use_mm = mm
        use_yyyy = yyyy
        if per_line_date:
            use_mm = rand_mm()
            use_yyyy = rand_yyyy()

        line = f"{ref17}|{use_mm}|{use_yyyy}|{rand_ref3()}"
        lines.append(line)

    return "\n".join(lines)

# -------------------------
# Telegram handlers
# -------------------------
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Reference Code Generator is ready.\n\n"
        "Usage:\n"
        "• /gen 559888065125xxxx|08|2029\n"
        "• /gen 559888065125xxxx\n"
        "• /gen 559888065125\n\n"
        "After /gen, I will ask how many codes you need (1–50)."
    )

async def gen_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = " ".join(context.args).strip()
        req = parse_gen_input(args)

        # store request in user_data for next step
        context.user_data["gen_req"] = req

        # ask amount
        await update.message.reply_text(
            "How many reference codes do you need?\n"
            f"Send a number from 1 to {MAX_AMOUNT}."
        )
        return ASK_AMOUNT

    except Exception:
        await update.message.reply_text(
            "Usage:\n"
            "/gen 559888065125xxxx|08|2029\n"
            "/gen 559888065125xxxx\n"
            "/gen 559888065125"
        )
        return ConversationHandler.END

async def amount_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (update.message.text or "").strip()

    if not txt.isdigit():
        await update.message.reply_text(f"Please send a number from 1 to {MAX_AMOUNT}.")
        return ASK_AMOUNT

    amount = int(txt)
    if amount < 1:
        amount = 1
    if amount > MAX_AMOUNT:
        amount = MAX_AMOUNT

    req: GenRequest = context.user_data.get("gen_req")
    if not req:
        await update.message.reply_text("Session expired. Please run /gen again.")
        return ConversationHandler.END

    try:
        lines = generate_unique_codes(req, amount)
        # Show "N" as the original pattern without pipes
        n_show = req.pattern

        info_block = (
            "──────────────\n"
            "|  Info: REFERENCE CODES (DEMO)\n"
            "|  Note: Not a payment card\n"
        )

        fname = (update.message.from_user.first_name if update.message else "") or "User"

        reply = (
            f"𝗡 ⇾ {n_show}\n"
            f"Amount {amount}\n\n"
            f"{lines}\n\n"
            f"{info_block}\n"
            f"Request by: {fname}"
        )
        await update.message.reply_text(reply)

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

    finally:
        context.user_data.pop("gen_req", None)

    return ConversationHandler.END

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("gen_req", None)
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

def main():
    if not BOT_TOKEN or "PASTE_YOUR_BOT_TOKEN_HERE" in BOT_TOKEN:
        raise RuntimeError("Set BOT_TOKEN inside the code first.")

    db_init()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("gen", gen_cmd)],
        states={
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_reply)]
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
    )

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(conv)

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

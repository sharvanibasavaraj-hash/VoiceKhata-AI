import re
import sqlite3
from pathlib import Path
from datetime import datetime, date, timedelta

DB_PATH = Path(__file__).resolve().parent / "voicekhata.db"


# DATABASE

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ledger_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                entry_type TEXT NOT NULL,
                amount REAL NOT NULL,
                occurred_at TEXT,
                description TEXT,
                created_at TEXT
            )
        """)
        conn.commit()


initialize_database()


# HELPERS

def clean_name(name):
    name = re.sub(r"[^A-Za-z0-9 .'-]", " ", str(name))
    return re.sub(r"\s+", " ", name).strip().title()


def extract_amount(text):
    matches = re.findall(
        r"(?<![A-Za-z])(?:₹|rs\.?\s*)?(\d[\d,]*(?:\.\d{1,2})?)(?![A-Za-z])",
        text,
        flags=re.IGNORECASE
    )

    if not matches:
        return None

    try:
        return float(matches[-1].replace(",", ""))
    except ValueError:
        return None


def money(amount):
    return f"₹{amount:,.2f}".replace(".00", "")


def get_date_from_text(text):
    lower = text.lower()
    today = date.today()

    if "day before yesterday" in lower or "parso" in lower:
        return (today - timedelta(days=2)).isoformat()

    if "yesterday" in lower or "kal" in lower:
        return (today - timedelta(days=1)).isoformat()

    if "tomorrow" in lower:
        return (today + timedelta(days=1)).isoformat()

    return today.isoformat()


def extract_customer(text):
    value = re.sub(
        r"(?:₹|rs\.?\s*)?\d[\d,]*(?:\.\d{1,2})?",
        " ",
        str(text),
        flags=re.IGNORECASE
    )

    remove_words = [
        "credit", "udhaar", "borrowed", "gave", "give",
        "payment", "paid", "received", "deposit", "jama",
        "sale", "sales", "sold", "purchase", "purchases",
        "bought", "balance", "total", "amount", "rupees",
        "rupee", "customer", "add", "record", "entry",
        "transaction", "account", "ka", "ki", "ke", "ko",
        "ne", "hai", "tha", "aaj", "kal", "please",
        "today", "yesterday", "tomorrow", "nahi", "no",
        "correction", "correct", "change", "set", "update",
        "my", "the", "for", "how", "much", "does", "owe",
        "owes", "pending", "what", "is", "his", "her"
    ]

    for word in remove_words:
        value = re.sub(
            r"\b" + re.escape(word) + r"\b",
            " ",
            value,
            flags=re.IGNORECASE
        )

    value = re.sub(r"\s+", " ", value).strip(" .,-")
    return clean_name(value) if value else None


# LEDGER OPERATIONS

def add_entry(customer_name, entry_type, amount,
              occurred_at=None, description=None):

    customer_name = clean_name(customer_name)
    amount = float(amount)

    if not customer_name:
        raise ValueError("Customer name is required.")

    if entry_type not in ("credit", "payment", "sale", "purchase"):
        raise ValueError("Invalid transaction type.")

    if amount <= 0:
        raise ValueError("Amount must be positive.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO ledger_entries
            (customer_name, entry_type, amount,
             occurred_at, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            customer_name,
            entry_type,
            amount,
            occurred_at or now,
            description or f"{customer_name} - {entry_type}",
            now
        ))
        conn.commit()
        return cursor.lastrowid


def get_customer_balance(customer_name):
    name = clean_name(customer_name)

    with get_connection() as conn:
        row = conn.execute("""
            SELECT COALESCE(SUM(
                CASE
                    WHEN entry_type = 'credit' THEN amount
                    WHEN entry_type = 'payment' THEN -amount
                    ELSE 0
                END
            ), 0) AS balance
            FROM ledger_entries
            WHERE LOWER(customer_name) = LOWER(?)
        """, (name,)).fetchone()

    return float(row["balance"] or 0)


def get_summary():
    today = date.today().isoformat()

    with get_connection() as conn:
        totals = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN entry_type='credit'
                    THEN amount ELSE 0 END), 0) AS total_credit,
                COALESCE(SUM(CASE WHEN entry_type='payment'
                    THEN amount ELSE 0 END), 0) AS total_payments,
                COALESCE(SUM(CASE WHEN entry_type='sale'
                    THEN amount ELSE 0 END), 0) AS total_sales,
                COALESCE(SUM(CASE WHEN entry_type='purchase'
                    THEN amount ELSE 0 END), 0) AS total_purchases
            FROM ledger_entries
        """).fetchone()

        daily = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN entry_type='sale'
                    THEN amount ELSE 0 END), 0) AS today_sales,
                COALESCE(SUM(CASE WHEN entry_type='credit'
                    THEN amount ELSE 0 END), 0) AS today_credit,
                COALESCE(SUM(CASE WHEN entry_type='payment'
                    THEN amount ELSE 0 END), 0) AS today_payments
            FROM ledger_entries
            WHERE DATE(occurred_at) = ?
        """, (today,)).fetchone()

    credit = float(totals["total_credit"])
    payments = float(totals["total_payments"])
    balance = credit - payments

    return {
        "balance": balance,
        "outstanding_balance": balance,
        "total_credit": credit,
        "total_credited": credit,
        "total_payments": payments,
        "total_sales": float(totals["total_sales"]),
        "total_purchases": float(totals["total_purchases"]),
        "today_sales": float(daily["today_sales"]),
        "today_credit": float(daily["today_credit"]),
        "today_payments": float(daily["today_payments"])
    }


def get_transactions(limit=100):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, customer_name, entry_type, amount,
                   occurred_at, description, created_at
            FROM ledger_entries
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [
        {
            "id": row["id"],
            "customer": row["customer_name"],
            "customer_name": row["customer_name"],
            "description": row["customer_name"],
            "type": row["entry_type"],
            "entry_type": row["entry_type"],
            "amount": float(row["amount"]),
            "date": row["occurred_at"] or row["created_at"],
            "created_at": row["created_at"],
            "note": row["description"] or ""
        }
        for row in rows
    ]


def correct_latest_entry(amount):
    amount = float(amount)

    if amount <= 0:
        return False

    with get_connection() as conn:
        row = conn.execute("""
            SELECT id FROM ledger_entries
            ORDER BY id DESC LIMIT 1
        """).fetchone()

        if row is None:
            return False

        conn.execute("""
            UPDATE ledger_entries
            SET amount = ?,
                description = COALESCE(description, '') || ' (corrected)'
            WHERE id = ?
        """, (amount, row["id"]))

        conn.commit()

    return True


# COMMAND PROCESSING

def process_command(command, language_code="en-IN"):
    text = str(command).strip()
    lower = text.lower()

    if not text:
        return "Please tell me your transaction."

    amount = extract_amount(text)

    # CORRECTIONS
    correction_words = [
        "no", "nahi", "correction", "correct it",
        "change it", "actually"
    ]

    if any(word in lower for word in correction_words):
        if amount is None:
            return "Please tell me the corrected amount."

        if correct_latest_entry(amount):
            return f"The latest transaction is corrected to {money(amount)}."

        return "There is no transaction to correct."

    # DAILY SUMMARY
    if any(word in lower for word in [
        "today's sales", "today sales", "daily sales",
        "aaj ki sale", "aaj kitna", "today summary"
    ]):
        summary = get_summary()

        return (
            f"Today's sales are {money(summary['today_sales'])}. "
            f"Today's credit is {money(summary['today_credit'])}. "
            f"Payments received are {money(summary['today_payments'])}."
        )

    # OVERALL SUMMARY
    if any(word in lower for word in [
        "overall summary", "total business", "full summary"
    ]):
        summary = get_summary()

        return (
            f"Total credit is {money(summary['total_credit'])}. "
            f"Total payments are {money(summary['total_payments'])}. "
            f"Outstanding balance is {money(summary['balance'])}."
        )

    # CUSTOMER BALANCE
    balance_query = any(word in lower for word in [
        "balance", "how much does", "how much has",
        "total udhaar", "kitna udhaar", "pending amount",
        "owes"
    ])

    if balance_query:
        customer = extract_customer(text)

        if not customer:
            return (
                f"Total outstanding balance is "
                f"{money(get_summary()['balance'])}."
            )

        balance = get_customer_balance(customer)
        return f"{customer}'s outstanding balance is {money(balance)}."

    # NEW TRANSACTION
    if amount is None:
        return "I couldn't identify the amount. Please mention the amount."

    customer = extract_customer(text)

    if not customer:
        return "I couldn't identify the customer name. Please mention it."

    words = lower.split()

    payment_words = {
        "paid", "payment", "received", "deposit",
        "jama", "repaid", "returned"
    }
    sale_words = {"sale", "sales", "sold"}
    purchase_words = {"purchase", "purchases", "bought"}

    if any(word in words for word in payment_words):
        entry_type = "payment"
    elif any(word in words for word in sale_words):
        entry_type = "sale"
    elif any(word in words for word in purchase_words):
        entry_type = "purchase"
    else:
        entry_type = "credit"

    transaction_date = get_date_from_text(text)
    occurred_at = (
        transaction_date + " " +
        datetime.now().strftime("%H:%M:%S")
    )

    add_entry(
        customer,
        entry_type,
        amount,
        occurred_at,
        f"{customer} - {entry_type}"
    )

    if entry_type == "credit":
        balance = get_customer_balance(customer)
        return (
            f"Recorded {money(amount)} credit for {customer}. "
            f"Their outstanding balance is {money(balance)}."
        )

    if entry_type == "payment":
        balance = get_customer_balance(customer)
        return (
            f"Recorded payment of {money(amount)} from {customer}. "
            f"Their outstanding balance is {money(balance)}."
        )

    if entry_type == "sale":
        return f"Recorded a sale of {money(amount)}."

    return f"Recorded a purchase of {money(amount)}."
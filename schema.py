import sqlite3
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Transaction(BaseModel):
    date: str = Field(..., description="The date of the transaction (YYYY-MM-DD)")
    description: str = Field(..., description="The merchant or description of the transaction")
    amount: float = Field(..., description="The transaction amount as a float")
    category: str = Field(..., description="The category like Grocery, Rent, Travel, etc. If not known, use 'Miscellaneous'")
    location: Optional[str] = Field(None, description="City and/or State if available")
    source_file: Optional[str] = Field(None, description="The name of the statement file this came from")

def init_db(db_path: str = "expenses.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            location TEXT,
            source_file TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_transactions(transactions: List[Transaction], db_path: str = "expenses.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    for tx in transactions:
        cursor.execute("""
            INSERT INTO transactions (date, description, amount, category, location, source_file)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tx.date, tx.description, tx.amount, tx.category, tx.location, tx.source_file))
    conn.commit()
    conn.close()

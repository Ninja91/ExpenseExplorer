import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, UniqueConstraint, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, ConfigDict
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tensorlake.applications import File

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///expenses.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# SQLAlchemy Model
class DBTransaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, nullable=False)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String)
    location = Column(String)
    source_file = Column(String, nullable=False)
    merchant = Column(String)
    is_subscription = Column(Boolean, default=False)
    payment_method = Column(String)
    tags = Column(String)
    currency = Column(String, default="USD")
    raw_description = Column(String)
    transaction_type = Column(String) # Debit, Credit, Transfer, Payment
    reference_number = Column(String)
    account_last_4 = Column(String)
    provider_name = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('date', 'description', 'amount', 'source_file', name='_date_desc_amount_file_uc'),
    )

# Insights Model
class DBInsight(Base):
    __tablename__ = "insights"
    
    id = Column(Integer, primary_key=True, index=True)
    insight_type = Column(String, nullable=False)  # category_summary, merchant_enrichment, trend, subscription
    key = Column(String, nullable=False)  # Category name, merchant name, or trend ID
    value = Column(String, nullable=False)  # JSON-serialized insight data
    transaction_ids = Column(String)  # Comma-separated IDs of related transactions
    confidence = Column(Float, default=1.0)  # Confidence score (0-1)
    computed_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)  # When this insight becomes stale

    __table_args__ = (
        UniqueConstraint('insight_type', 'key', name='_insight_type_key_uc'),
    )

# Pydantic Models for API/Logic
class Transaction(BaseModel):
    date: str = Field(..., description="The date of the transaction (YYYY-MM-DD)")
    description: str = Field(..., description="The merchant or description of the transaction")
    amount: float = Field(..., description="The transaction amount as a float")
    category: str = Field(..., description="The category like Grocery, Rent, Travel, etc. If not known, use 'Miscellaneous'")
    location: str | None = Field(None, description="City and/or State if available")
    source_file: str | None = Field(None, description="The name of the statement file this came from")
    merchant: str | None = Field(None, description="The cleaned merchant name")
    is_subscription: bool = Field(False, description="Whether this appears to be a recurring subscription")
    payment_method: str | None = Field(None, description="The payment method (e.g., Visa, Mastercard, Cash)")
    tags: str | None = Field(None, description="Comma-separated tags for further classification")
    currency: str = Field("USD", description="The currency of the transaction")
    raw_description: str | None = Field(None, description="The unmodified description string")
    transaction_type: str | None = Field(None, description="Debit, Credit, Transfer, Payment")
    reference_number: str | None = Field(None, description="Transaction reference or ID")
    account_last_4: str | None = Field(None, description="Last 4 digits of the account/card")
    provider_name: str | None = Field(None, description="Name of the financial institution")

class IngestionRequest(BaseModel):
    file_b64: str
    content_type: str
    filename: str


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(SQLAlchemyError),
    reraise=True
)
def init_db():
    from sqlalchemy import inspect
    # Create all tables first
    Base.metadata.create_all(bind=engine)
    
    # Self-healing: Add new columns if they don't exist
    new_columns = [
        ("merchant", "VARCHAR"),
        ("is_subscription", "BOOLEAN DEFAULT FALSE"),
        ("payment_method", "VARCHAR"),
        ("tags", "VARCHAR"),
        ("currency", "VARCHAR DEFAULT 'USD'"),
        ("raw_description", "VARCHAR"),
        ("transaction_type", "VARCHAR"),
        ("reference_number", "VARCHAR"),
        ("account_last_4", "VARCHAR"),
        ("provider_name", "VARCHAR")
    ]
    
    try:
        inspector = inspect(engine)
        existing_columns = [c['name'] for c in inspector.get_columns('transactions')]
        
        with engine.connect() as conn:
            for col_name, col_type in new_columns:
                if col_name not in existing_columns:
                    try:
                        conn.execute(text(f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}"))
                        conn.commit()
                        print(f"Migration: Added column {col_name}")
                    except Exception as e:
                        print(f"Migration error for {col_name}: {e}")
    except Exception as e:
        print(f"Inspector error: {e}")

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(SQLAlchemyError),
    reraise=True
)
def save_transactions(transactions: List[Transaction]) -> int:
    session = SessionLocal()
    new_count = 0
    try:
        for tx in transactions:
            # Check for existing transaction with same date, description, amount, and source_file
            exists = session.query(DBTransaction).filter(
                DBTransaction.date == tx.date,
                DBTransaction.description == tx.description,
                DBTransaction.amount == tx.amount,
                DBTransaction.source_file == (tx.source_file or "unknown")
            ).first()
            
            if not exists:
                db_tx = DBTransaction(
                    date=tx.date,
                    description=tx.description,
                    amount=tx.amount,
                    category=tx.category,
                    location=tx.location,
                    source_file=tx.source_file or "unknown",
                    merchant=tx.merchant,
                    is_subscription=tx.is_subscription,
                    payment_method=tx.payment_method,
                    tags=tx.tags,
                    currency=tx.currency,
                    raw_description=tx.raw_description,
                    transaction_type=tx.transaction_type,
                    reference_number=tx.reference_number,
                    account_last_4=tx.account_last_4,
                    provider_name=tx.provider_name
                )
                session.add(db_tx)
                new_count += 1
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()
    return new_count

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(SQLAlchemyError),
    reraise=True
)
def get_all_transactions() -> List[dict]:
    session = SessionLocal()
    try:
        transactions = session.query(DBTransaction).all()
        return [
            {
                "date": tx.date,
                "description": tx.description,
                "amount": tx.amount,
                "category": tx.category,
                "location": tx.location,
                "source_file": tx.source_file,
                "merchant": tx.merchant,
                "is_subscription": tx.is_subscription,
                "payment_method": tx.payment_method,
                "tags": tx.tags,
                "currency": tx.currency,
                "raw_description": tx.raw_description,
                "transaction_type": tx.transaction_type,
                "reference_number": tx.reference_number,
                "account_last_4": tx.account_last_4,
                "provider_name": tx.provider_name
            }
            for tx in transactions
        ]
    finally:
        session.close()

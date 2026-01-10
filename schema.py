import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, ConfigDict
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
    created_at = Column(DateTime, default=datetime.utcnow)

# Pydantic Models for API/Logic
class Transaction(BaseModel):
    date: str = Field(..., description="The date of the transaction (YYYY-MM-DD)")
    description: str = Field(..., description="The merchant or description of the transaction")
    amount: float = Field(..., description="The transaction amount as a float")
    category: str = Field(..., description="The category like Grocery, Rent, Travel, etc. If not known, use 'Miscellaneous'")
    location: str | None = Field(None, description="City and/or State if available")
    source_file: str | None = Field(None, description="The name of the statement file this came from")

class IngestionRequest(BaseModel):
    file_b64: str
    content_type: str
    filename: str


def init_db():
    Base.metadata.create_all(bind=engine)

def save_transactions(transactions: List[Transaction]):
    session = SessionLocal()
    try:
        for tx in transactions:
            db_tx = DBTransaction(
                date=tx.date,
                description=tx.description,
                amount=tx.amount,
                category=tx.category,
                location=tx.location,
                source_file=tx.source_file or "unknown"
            )
            session.add(db_tx)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

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
                "source_file": tx.source_file
            }
            for tx in transactions
        ]
    finally:
        session.close()

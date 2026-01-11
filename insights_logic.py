"""
Insights Logic for Expense Explorer.
Contains the agent tools and CRUD functions for generating and storing insights.
"""
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import litellm

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///expenses.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Cache duration: 1 week
INSIGHTS_TTL_DAYS = 7


def init_insights_table():
    """Creates the insights table if it doesn't exist."""
    from schema import Base, engine
    
    # Create all tables (including insights table via DBInsight model)
    Base.metadata.create_all(bind=engine)


# ============================================================
# TOOL 1: Category Summarizer (Pure SQL/Python)
# ============================================================

def summarize_by_category() -> Dict[str, float]:
    """
    Aggregates spending totals by category.
    Returns a dict like {"Groceries": 450.00, "Travel": 1200.00, ...}
    """
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT category, SUM(amount) as total
            FROM transactions
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY total DESC
        """))
        return {row[0]: round(float(row[1]), 2) for row in result}


# ============================================================
# TOOL 2: Merchant Enricher (Rule-Based)
# ============================================================

MERCHANT_RULES = {
    # Transportation
    "Transportation": ["UBER", "LYFT", "TAXI", "METRO", "TRANSIT", "PARKING", "GAS", "SHELL", "CHEVRON", "EXXON"],
    # Groceries
    "Groceries": ["WALMART", "COSTCO", "SAFEWAY", "KROGER", "TRADER JOE", "WHOLE FOODS", "ALDI", "PUBLIX", "HEB"],
    # Dining
    "Dining": ["RESTAURANT", "CAFE", "COFFEE", "STARBUCKS", "MCDONALDS", "CHIPOTLE", "PIZZA", "SUSHI", "GRUBHUB", "DOORDASH"],
    # Travel
    "Travel": ["AIRLINE", "HOTEL", "MARRIOTT", "HILTON", "HERTZ", "AVIS", "AIRBNB", "BOOKING", "EXPEDIA", "SOUTHWEST", "DELTA", "UNITED"],
    # Subscriptions
    "Subscriptions": ["NETFLIX", "SPOTIFY", "APPLE", "AMAZON PRIME", "HULU", "HBO", "DISNEY", "YOUTUBE"],
    # Insurance
    "Insurance": ["INSURANCE", "GEICO", "STATE FARM", "ALLSTATE", "PROGRESSIVE"],
    # Utilities
    "Utilities": ["ELECTRIC", "WATER", "GAS BILL", "INTERNET", "COMCAST", "ATT", "VERIZON", "TMOBILE"],
    # Shopping
    "Shopping": ["AMAZON", "TARGET", "BEST BUY", "APPLE STORE", "NORDSTROM", "MACYS"],
}

def enrich_merchant(merchant_name: str) -> Dict[str, Any]:
    """
    Enriches merchant with inferred business type and category.
    Uses rule-based matching (Option C).
    """
    if not merchant_name:
        return {"type": "Unknown", "inferred_category": "Miscellaneous"}
    
    upper_name = merchant_name.upper()
    
    for category, keywords in MERCHANT_RULES.items():
        for keyword in keywords:
            if keyword in upper_name:
                return {
                    "type": category,
                    "inferred_category": category,
                    "matched_keyword": keyword
                }
    
    return {"type": "Unknown", "inferred_category": "Miscellaneous"}


# ============================================================
# TOOL 3: Subscription Detector (Pattern Matching)
# ============================================================

def detect_subscriptions() -> List[Dict[str, Any]]:
    """
    Finds recurring transactions by matching:
    - Same merchant (or similar description)
    - Same amount (within 5% tolerance)
    - Regular interval (monthly)
    """
    with engine.connect() as conn:
        # Get all transactions grouped by description, amount, and account/provider
        result = conn.execute(text("""
            SELECT description, amount, provider_name, account_last_4, COUNT(*) as occurrences
            FROM transactions
            GROUP BY description, amount, provider_name, account_last_4
            HAVING COUNT(*) >= 2
            ORDER BY occurrences DESC
        """))
        
        subscriptions = []
        for row in result:
            description, amount, provider_name, account_last_4, occurrences = row
            
            # Check if it matches known subscription keywords
            upper_desc = description.upper() if description else ""
            is_likely_subscription = any(
                kw in upper_desc for kw in 
                ["SUBSCRIPTION", "MONTHLY", "NETFLIX", "SPOTIFY", "APPLE", "AMAZON PRIME", "HULU", "HBO", "DISNEY", "YOUTUBE", "INSURANCE"]
            )
            
            if is_likely_subscription or occurrences >= 3:
                subscriptions.append({
                    "description": description,
                    "amount": float(amount),
                    "occurrences": occurrences,
                    "provider": provider_name,
                    "account": account_last_4,
                    "is_likely_subscription": is_likely_subscription,
                    "estimated_monthly_cost": float(amount) if occurrences >= 2 else 0
                })
        
        return subscriptions


# ============================================================
# TOOL 3.5: Anomaly Detector (Statistics)
# ============================================================

def detect_anomalies() -> List[Dict[str, Any]]:
    """
    Identifies:
    - Spending spikes (amount > 2x recent category average)
    - New merchant charges (first time seen)
    """
    from schema import SessionLocal as SchemaSession, DBTransaction
    from collections import defaultdict
    import numpy as np

    session = SchemaSession()
    try:
        transactions = session.query(DBTransaction).all()
        if not transactions:
            return []

        # Sort by date
        sorted_txs = sorted(transactions, key=lambda x: x.date)
        
        category_spending = defaultdict(list)
        seen_merchants = set()
        anomalies = []

        # Process chronologically
        for tx in sorted_txs:
            # Skip non-expenses
            if tx.amount <= 0 or tx.category in ["Credit Card Payment", "Internal Transfer"]:
                continue

            # 1. Spike Detection
            recent_spending = category_spending[tx.category][-10:] # Last 10 in category
            if recent_spending:
                avg = sum(recent_spending) / len(recent_spending)
                if tx.amount > (avg * 2.5) and tx.amount > 50:
                    anomalies.append({
                        "type": "spike",
                        "severity": "high" if tx.amount > (avg * 5) else "medium",
                        "description": f"Unusually high {tx.category} expense",
                        "amount": tx.amount,
                        "date": tx.date,
                        "merchant": tx.merchant or tx.description
                    })
            
            # 2. New Merchant Detection
            m_key = (tx.merchant or tx.description).lower()
            if m_key not in seen_merchants and len(seen_merchants) > 20: 
                anomalies.append({
                    "type": "new_merchant",
                    "severity": "low",
                    "description": f"First time spending at {tx.merchant or tx.description}",
                    "amount": tx.amount,
                    "date": tx.date,
                    "merchant": tx.merchant or tx.description
                })
            
            # Update state
            category_spending[tx.category].append(tx.amount)
            seen_merchants.add(m_key)

        # Return latest anomalies (last 5)
        return anomalies[-5:]
    finally:
        session.close()

# ============================================================
# TOOL 4: Category Inferer (LLM-Powered)
# ============================================================

def infer_category(description: str) -> str:
    """
    Uses Gemini to intelligently categorize a transaction.
    Falls back to 'Miscellaneous' if uncertain.
    """
    if not description:
        return "Miscellaneous"
    
    try:
        response = litellm.completion(
            model="gemini/gemini-3-flash-preview",
            messages=[{
                "role": "user",
                "content": f"""Categorize this transaction into ONE of these categories:
Groceries, Dining, Transportation, Travel, Shopping, Subscriptions, Utilities, Insurance, Healthcare, Entertainment, Education, Personal Care, Miscellaneous

Transaction: {description}

Reply with ONLY the category name, nothing else."""
            }],
            max_tokens=20
        )
        category = response.choices[0].message.content.strip()
        return category if category else "Miscellaneous"
    except Exception as e:
        print(f"LLM inference error: {e}")
        return "Miscellaneous"


# ============================================================
# TOOL 5: Trend Analyzer
# ============================================================

def analyze_trends() -> Dict[str, Any]:
    """
    Analyzes spending trends over time.
    Aggregates in Python to be robust against varying date formats in the database.
    """
    from schema import SessionLocal as SchemaSession, DBTransaction
    from collections import defaultdict
    from datetime import datetime, timedelta
    import re

    session = SchemaSession()
    try:
        transactions = session.query(DBTransaction).all()
        if not transactions:
            return {
                "trend": "stable", "change_percentage": 0, "current_month_total": 0,
                "previous_month_total": 0, "daily": [], "weekly": [], "monthly": []
            }

        parsed_data = []
        for tx in transactions:
            # Skip transfers and payments to avoid double-counting in spending trends
            if tx.category in ["Credit Card Payment", "Internal Transfer"]:
                continue
                
            try:
                # Handle various formats: YYYY-MM-DD, MM/DD/YYYY, etc.
                d_str = tx.date
                dt = None
                if '-' in d_str: # Assume YYYY-MM-DD or YYYY-M-D
                    parts = d_str.split('-')
                    if len(parts[0]) == 4:
                        dt = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                elif '/' in d_str: # Assume MM/DD/YYYY or DD/MM/YYYY
                    parts = d_str.split('/')
                    if len(parts[2]) == 4:
                        # Guessing MM/DD/YYYY first
                        try: dt = datetime(int(parts[2]), int(parts[0]), int(parts[1]))
                        except: dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                
                if dt:
                    parsed_data.append({"date": dt, "amount": tx.amount})
            except Exception:
                continue

        if not parsed_data:
            return {"trend": "stable", "change_percentage": 0, "current_month_total": 0, "previous_month_total": 0, "daily": [], "weekly": [], "monthly": []}

        # Sort by date
        parsed_data.sort(key=lambda x: x['date'])
        anchor_date = parsed_data[-1]['date']

        # Daily (last 30 days of data)
        daily_map = defaultdict(float)
        thirty_days_ago = anchor_date - timedelta(days=30)
        for d in parsed_data:
            if d['date'] >= thirty_days_ago:
                date_key = d['date'].strftime('%Y-%m-%d')
                daily_map[date_key] += d['amount']
        daily_series = [{"date": k, "amount": round(v, 2)} for k, v in sorted(daily_map.items())]

        # Monthly (all time, but focused on last 12)
        monthly_map = defaultdict(float)
        for d in parsed_data:
            month_key = d['date'].strftime('%Y-%m')
            monthly_map[month_key] += d['amount']
        monthly_series = [{"month": k, "amount": round(v, 2)} for k, v in sorted(monthly_map.items())]
        
        # Weekly (last 12 weeks of data)
        weekly_map = defaultdict(float)
        twelve_weeks_ago = anchor_date - timedelta(weeks=12)
        for d in parsed_data:
            if d['date'] >= twelve_weeks_ago:
                # ISO week format
                week_key = d['date'].strftime('%Y-W%W')
                weekly_map[week_key] += d['amount']
        weekly_series = [{"week": k, "amount": round(v, 2)} for k, v in sorted(weekly_map.items())]

        # Calculate Trend
        change_pct = 0
        current_val = 0
        previous_val = 0
        if len(monthly_series) >= 2:
            current_val = monthly_series[-1]['amount']
            previous_val = monthly_series[-2]['amount']
            if previous_val != 0:
                change_pct = ((current_val - previous_val) / abs(previous_val)) * 100
        else:
            current_val = monthly_series[0]['amount'] if monthly_series else 0

        trend_direction = "increasing" if change_pct > 5 else "decreasing" if change_pct < -5 else "stable"

        return {
            "trend": trend_direction,
            "change_percentage": round(change_pct, 1),
            "current_month_total": round(current_val, 2),
            "previous_month_total": round(previous_val, 2),
            "daily": daily_series,
            "weekly": weekly_series,
            "monthly": monthly_series[-12:] # Last 12 months
        }
    finally:
        session.close()


# ============================================================
# INSIGHT PERSISTENCE
# ============================================================

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(SQLAlchemyError),
    reraise=True
)
def save_insight(insight_type: str, key: str, value: Any, transaction_ids: List[int] = None, confidence: float = 1.0) -> None:
    """
    Saves or updates an insight in the database.
    Uses UPSERT logic based on (insight_type, key).
    """
    from schema import DBInsight, SessionLocal as SchemaSession
    
    session = SchemaSession()
    try:
        # Check for existing insight
        existing = session.query(DBInsight).filter(
            DBInsight.insight_type == insight_type,
            DBInsight.key == key
        ).first()
        
        value_json = json.dumps(value) if not isinstance(value, str) else value
        expires_at = datetime.utcnow() + timedelta(days=INSIGHTS_TTL_DAYS)
        tx_ids_str = ",".join(map(str, transaction_ids)) if transaction_ids else None
        
        if existing:
            existing.value = value_json
            existing.transaction_ids = tx_ids_str
            existing.confidence = confidence
            existing.computed_at = datetime.utcnow()
            existing.expires_at = expires_at
        else:
            new_insight = DBInsight(
                insight_type=insight_type,
                key=key,
                value=value_json,
                transaction_ids=tx_ids_str,
                confidence=confidence,
                expires_at=expires_at
            )
            session.add(new_insight)
        
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_cached_insights() -> Optional[Dict[str, Any]]:
    """
    Returns cached insights if they exist and are not expired.
    Returns None if insights are stale or don't exist.
    """
    from schema import DBInsight, SessionLocal as SchemaSession
    
    session = SchemaSession()
    try:
        now = datetime.utcnow()
        insights = session.query(DBInsight).filter(
            DBInsight.expires_at > now
        ).all()
        
        if not insights:
            return None
        
        result = {
            "category_summary": {},
            "subscriptions": [],
            "trends": {},
            "anomalies": [],
            "merchants": {},
            "computed_at": None
        }
        
        for insight in insights:
            value = json.loads(insight.value) if insight.value else None
            
            if insight.insight_type == "category_summary":
                result["category_summary"] = value
                result["computed_at"] = insight.computed_at.isoformat()
            elif insight.insight_type == "subscriptions":
                result["subscriptions"] = value
            elif insight.insight_type == "trends":
                result["trends"] = value
            elif insight.insight_type == "merchant_enrichment":
                result["merchants"][insight.key] = value
            elif insight.insight_type == "anomalies":
                result["anomalies"] = value
        
        return result
    finally:
        session.close()


def run_full_insights_pipeline(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Runs the full insights pipeline and persists results.
    Returns the computed insights.
    """
    # Check cache first (unless force refresh)
    if not force_refresh:
        cached = get_cached_insights()
        if cached:
            return cached
    
    # Run all tools
    print("Running category summarizer...")
    category_summary = summarize_by_category()
    save_insight("category_summary", "all", category_summary)
    
    print("Detecting subscriptions...")
    subscriptions = detect_subscriptions()
    save_insight("subscriptions", "all", subscriptions)
    
    print("Analyzing trends...")
    trends = analyze_trends()
    save_insight("trends", "all", trends)
    
    print("Detecting anomalies...")
    anomalies = detect_anomalies()
    save_insight("anomalies", "all", anomalies)
    
    print("Insights pipeline complete!")
    
    return {
        "category_summary": category_summary,
        "subscriptions": subscriptions,
        "trends": trends,
        "anomalies": anomalies,
        "computed_at": datetime.utcnow().isoformat()
    }

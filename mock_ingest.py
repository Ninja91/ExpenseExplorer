import os
from schema import init_db, save_transactions, Transaction

def mock_ingest():
    print("--- Expense Explorer Mock Ingestion ---")
    init_db()
    
    mock_transactions = [
        # Dining
        Transaction(date="2025-12-01", description="Starbucks", amount=5.75, category="Dining", location="Seattle, WA", source_file="mock_statement.pdf"),
        Transaction(date="2025-12-05", description="McDonald's", amount=12.50, category="Dining", location="San Francisco, CA", source_file="mock_statement.pdf"),
        Transaction(date="2025-12-15", description="Italian Bistro", amount=85.00, category="Dining", location="New York, NY", source_file="mock_statement.pdf"),
        
        # Groceries
        Transaction(date="2025-12-03", description="Whole Foods", amount=120.45, category="Groceries", location="Austin, TX", source_file="mock_statement.pdf"),
        Transaction(date="2025-12-10", description="Safeway", amount=45.20, category="Groceries", location="San Jose, CA", source_file="mock_statement.pdf"),
        
        # Travel
        Transaction(date="2025-12-08", description="Uber", amount=24.50, category="Travel", location="SF, CA", source_file="mock_statement.pdf"),
        Transaction(date="2025-12-20", description="United Airlines", amount=450.00, category="Travel", location="Online", source_file="mock_statement.pdf"),
        Transaction(date="2025-12-22", description="Hilton Hotels", amount=180.00, category="Travel", location="Chicago, IL", source_file="mock_statement.pdf"),
        
        # Shopping
        Transaction(date="2025-12-12", description="Amazon.com", amount=65.00, category="Shopping", location="Online", source_file="mock_statement.pdf"),
        Transaction(date="2025-12-24", description="Apple Store", amount=1299.00, category="Shopping", location="Palo Alto, CA", source_file="mock_statement.pdf"),
        
        # Utilities
        Transaction(date="2025-12-02", description="PG&E", amount=145.00, category="Utilities", location="SF, CA", source_file="mock_statement.pdf"),
        Transaction(date="2025-12-18", description="Comcast", amount=89.99, category="Utilities", location="Online", source_file="mock_statement.pdf"),
        
        # Services
        Transaction(date="2025-12-28", description="Netflix", amount=19.99, category="Services", location="Online", source_file="mock_statement.pdf"),
    ]
    
    save_transactions(mock_transactions)
    print(f"Successfully ingested {len(mock_transactions)} mock transactions.")

if __name__ == "__main__":
    mock_ingest()

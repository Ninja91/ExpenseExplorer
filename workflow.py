from tensorlake.applications import application, function, Image, File
import os
import sys
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(override=True)

from schema import Transaction, init_db, save_transactions, get_all_transactions, IngestionRequest
from extractor_logic import extract_transactions_agent, TransactionList

# Define the container image for the functions
image = Image(name="expense-explorer-v2")
image.run("pip install litellm google-generativeai pydantic sqlalchemy psycopg2-binary openai-agents python-dotenv requests tenacity")


@function(image=image, secrets=["TENSORLAKE_API_KEY", "GEMINI_API_KEY"])
def parse_statement(file: File) -> str:
    """Node that converts PDF (passed as File object) to Markdown."""
    from ingest import TensorLakeV2RESTClient
    
    client = TensorLakeV2RESTClient()
    
    print(f"Parsing file with content type {file.content_type}...")
    file_id = client.upload_content(file.content, content_type=file.content_type)
    markdown = client.parse_to_markdown(file_id)
    return markdown

@function(image=image, secrets=["TENSORLAKE_API_KEY", "GEMINI_API_KEY"])
def extract_transactions(markdown: str) -> TransactionList:
    """Node that uses Gemma 3 agent to extract transactions."""
    print("--- EXTRACTED OCR (MARKDOWN) ---")
    print(markdown)
    print("-------------------------------")
    print("Extracting transactions...")
    transaction_list = extract_transactions_agent(markdown)
    return transaction_list

@function(image=image, secrets=["DATABASE_URL"])
def persist_transactions(tx_list: TransactionList, filename: str) -> int:
    """Node that saves extracted transactions to the cloud database."""
    print(f"Persisting {len(tx_list.transactions)} transactions to database...")
    init_db()
    for tx in tx_list.transactions:
        tx.source_file = filename
    new_count = save_transactions(tx_list.transactions)
    print(f"Added {new_count} new transactions, skipped {len(tx_list.transactions) - new_count} duplicates.")
    return new_count


@application()
@function(image=image, secrets=["TENSORLAKE_API_KEY", "GEMINI_API_KEY", "DATABASE_URL"])
def expense_ingestion_app(request: IngestionRequest) -> int:
    """
    Ingests PDF statements, extracts transactions, and saves them to Neon Postgres.
    """
    import base64
    from tensorlake.applications import File
    
    file_bytes = base64.b64decode(request.file_b64)
    file_obj = File(content=file_bytes, content_type=request.content_type)
    
    markdown = parse_statement(file_obj)
    tx_list = extract_transactions(markdown)
    count = persist_transactions(tx_list, request.filename)
    return count

@application()
@function(image=image, secrets=["DATABASE_URL", "GEMINI_API_KEY"])
def expense_query_app(user_query: str) -> str:
    """
    Conversational agent that answers questions about expenses stored in the cloud database.
    """
    from agents import Agent, Runner, RunConfig
    
    print("Initialising database and ensuring schema is up to date...")
    init_db()
    
    print("Fetching data from cloud database...")
    transactions = get_all_transactions()
    
    if not transactions:
        return "No transactions found in the database. Please ingest some statements first."
        
    system_prompt = (
        "You are an ExpenseExplorer assistant. You have access to a list of financial transactions "
        "extracted from statements and stored in a Neon Postgres database.\n\n"
        f"DATA CONTEXT:\n{len(transactions)} transactions found.\n"
        "Columns: [date, description, amount, category, location, source_file, merchant, is_subscription, payment_method, tags, currency, raw_description, transaction_type, reference_number, account_last_4, provider_name].\n"
        "Amount is positive for expenses, negative for refunds/payments.\n\n"
        "Note: 'Credit Card Payment' and 'Internal Transfer' are specific categories for financial moves that shouldn't typically count as new spending.\n\n"
        "TASK:\n"
        "Answer the user's question based on the provided transaction data.\n"
        "FORMATTING RULES:\n"
        "1. Use **Markdown** for all responses.\n"
        "2. If listing multiple transactions, ALWAYS use a **Markdown Table**.\n"
        "3. Use bold text for key figures and summaries.\n"
        "4. Be concise, structured, and professional."
    )
    
    agent = Agent(
        name="ExpenseQueryExplorer",
        model="litellm/gemini/gemini-3-flash-preview",
        instructions=system_prompt
    )
    
    run_config = RunConfig(tracing_disabled=True)
    print(f"Querying Gemini-3-Flash with {len(transactions)} items...")
    
    prompt = f"Data: {transactions}\n\nUser Question: {user_query}"
    result = Runner.run_sync(agent, prompt, run_config=run_config)
    return result.final_output

@application()
@function(image=image, secrets=["DATABASE_URL", "GEMINI_API_KEY"])
def insights_app(force_refresh: bool = False) -> dict:
    """
    Runs the Insights Engine to analyze transactions and persist insights.
    Returns category summaries, subscriptions, and trends.
    """
    from insights_logic import run_full_insights_pipeline, init_insights_table
    
    print("Initializing insights table...")
    init_insights_table()
    
    print(f"Running insights pipeline (force_refresh={force_refresh})...")
    insights = run_full_insights_pipeline(force_refresh=force_refresh)
    
    return insights

# Endpoints for deployment
ingest_app = expense_ingestion_app
query_app = expense_query_app
insights = insights_app

if __name__ == "__main__":
    print("This file contains TensorLake application definitions.")
    print("Use the CLI to deploy:")
    print("  tensorlake deploy workflow.py")

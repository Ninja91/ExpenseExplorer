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
image.run("pip install litellm google-genai pydantic sqlalchemy psycopg2-binary openai-agents python-dotenv requests tenacity pandas numpy google-adk nest-asyncio \"protobuf>=6.0\"")


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
    """Node that saves extracted transactions and statement metadata to the cloud database."""
    from schema import init_db, save_transactions, save_statement_metadata
    print(f"Persisting {len(tx_list.transactions)} transactions and metadata for {filename}...")
    init_db()
    
    # Save statement summary if available
    if tx_list.summary:
        print(f"Saving statement metadata: {tx_list.summary}")
        save_statement_metadata(filename, tx_list.summary)
        
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
    Conversational agent that answers questions about expenses using a Python tool.
    """
    from query_agent import run_query
    
    try:
        print(f"Querying Gemini 2.5 Flash Agent (ADK) with query: {user_query}")
        result = run_query(user_query)
        return result
    except Exception as e:
        import traceback
        error_msg = f"Error in expense_query_app: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return error_msg

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

@application()
@function(image=image, secrets=["DATABASE_URL"])
def force_migrate_app(force: bool = True) -> str:
    """Aggressively forces the database schema to match the current models."""
    from schema import init_db
    try:
        logs = init_db()
        return "\n".join(logs)
    except Exception as e:
        return f"Migration failed: {str(e)}"

# Endpoints for deployment
ingest_app = expense_ingestion_app
query_app = expense_query_app
insights = insights_app
migrate = force_migrate_app

if __name__ == "__main__":
    print("This file contains TensorLake application definitions.")
    print("Use the CLI to deploy:")
    print("  tensorlake deploy workflow.py")

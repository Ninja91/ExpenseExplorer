import os
import sys
from typing import List
from pydantic import BaseModel
from tensorlake import Graph, RemoteGraph, tensorlake_function, Image
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(override=True)

from schema import Transaction
from extractor_logic import extract_transactions_agent, TransactionList

# Define the container image for the functions
image = Image().name("expense-explorer-v1")
image.run("pip install litellm google-generativeai pydantic openai-agents python-dotenv requests")

@tensorlake_function(image=image)
def parse_statement(file_path: str) -> str:
    """Node that converts PDF to Markdown using TensorLake REST API."""
    from ingest import TensorLakeV2RESTClient
    
    client = TensorLakeV2RESTClient()
    
    print(f"Parsing {file_path}...")
    file_id = client.upload(file_path)
    markdown = client.parse_to_markdown(file_id)
    return markdown

@tensorlake_function(image=image)
def extract_transactions(markdown: str) -> TransactionList:
    """Node that uses Gemma 3 agent to extract transactions."""
    print("Extracting transactions...")
    transaction_list = extract_transactions_agent(markdown)
    return transaction_list

# --- Global Graph Definition for CLI ---
graph = Graph(
    name="expense_ingestion",
    start_node=parse_statement,
    description="Ingests PDF statements and extracts structured transactions into the TensorLake Knowledge Graph."
)
graph.add_edge(parse_statement, extract_transactions)
# ----------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  tensorlake deploy workflow.py  # To deploy")
        print("  python workflow.py ingest <file_path>  # To ingest locally")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "ingest":
        if len(sys.argv) < 3:
            print("Error: Missing file path.")
            print("Usage: python workflow.py ingest <file_path>")
            sys.exit(1)
            
        file_path = sys.argv[2]
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            sys.exit(1)
            
        print(f"Running ingestion for {file_path}...")
        # For remote graphs, we would use client.invocations.create, but here we run the graph definition
        # Locally this runs synchronously
        invocation_id = graph.run(file_path=file_path)
        print(f"Invocation ID: {invocation_id}")
        
        # Verify output locally
        outputs = graph.output(invocation_id, "extract_transactions")
        if outputs:
            tx_list = outputs[0]
            print(f"Successfully extracted {len(tx_list.transactions)} transactions.")
    else:
        # If user tries 'deploy' with python script, guide them to CLI
        if command == "deploy":
            print("To deploy, please use the TensorLake CLI:")
            print("  tensorlake deploy workflow.py")
        else:
            print(f"Unknown command: {command}")

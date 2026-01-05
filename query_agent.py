import os
from dotenv import load_dotenv
load_dotenv(override=True)

import sqlite3
import sys
from typing import List, Dict, Any
from agents import Agent, Runner, function_tool, RunConfig

# litellm expects GOOGLE_API_KEY or GEMINI_API_KEY
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

from tensorlake import TensorlakeClient
import sys
from typing import List, Dict, Any
from agents import Agent, Runner, RunConfig
from workflow import TransactionList # Import for type reference if needed

def get_transactions_from_kg() -> List[Dict[str, Any]]:
    """Fetch all extracted transactions from the TensorLake Knowledge Graph."""
    # Use the specific project namespace provided by user
    namespace = "org_kBzG9mbrrbcWJQwfbC9nf/projects/project_8LLcJp9qpdjfnDHRTPpnM"
    client = TensorlakeClient(namespace=namespace)
    graph_name = "expense_ingestion"
    
    all_transactions = []
    try:
        # 1. Get all successful invocations for this graph
        invocations = client.invocations(graph_name)
        print(f"Found {len(invocations)} invocations in TensorLake.")
        
        for inv in invocations:
            # 2. Fetch the output of the 'extract_transactions' node
            # Based on the graph: start -> parse -> extract
            outputs = client.graph_outputs(graph_name, inv.invocation_id, "extract_transactions")
            for out in outputs:
                # 'out' should be a TransactionList (Pydantic model)
                if hasattr(out, 'transactions'):
                    for tx in out.transactions:
                        all_transactions.append({
                            "date": tx.date,
                            "description": tx.description,
                            "amount": tx.amount,
                            "category": tx.category,
                            "location": tx.location,
                            "source_file": tx.source_file
                        })
    except Exception as e:
        print(f"Error fetching from TensorLake: {e}")
        return []
        
    return all_transactions

def query_expenses(user_query: str) -> str:
    """
    Agentic interface that queries the TensorLake Knowledge Graph.
    Retrieves all transactions and analyzes them using Gemma 3.
    """
    transactions = get_transactions_from_kg()
    
    if not transactions:
        return "No transactions found in the Knowledge Graph. Please ingest some statements first."
        
    system_prompt = (
        "You are an ExpenseExplorer assistant. You have access to a list of financial transactions "
        "extracted from statements and stored in the TensorLake Knowledge Graph.\n\n"
        f"DATA CONTEXT:\n{len(transactions)} transactions found.\n"
        "Columns: [date, description, amount, category, location, source_file].\n"
        "Amount is positive for expenses, negative for refunds/payments.\n\n"
        "TASK:\n"
        "Answer the user's question based on the provided transaction data. "
        "Be concise and accurate."
    )
    
    agent = Agent(
        name="ExpenseExplorer",
        model="litellm/gemini/gemma-3-27b-it",
        instructions=system_prompt
    )
    
    run_config = RunConfig(tracing_disabled=True)
    
    print(f"Querying Gemma 3 with Knowledge Graph data ({len(transactions)} items)...")
    
    # We pass the data in the prompt for simplicity in this POC version.
    # For very large datasets, we would implement a real vector or SQL tool.
    prompt = f"Data: {transactions}\n\nUser Question: {user_query}"
    
    result = Runner.run_sync(agent, prompt, run_config=run_config)
    return result.final_output

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print("\n--- Querying Expense Explorer ---")
        response = query_expenses(query)
        print("\n--- Response ---")
        print(response)
    else:
        print("Usage: python query_agent.py 'How much did I spend on dining in December?'")

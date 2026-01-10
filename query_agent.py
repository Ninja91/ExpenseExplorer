from tensorlake.applications import run_remote_application
import sys
import os
from dotenv import load_dotenv

load_dotenv(override=True)

def query_expenses(user_query: str) -> str:
    """
    Agentic interface that invokes the remote 'query_app' on TensorLake Cloud.
    """
    print(f"--- Querying Expense Explorer (Cloud-Native) ---")
    
    try:
        # run_remote_application returns a RemoteRequest object with positional payload
        print(f"Invoking expense_query_app with: '{user_query}'")
        request = run_remote_application("expense_query_app", user_query)
        print(f"Request started. ID: {request.id}")
        
        print("Waiting for response from Gemma 3 in the cloud...")
        # .output() waits for completion and deserializes the string result
        response = request.output()
        return response
            
    except Exception as e:
        print(f"Error during remote query: {e}")
        import traceback
        traceback.print_exc()
        return f"Query failed: {e}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        print("\n--- Starting Remote Query ---")
        response = query_expenses(query)
        print("\n--- Response ---")
        print(response)
    else:
        print("Usage: python query_agent.py 'How much did I spend on dining in December?'")

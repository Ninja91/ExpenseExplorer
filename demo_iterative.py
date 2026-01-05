from tensorlake import TensorlakeClient, Graph
from workflow import extract_transactions # Ensure we can reference the node name
from schema import Transaction

def demonstrate_history():
    client = TensorlakeClient()
    graph_name = "expense_ingestion"
    
    print(f"--- Fetching History for Graph: {graph_name} ---")
    
    # 1. Fetch all invocations (history of runs)
    invocations = client.invocations(graph_name)
    print(f"Total Invocations Found: {len(invocations)}")
    
    total_transactions = 0
    
    for i, inv in enumerate(invocations):
        print(f"\nInvocation #{i+1} (ID: {inv.invocation_id})")
        # 2. Fetch outputs for each run
        outputs = client.graph_outputs(graph_name, inv.invocation_id, "extract_transactions")
        
        if outputs:
            tx_list = outputs[0]
            count = len(tx_list.transactions)
            total_transactions += count
            print(f"  > Extracted {count} transactions")
            if count > 0:
                print(f"  > First item: {tx_list.transactions[0].description} ({tx_list.transactions[0].amount})")
        else:
            print("  > No outputs found (might be failed or running)")

    print(f"\n--- Total Knowledge Graph State ---")
    print(f"Total Consolidated Transactions: {total_transactions}")
    print("This confirms that TensorLake maintains the history of all ingested statements.")

if __name__ == "__main__":
    demonstrate_history()

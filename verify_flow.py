from tensorlake.applications import run_remote_application, File
import os
from dotenv import load_dotenv
from schema import init_db, save_transactions

load_dotenv(override=True)

import glob
from schema import IngestionRequest

def verify():
    print("--- Cloud-Native Batch Ingestion Verification ---")
    
    statement_dir = "/Users/nitinjain/Downloads/Credit_Card_Statements"
    statement_files = glob.glob(os.path.join(statement_dir, "*.pdf"))
    
    if not statement_files:
        print(f"No PDF statements found in {statement_dir}")
        return

    print(f"Found {len(statement_files)} PDF statements to process.")
    
    results = {}

    for test_file in statement_files:
        filename = os.path.basename(test_file)
        print(f"\n--- Processing {filename} ---")
        
        try:
            print(f"Loading {filename} as raw bytes and encoding to Base64...")
            import base64
            with open(test_file, "rb") as f:
                content_b64 = base64.b64encode(f.read()).decode("utf-8")

            print(f"Invoking expense_ingestion_app for {filename}...")
            # Use the Base64 refactored IngestionRequest model
            req = IngestionRequest(file_b64=content_b64, content_type="application/pdf", filename=filename)
            request = run_remote_application("expense_ingestion_app", req)
            print(f"Request started. ID: {request.id}")
            
            print("Waiting for completion and fetching output...")
            count = request.output()
            
            print(f"Successfully processed {filename}. Extracted and saved {count} transactions to Neon Postgres.")
            results[filename] = f"Success: {count} transactions"
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            results[filename] = f"Error: {str(e)}"

    print("\n" + "="*40)
    print("CLOUD BATCH SUMMARY")
    print("="*40)
    for file, status in results.items():
        print(f"{file: <40} | {status}")
    print("="*40)

if __name__ == "__main__":
    verify()

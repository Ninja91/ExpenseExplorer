import os
from dotenv import load_dotenv
load_dotenv(override=True)

import glob
import time
import requests
from extractor_logic import extract_transactions_agent
from schema import init_db, save_transactions, Transaction

class TensorLakeV2RESTClient:
    """Simple REST client for TensorLake v2 API specifically for parsing."""
    def __init__(self):
        self.api_key = os.getenv("TENSORLAKE_API_KEY")
        self.base_url = "https://api.tensorlake.ai/documents/v2"
        if not self.api_key:
            raise ValueError("TENSORLAKE_API_KEY not found in environment")

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def upload(self, file_path: str) -> str:
        """Upload a local file and return the file_id."""
        url = f"{self.base_url}/files"
        print(f"  Uploading {file_path}...")
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            response = requests.post(url, headers=self._headers(), files=files, timeout=30)
            print(f"  Upload response: {response.status_code}")
            response.raise_for_status()
            file_id = response.json().get("file_id")
            print(f"  File ID: {file_id}")
            return file_id

    def parse_to_markdown(self, file_id: str) -> str:
        """Parse a file to Markdown and wait for completion."""
        url = f"{self.base_url}/parse"
        payload = {
            "file_id": file_id,
            "parsing_options": {
                "chunking_strategy": "page"
            }
        }
        
        print(f"  Requesting parse for {file_id}...")
        response = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        print(f"  Parse request response: {response.status_code}")
        response.raise_for_status()
        parse_id = response.json().get("parse_id")
        
        print(f"Waiting for parsing job {parse_id}...")
        max_wait = 120 
        while max_wait > 0:
            result_url = f"{self.base_url}/parse/{parse_id}"
            result_response = requests.get(result_url, headers=self._headers(), timeout=30)
            
            if result_response.status_code == 200:
                data = result_response.json()
                status = data.get("status")
                print(f"  Parsing status: {status} (waited {120 - max_wait}s)")
                
                if status == "successful":
                    types_seen = set()
                    for page in data.get("pages", []):
                        for fragment in page.get("page_fragments", []):
                            types_seen.add(fragment.get("fragment_type"))
                    print(f"  Fragment types found: {types_seen}")
                    
                    full_md = ""
                    for page in data.get("pages", []):
                        for fragment in page.get("page_fragments", []):
                            f_type = fragment.get("fragment_type")
                            content = fragment.get("content", {}).get("content", "")
                            if f_type in ["text", "table", "list"]:
                                full_md += f_type.upper() + ":\n" + content + "\n\n"
                    return full_md
                elif status in ["failed", "failure"]:
                    print(f"  Full response data: {data}")
                    raise Exception(f"Parsing failed with status {status}: {data.get('error', 'No error message')}")
            else:
                print(f"  Warning: Polling status code {result_response.status_code}")
            
            time.sleep(5)
            max_wait -= 5
        
        raise TimeoutError("Parsing job timed out")

def process_statements():
    print("--- Expense Explorer Ingestion Pipeline (Gemini-Powered) ---")
    init_db()
    client = TensorLakeV2RESTClient()
    
    statement_dir = os.path.expanduser("~/Downloads/Credit_Card_Statements")
    statement_files = glob.glob(os.path.join(statement_dir, "*.pdf"))
    
    if not statement_files:
        print(f"No PDF statements found in {statement_dir}")
        return

    for file_path in statement_files:
        filename = os.path.basename(file_path)
        print(f"\nProcessing {filename}...")
        
        try:
            # 1. Parse to Markdown
            print(f"[{filename}] Uploading and parsing...")
            file_id = client.upload(file_path)
            markdown = client.parse_to_markdown(file_id)
            print(f"[{filename}] Received Markdown (length: {len(markdown)})")
            with open("debug_statement.md", "w") as f:
                f.write(markdown)
            print(f"[{filename}] Saved Markdown to debug_statement.md")
            if len(markdown) < 100:
                print(f"[{filename}] WARNING: Markdown looks too short:\n{markdown}")
            
            # 2. Extract using Gemini
            print(f"[{filename}] Extracting transactions using Gemini Agent...")
            
            # Add retry logic for Gemini rate limits (RESOURCE_EXHAUSTED)
            max_retries = 3
            retry_delay = 30 # Longer delay for free tier
            result = None
            
            for attempt in range(max_retries):
                try:
                    result = extract_transactions_agent(markdown)
                    break 
                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        print(f"  Rate limited (429/RESOURCE_EXHAUSTED). Retrying in {retry_delay}s... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        raise e
            
            # 3. Save
            if result and result.transactions:
                for tx in result.transactions:
                    tx.source_file = filename
                
                save_transactions(result.transactions)
                print(f"[{filename}] Successfully extracted and saved {len(result.transactions)} transactions.")
            else:
                print(f"[{filename}] No transactions extracted for {filename}.")
                
        except Exception as e:
            import traceback
            print(f"[{filename}] Error: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    process_statements()

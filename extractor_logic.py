import os
from dotenv import load_dotenv
load_dotenv(override=True)

from agents import Agent, Runner, RunConfig
from pydantic import BaseModel
from typing import List
from schema import Transaction

# litellm expects GOOGLE_API_KEY or GEMINI_API_KEY
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

class TransactionList(BaseModel):
    transactions: List[Transaction]

def extract_transactions_agent(markdown_content: str) -> TransactionList:
    """
    Extracts high-fidelity structured transactions from a financial statement.
    Uses Gemini-3-Flash for fast and accurate extraction.
    """
    extractor = Agent(
        name="TransactionExtractor",
        model="litellm/gemini/gemini-3-flash-preview",
        instructions=(
            "You are an expert financial analyst. Extract all individual transactions from the provided markdown content.\n\n"
            "CATEGORIES:\n"
            "- Dining, Groceries, Travel, Shopping, Utilities, Services, Rent, Credit Card Payment, Internal Transfer, Miscellaneous.\n\n"
            "FIELDS TO EXTRACT:\n"
            "- date: YYYY-MM-DD format.\n"
            "- description: A concise, cleaned merchant or transaction name.\n"
            "- raw_description: The EXACT unmodified description string from the statement.\n"
            "- amount: Float (positive for expenses, negative for refunds/payments/credits).\n"
            "- category: Choose the best fit from the CATEGORIES list. Note: Bill payments to credit cards must be 'Credit Card Payment'.\n"
            "- transaction_type: One of: Debit, Credit, Transfer, Payment.\n"
            "- location: City/State if available.\n"
            "- merchant: A cleaned, human-readable merchant name.\n"
            "- is_subscription: Boolean. True if the transaction appears to be a revolving subscription.\n"
            "- reference_number: Transaction reference or ID if present.\n"
            "- account_last_4: Last 4 digits of the account or card associated with the transaction.\n"
            "- provider_name: Name of the bank or financial institution (e.g., Chase, Amex, Well Fargo).\n"
            "- payment_method: Detailed card type (e.g., 'Visa Infinite', 'Amex Gold') if visible.\n"
            "- tags: Comma-separated tags for additional context.\n"
            "- currency: The 3-letter currency code (default: 'USD').\n\n"
            "OUTPUT FORMAT:\n"
            "You must output ONLY a valid JSON block:\n"
            "```json\n"
            "{\"transactions\": [{\n"
            "  \"date\": \"...\", \"description\": \"...\", \"raw_description\": \"...\", \"amount\": 0.0, \"category\": \"...\",\n"
            "  \"transaction_type\": \"...\", \"location\": \"...\", \"merchant\": \"...\", \"is_subscription\": false,\n"
            "  \"reference_number\": \"...\", \"account_last_4\": \"...\", \"provider_name\": \"...\",\n"
            "  \"payment_method\": \"...\", \"tags\": \"...\", \"currency\": \"...\"\n"
            "}]}\n"
            "```"
        )
    )

    prompt = f"Please extract all transactions from the following statement content:\n\n{markdown_content}"
    
    print(f"Running extraction via Gemma 3-27b-it (markdown length: {len(markdown_content)})...")
    run_config = RunConfig(tracing_disabled=True)
    result = Runner.run_sync(extractor, prompt, run_config=run_config)
    
    print(f"Raw agent response:\n{result.final_output}")
    
    # Manually parse JSON from result
    import re
    import json
    json_match = re.search(r"```json\n(.*?)\n```", result.final_output, re.DOTALL)
    if not json_match:
        # Fallback to looking for { ... }
        json_match = re.search(r"(\{.*\})", result.final_output, re.DOTALL)
        
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
            return TransactionList.parse_obj(data)
        except Exception as e:
            print(f"Error parsing JSON from agent: {e}")
            print(f"Raw output: {result.final_output}")
            raise e
    else:
        print(f"No JSON found in agent output: {result.final_output}")
        return TransactionList(transactions=[])

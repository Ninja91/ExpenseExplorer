import os
from dotenv import load_dotenv
load_dotenv(override=True)

from agents import Agent, Runner, RunConfig
from pydantic import BaseModel
from typing import List
from schema import Transaction, StatementMetadata

# litellm expects GOOGLE_API_KEY or GEMINI_API_KEY
if os.getenv("GEMINI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

class TransactionList(BaseModel):
    summary: StatementMetadata | None = None
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
            "You are an expert financial analyst. Extract all individual transactions and statement-level summary metadata from the provided markdown content.\n\n"
            "CATEGORIES:\n"
            "- Dining, Groceries, Travel, Shopping, Utilities, Services, Rent, Credit Card Payment, Internal Transfer, Miscellaneous.\n\n"
            "STATEMENT SUMMARY FIELDS:\n"
            "- period_start: Opening date of statement cycle (YYYY-MM-DD).\n"
            "- period_end: Closing date of statement cycle (YYYY-MM-DD).\n"
            "- opening_balance: Balance at start of cycle.\n"
            "- closing_balance: Balance at end of cycle.\n"
            "- total_credits: Sum of all credits/payments.\n"
            "- total_debits: Sum of all debits/expenses.\n\n"
            "TRANSACTION FIELDS:\n"
            "- date: YYYY-MM-DD format.\n"
            "- description: A concise, cleaned merchant or transaction name.\n"
            "- raw_description: The EXACT unmodified description string.\n"
            "- amount: Float (positive for expenses, negative for refunds/payments/credits).\n"
            "- category: Choose from CATEGORIES list.\n"
            "- transaction_type: Debit, Credit, Transfer, Payment.\n"
            "- is_essential: Boolean. True if the transaction is a non-discretionary need (Rent, Basic Groceries, Utilities, Insurance, Medical).\n"
            "- tax_category: One of (Supplies, Travel, Meals, Services, Utilities, Rent, Interest, Other, Personal).\n"
            "- confidence: Float (0.0 to 1.0) representing your certainty in the extraction.\n"
            "- location, merchant, is_subscription, reference_number, account_last_4, provider_name, payment_method, tags, currency.\n\n"
            "OUTPUT FORMAT:\n"
            "You must output ONLY a valid JSON block:\n"
            "```json\n"
            "{\n"
            "  \"summary\": {\n"
            "    \"provider_name\": \"...\", \"account_last_4\": \"...\", \"period_start\": \"...\", \"period_end\": \"...\",\n"
            "    \"opening_balance\": 0.0, \"closing_balance\": 0.0, \"total_credits\": 0.0, \"total_debits\": 0.0\n"
            "  },\n"
            "  \"transactions\": [{\n"
            "    \"date\": \"...\", \"description\": \"...\", \"raw_description\": \"...\", \"amount\": 0.0, \"category\": \"...\",\n"
            "    \"transaction_type\": \"...\", \"is_essential\": true, \"tax_category\": \"...\", \"confidence\": 0.95,\n"
            "    \"location\": \"...\", \"merchant\": \"...\", \"is_subscription\": false,\n"
            "    \"reference_number\": \"...\", \"account_last_4\": \"...\", \"provider_name\": \"...\",\n"
            "    \"payment_method\": \"...\", \"tags\": \"...\", \"currency\": \"...\"\n"
            "  }]\n"
            "}\n"
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

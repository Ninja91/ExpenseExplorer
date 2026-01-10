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
        model="litellm/gemini/gemini-3-flash",
        instructions=(
            "You are an expert financial analyst. Extract all individual transactions from the provided markdown content.\n\n"
            "FIELDS TO EXTRACT:\n"
            "- date: YYYY-MM-DD format.\n"
            "- description: The original line item description.\n"
            "- amount: Float (positive for expenses, negative for refunds/payments).\n"
            "- category: One of: Dining, Groceries, Travel, Shopping, Utilities, Services, Rent, Miscellaneous.\n"
            "- location: City/State if available.\n"
            "- merchant: A cleaned, human-readable merchant name (e.g., 'Uber' instead of 'UBER *TRIP HELP.UBER.COM').\n"
            "- is_subscription: Boolean. True if the transaction appears to be a recurring subscription (Netflix, Spotify, Gym, etc.).\n"
            "- payment_method: The card type or payment mode if visible (e.g., 'Visa', 'Amex').\n"
            "- tags: Comma-separated tags for additional context (e.g., 'Dining Out', 'Electronics').\n"
            "- currency: The 3-letter currency code (default: 'USD').\n\n"
            "OUTPUT FORMAT:\n"
            "You must output ONLY a valid JSON block:\n"
            "```json\n"
            "{\"transactions\": [{\n"
            "  \"date\": \"...\", \"description\": \"...\", \"amount\": 0.0, \"category\": \"...\",\n"
            "  \"location\": \"...\", \"merchant\": \"...\", \"is_subscription\": false,\n"
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

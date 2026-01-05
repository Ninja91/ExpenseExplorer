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
    Extracts structured transactions from a financial statement in Markdown format.
    Uses Gemma-3-27b-it with manual JSON parsing (since it doesn't support JSON mode yet).
    """
    extractor = Agent(
        name="TransactionExtractor",
        model="litellm/gemini/gemma-3-27b-it",
        instructions=(
            "You are an expert at extracting financial data from bank and credit card statements. "
            "Given the markdown content of a statement, extract all individual transactions. "
            "Ensure 'date' is in YYYY-MM-DD format. "
            "Ensure 'amount' is a number (positive for expenses, negative for refunds/payments). "
            "Categorize each transaction into one of: Dining, Groceries, Travel, Shopping, Utilities, Services, Miscellaneous.\n\n"
            "OUTPUT FORMAT:\n"
            "You must output ONLY a valid JSON block containing the list of transactions, like this:\n"
            "```json\n"
            "{\"transactions\": [{\"date\": \"...\", \"description\": \"...\", \"amount\": 10.0, \"category\": \"...\", \"location\": \"...\"}]}\n"
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

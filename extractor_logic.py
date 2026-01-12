import os
import json
import re
import asyncio
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List
from schema import Transaction, StatementMetadata
from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types

load_dotenv(override=True)

# Ensure API keys are accessible
if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

class TransactionList(BaseModel):
    summary: StatementMetadata | None = None
    transactions: List[Transaction]

def _run_async_logic(runner, new_message, user_id, session_id):
    """Bridge to collect events from the async runner logic."""
    full_output = []
    
    async def _collect():
        from google.adk.utils.context_utils import Aclosing
        async with Aclosing(runner.run_async(user_id=user_id, session_id=session_id, new_message=new_message)) as agen:
            async for event in agen:
                if event.content and event.content.parts:
                    text = "".join(p.text for p in event.content.parts if p.text)
                    if text:
                        full_output.append(text)
    
    import nest_asyncio
    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(_collect())
    return "".join(full_output)

def extract_transactions_agent(markdown_content: str) -> TransactionList:
    """
    Extracts high-fidelity structured transactions from a financial statement.
    Uses Google ADK and Gemini-2.5-Flash-Lite for robust extraction.
    """
    extractor = Agent(
        name="TransactionExtractor",
        model="gemini-2.5-flash",
        instruction=(
            "You are an expert financial analyst. Extract all individual transactions and statement-level summary metadata from the provided markdown content.\n\n"
            "CATEGORIES:\n"
            "- Dining, Groceries, Travel, Shopping, Utilities, Services, Rent, Credit Card Payment, Internal Transfer, Miscellaneous.\n\n"
            "TRANSACTION FIELDS (REQUIRED):\n"
            "- date: YYYY-MM-DD format.\n"
            "- description: The original or slightly cleaned transaction text from the statement.\n"
            "- amount: Float.\n"
            "- category: Choose from CATEGORIES list.\n\n"
            "TRANSACTION FIELDS (OPTIONAL):\n"
            "- merchant: The cleaned name of the business.\n"
            "- location: City/State if found.\n"
            "- transaction_type: Debit, Credit, etc.\n\n"
            "OUTPUT FORMAT:\n"
            "You must output ONLY a valid JSON block containing 'summary' and 'transactions' list. Ensure every transaction has a 'description' field."
        )
    )

    runner = InMemoryRunner(agent=extractor)
    
    # Create session using the runner's app_name to ensure consistency
    import nest_asyncio
    nest_asyncio.apply()
    loop = asyncio.get_event_loop()
    session = loop.run_until_complete(runner.session_service.create_session(user_id="ingest_user", app_name=runner.app_name))

    prompt = f"Please extract all transactions from the following statement content:\n\n{markdown_content}"
    new_message = types.Content(role="user", parts=[types.Part(text=prompt)])
    
    print(f"Running extraction via Google ADK (Gemini 2.5 Flash)...")
    combined_result = _run_async_logic(runner, new_message, session.user_id, session.id)
    
    # Manually parse JSON from result
    json_match = re.search(r"```json\n(.*?)\n```", combined_result, re.DOTALL)
    if not json_match:
        json_match = re.search(r"(\{.*\})", combined_result, re.DOTALL)
        
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip())
            return TransactionList.model_validate(data)
        except Exception as e:
            print(f"Error parsing JSON from ADK agent: {e}\nRaw output: {combined_result}")
            raise e
    else:
        print(f"No JSON found in ADK agent output: {combined_result}")
        return TransactionList(transactions=[])

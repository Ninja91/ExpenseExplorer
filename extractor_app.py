from tensorlake.applications import application, function
from agents import Agent, Runner
from pydantic import BaseModel
from typing import List
from schema import Transaction
import os

class TransactionList(BaseModel):
    transactions: List[Transaction]

@application()
@function()
def extract_transactions(markdown_content: str) -> TransactionList:
    """
    Extracts structured transactions from a financial statement in Markdown format.
    Uses Gemini-2.0-Flash for high-accuracy extraction.
    """
    extractor = Agent(
        name="TransactionExtractor",
        model="gemini-2.0-flash",
        output_type=TransactionList,
        instructions=(
            "You are an expert at extracting financial data from bank and credit card statements. "
            "Given the markdown content of a statement, extract all individual transactions. "
            "Ensure 'date' is in YYYY-MM-DD format. "
            "Ensure 'amount' is a number (positive for expenses). "
            "Categorize each transaction into one of: Dining, Groceries, Travel, Shopping, Utilities, Services, Miscellaneous."
        )
    )

    prompt = f"Please extract all transactions from this statement content:\n\n{markdown_content}"
    
    # Run the agentic extraction flow
    result = Runner.run_sync(extractor, prompt)
    return result.final_output

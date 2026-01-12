import os
import io
import contextlib
import asyncio
import pandas as pd
import numpy as np
from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types
from schema import get_all_transactions, init_db

# Ensure API keys are accessible
if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

class PythonInterpreter:
    def __init__(self, df: pd.DataFrame):
        self.df = df

    def execute_python(self, code: str) -> str:
        """
        Executes a Python code block against a pandas DataFrame 'df' containing transaction data.
        Always use print() to output the results you need.
        
        Args:
          code: The python code to execute as a string.
        """
        print(f"DEBUG: ADK Tool Executing Python...\nCode:\n{code}")
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                # Provide df, pd, np to the execution context
                local_vars = {"df": self.df, "pd": pd, "np": np}
                exec(code, {}, local_vars)
            result = output.getvalue().strip()
            print(f"DEBUG: ADK Tool Result: {result}")
            return result or "Code executed successfully (no output)."
        except Exception as e:
            error_msg = f"Error executing Python: {str(e)}"
            print(f"DEBUG: ADK Tool {error_msg}")
            return error_msg

def get_query_agent():
    """
    Initializes and returns the Programmable Query Agent with Google ADK.
    """
    init_db()
    transactions = get_all_transactions()
    tx_dicts = transactions if transactions else []
    df = pd.DataFrame(tx_dicts)
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    
    interpreter = PythonInterpreter(df)
    
    system_prompt = (
        "You are an expert Financial Data Analyst. You have access to a pandas DataFrame named 'df' containing expense data.\n\n"
        "DATAFRAME STRUCTURE ('df'):\n"
        f"- {len(df)} rows found.\n"
        "- Columns: [date (datetime), description, amount (float), category, location, merchant, is_subscription, payment_method, raw_description, transaction_type, account_last_4, provider_name, is_essential, tax_category].\n"
        "- Note: 'amount' is positive for costs/spending, negative for refunds/income.\n\n"
        "INSTRUCTIONS:\n"
        "1. Prefer the 'execute_python' tool for ANY calculations, aggregations, or time-series analysis.\n"
        "2. When using Python, always print() the final result so you can see it.\n"
        "3. Provide your final answer in Markdown format."
    )
    
    agent = Agent(
        name="ProgrammableQueryAgent",
        model="gemini-2.5-flash",
        instruction=system_prompt,
        tools=[interpreter.execute_python]
    )
    
    return agent

async def _get_adk_response(runner, query: str):
    # Create session using runner.app_name
    session = await runner.session_service.create_session(user_id="query_user", app_name=runner.app_name)
    
    new_message = types.Content(
        role="user",
        parts=[types.Part(text=query)]
    )
    
    full_output = []
    from google.adk.utils.context_utils import Aclosing
    async with Aclosing(runner.run_async(user_id=session.user_id, session_id=session.id, new_message=new_message)) as agen:
        async for event in agen:
            if event.content and event.content.parts:
                text = "".join(p.text for p in event.content.parts if p.text)
                if text:
                    full_output.append(text)
    
    return "".join(full_output)

def run_query(query: str) -> str:
    """
    High-level function to run a query through the ADK agent.
    Handles async internals.
    """
    agent = get_query_agent()
    runner = InMemoryRunner(agent=agent)
    print(f"Running ADK agent (Gemini 2.5 Flash) with query: {query}")
    
    try:
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_get_adk_response(runner, query))
    except Exception as e:
        import traceback
        print(f"ADK Execution Error: {e}\n{traceback.format_exc()}")
        return f"Error executing query: {str(e)}"

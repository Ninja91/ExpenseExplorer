import os
import io
import contextlib
import asyncio
import pandas as pd
import numpy as np
from google.adk.agents.llm_agent import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types
from sqlalchemy import text
from schema import SessionLocal, init_db

# Ensure API keys are accessible
if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

class DatabaseExplorer:
    """Tool to execute SQL queries and explore database schema."""
    
    def get_schema(self) -> str:
        """Returns the schema of the 'transactions' and 'statements' tables."""
        return (
            "TABLE 'transactions':\n"
            "- Columns: [id (int), date (str: YYYY-MM-DD), description (str), amount (float), category (str), "
            "merchant (str), is_subscription (bool), transaction_type (str), is_essential (bool), tax_category (str)]\n\n"
            "TABLE 'statements':\n"
            "- Columns: [source_file (str), provider_name (str), closing_balance (float), total_debits (float)]"
        )

    def execute_sql(self, sql: str) -> str:
        """
        Executes a read-only SQL query against the database and returns results as CSV string.
        Only SELECT statements are allowed.
        """
        print(f"DEBUG: DatabaseExplorer executing SQL: {sql}")
        if not sql.strip().lower().startswith("select"):
            return "Error: Only SELECT queries are allowed."
            
        session = SessionLocal()
        try:
            result = session.execute(text(sql))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            if df.empty:
                return "Query executed successfully, but returned no results."
            return df.to_csv(index=False)
        except Exception as e:
            return f"SQL Error: {str(e)}"
        finally:
            session.close()

class PythonInterpreter:
    """Tool to execute Python code for advanced analysis."""
    
    def execute_python(self, code: str, data_csv: str = None) -> str:
        """
        Executes Python code. If 'data_csv' is provided, it's loaded into a DataFrame named 'df'.
        Always use print() to output results.
        """
        print(f"DEBUG: PythonInterpreter executing code...")
        output = io.StringIO()
        df = pd.DataFrame()
        if data_csv:
            try:
                df = pd.read_csv(io.StringIO(data_csv))
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
            except Exception as e:
                return f"Error loading data_csv: {str(e)}"

        try:
            with contextlib.redirect_stdout(output):
                local_vars = {"df": df, "pd": pd, "np": np}
                exec(code, {}, local_vars)
            result = output.getvalue().strip()
            return result or "Code executed successfully."
        except Exception as e:
            return f"Python Error: {str(e)}"

def get_query_agent():
    """Initializes the Gemma-3 Query Agent with advanced tools."""
    explorer = DatabaseExplorer()
    interpreter = PythonInterpreter()
    
    system_prompt = (
        "You are the Expense Explorer AI, powered by Gemini-2.5-Flash-Lite. You help users understand their financial data.\n\n"
        "REASONING LOOP (ReAct):\n"
        "1. **Think**: Analyze the user's request. What data do I need?\n"
        "2. **Schema**: Use 'get_schema' to understand the available tables if unsure.\n"
        "3. **Query**: Use 'execute_sql' to fetch relevant data from the database.\n"
        "4. **Analyze**: If the query returns data that needs complex processing (trends, math, filtering), use 'execute_python' passing the CSV result.\n"
        "5. **Iterate**: If results are unclear or more data is needed, repeat steps 3-4.\n"
        "6. **Answer**: Provide a clear, Markdown-formatted final response.\n\n"
        "DATABASE NOTES:\n"
        "- 'amount' is positive for spending, negative for income/refunds.\n"
        "- 'date' is stored as a string but can be parsed as datetime in Python.\n"
        "- Use boolean columns for filtering: 'is_subscription' for recurring costs, 'is_essential' for needs.\n"
        "- Use SQL for primary filtering/aggregation; use Python for complex logic."
    )
    
    agent = Agent(
        name="SophisticatedQueryAgent",
        model="gemini-2.5-flash-lite",
        instruction=system_prompt,
        tools=[
            explorer.get_schema,
            explorer.execute_sql,
            interpreter.execute_python
        ]
    )
    return agent

async def _get_adk_response(runner, query: str):
    session = await runner.session_service.create_session(user_id="query_user", app_name=runner.app_name)
    new_message = types.Content(role="user", parts=[types.Part(text=query)])
    
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
    """Entry point for the Query Agent."""
    init_db()
    agent = get_query_agent()
    runner = InMemoryRunner(agent=agent)
    print(f"Running Gemini-2.5-Flash-Lite Agent with query: {query}")
    
    try:
        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(_get_adk_response(runner, query))
    except Exception as e:
        import traceback
        return f"Error: {str(e)}\n{traceback.format_exc()}"

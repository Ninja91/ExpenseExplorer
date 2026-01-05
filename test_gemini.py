import os
from dotenv import load_dotenv
from agents import Agent, Runner

load_dotenv()

def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    # Google's OpenAI-compatible endpoint
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_BASE_URL"] = base_url
    
    agent = Agent(
        name="TestAgent",
        model="gemini-1.5-flash",
        instructions="You are a helpful assistant."
    )
    
    print("Testing Gemini via OpenAI-compatible endpoint...")
    try:
        # run_sync should be called outside of an event loop
        result = Runner.run_sync(agent, "Hello, who are you?")
        print(f"Success: {result.final_output}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_gemini()

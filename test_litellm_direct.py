import os
import asyncio
import litellm
from dotenv import load_dotenv

load_dotenv()

os.environ['LITELLM_LOG'] = 'DEBUG'

async def test_litellm():
    print(f"GEMINI_API_KEY: {os.getenv('GEMINI_API_KEY')[:10]}...")
    
    # Configure LiteLLM to use Google's OpenAI-compatible endpoint
    # Note: agents library will see 'litellm/openai/...' and use LiteLLM
    # We can also just use 'openai/...' if we set OPENAI_BASE_URL
    
    try:
        response = await litellm.acompletion(
            model="openai/gemini-1.5-flash",
            api_key=os.getenv("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print(f"LiteLLM Success: {response.choices[0].message.content}")
    except Exception as e:
        print(f"LiteLLM Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_litellm())

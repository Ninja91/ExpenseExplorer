import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv(override=True)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def test_genai():
    print(f"GEMINI_API_KEY: {os.getenv('GEMINI_API_KEY')[:10]}...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Hello")
        print(f"GenAI Success: {response.text}")
    except Exception as e:
        print(f"GenAI Error: {e}")

if __name__ == "__main__":
    test_genai()

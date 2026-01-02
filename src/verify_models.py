import os
import asyncio
from dotenv import load_dotenv
from google import genai

load_dotenv()

async def list_models():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in environment.")
        return

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    
    print("Listing available models...")
    try:
        models = await client.aio.models.list(config={"page_size": 100})
        with open("src/models_list.txt", "w", encoding="utf-8") as f:
            async for model in models:
                f.write(f"Model: {model.name}\n")
                f.write(f"  DisplayName: {model.display_name}\n")
                f.write("-" * 20 + "\n")
        print("Models listed to src/models_list.txt")
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())

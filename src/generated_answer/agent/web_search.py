from openai import OpenAI
import os
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)
load_dotenv()
api_key = os.getenv("GPT_SECRET_KEY_FASOLKAAI")
client = OpenAI(api_key=api_key)

def openai_web_search(query: str) -> str:
    try:
        response = client.responses.create(
            model="gpt-4o",
            tools=[{"type": "web_search_preview"}],
            input=query
        )
        return response.output_text
    except Exception as e:
        logger.error(f"Ошибка при поиске: {e}")
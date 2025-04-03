from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
import logging


load_dotenv()
logger = logging.getLogger(__name__)
api_key = os.getenv("GPT_SECRET_KEY_FASOLKAAI")
client = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=api_key)


def answer_summarization(text):
    summarization_prompt = (
        f"""You are an expert in text editing and summarization.

        You are provided with a long text containing multiple blocks of already high-quality information on a single topic. The text may include:

        - Repeating headings;
        - Duplicate descriptions and definitions;
        - Redundant phrases and explanations;
        - Rephrased but semantically identical parts.

        📌 Your task is:

        1. Remove **all semantically duplicate content**, including both headings and body text.
        2. **Merge** similar blocks into one cohesive segment.
        3. **Do not add** any new information or **distort** the original meaning.
        4. The final text must **not contain any repetitive descriptions or headings**.
        5. The response should be a **coherent, logically structured, and concise** section — like a single article section, not a set of repeating fragments.
        6. You are strictly **forbidden from removing source links** in the format: [Source Name](https://example.com).
        ⚠️ Do not output any drafts or intermediate versions. Only the final cleaned and compressed version of the text.

        Here is the original text:

        {text}
        """
    )

    try:
        messages=[
            {"role": "system", "content": summarization_prompt},
            {"role": "user", "content": text}
        ]
        response = client.invoke(messages)

        response_text = response.content
        logger.info(f"Резюме ответа: {response_text}")

        return response_text

    except Exception as e:
        logger.error(f"Ошибка суммаризации: {e}")
        return None

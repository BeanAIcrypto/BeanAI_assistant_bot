import logging
import os

from dotenv import load_dotenv

from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS


load_dotenv()
logger = logging.getLogger(__name__)

API_KEY: str = os.getenv("GPT_SECRET_KEY_FASOLKAAI", "")
MODEL_NAME: str = os.getenv("MODEL_NAME", "")
FAISS_INDEX_PATH: str = "faiss_index_RU"

if not API_KEY:
    raise ValueError("API-ключ OpenAI не найден. Проверьте файл .env.")

embeddings = OpenAIEmbeddings(
    openai_api_key=API_KEY, model="text-embedding-ada-002"
)

try:
    retriever = FAISS.load_local(
        "faiss_index_RU", embeddings, allow_dangerous_deserialization=True
    ).as_retriever(
        k=4, search_type="similarity_score_threshold", search_kwargs={"score_threshold": 0.78, "k": 6}, fetch_k=50
    )
    logger.info("FAISS индекс успешно загружен.")
except Exception as e:
    logger.error(f"Ошибка загрузки FAISS индекса: {e}")
    raise

def knowledge_base_search(query: str) -> str:
    """
    Поиск информации в базе знаний.

    Args:
        query (str): Запрос пользователя.

    Returns:
        str: Результаты поиска в базе знаний или сообщение об ошибке.

    Raises:
        ValueError: Если запрос пустой или недействительный.
        RuntimeError: Если ретривер недоступен или произошла ошибка во время поиска.
    """
    try:
        if not query.strip():
            raise ValueError("Запрос не может быть пустым.")

        if not retriever:
            raise RuntimeError("Ретривер базы знаний недоступен.")

        docs = retriever.get_relevant_documents(query)
        if not docs:
            logger.info(f"Результаты поиска отсутствуют для запроса: {query}")

        results = "\n".join([doc.page_content for doc in docs])
        logger.info(f"Найдено {len(docs)} документов для запроса: {query}")
        return results
    except ValueError as e:
        logger.error(f"Ошибка поиска в базе знаний: {e}")
    except RuntimeError as e:
        logger.error(f"Ошибка доступа к базе знаний: {e}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка во время поиска: {e}")

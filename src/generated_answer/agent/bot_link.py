import logging
from dotenv import load_dotenv
from langchain.schema import SystemMessage, HumanMessage

from src.services.count_token import count_output_tokens
from db.dbworker import get_user_limit, update_user_limit

load_dotenv()
logger = logging.getLogger(__name__)


async def bot_link(question: str, user_id: int, llm) -> str | None:
    """
    Модель решает, нужно ли направить пользователя к криптоаналитику.
    Если нужно — возвращает готовый текст с упоминанием @FasolkaAI_Analyst_bot.
    Если не нужно — возвращает None.
    """
    logger.debug(f"[bot_link] Проверка вопроса: '{question}' от user_id={user_id}")

    system_prompt = (
        "You are an assistant that helps with user questions.\n"
        "If the user's question relates to crypto project analytics — politely respond that you do not provide analytics, and recommend contacting @FasolkaAI_Analyst_bot instead.\n"
        "If the question is not about analytics, do not reply — simply return an empty response."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=question)
    ]

    total_tokens = count_output_tokens(system_prompt + question)
    user_limit = get_user_limit(user_id)

    if user_limit < total_tokens:
        logger.warning(f"[bot_link] Недостаточно токенов. Осталось: {user_limit}, нужно: {total_tokens}")
        return None

    response = llm(messages)
    update_user_limit(user_id, user_limit - total_tokens)

    model_answer = response.content.strip()
    logger.debug(f"[bot_link] Ответ модели: '{model_answer}'")

    return model_answer if model_answer else ""

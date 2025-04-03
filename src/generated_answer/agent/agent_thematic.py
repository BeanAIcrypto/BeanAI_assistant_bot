import os
import logging
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage

from src.services.count_token import count_output_tokens
from db.dbworker import get_user_limit, update_user_limit, get_user_history
from src.generated_answer.agent.agent_response import knowledge_base_search
from src.bot.promt import PROMTS


logger = logging.getLogger(__name__)
load_dotenv()
OPENAI_API_KEY = os.getenv("GPT_SECRET_KEY_FASOLKAAI")

llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    openai_api_key=OPENAI_API_KEY
)

async def is_crypto_related(question: str, user_id: int) -> bool:
    logger.debug(f"[is_crypto_related] Проверяем вопрос: '{question}' для user_id={user_id}")

    knowledge_snippets = knowledge_base_search(question)
    has_knowledge = knowledge_snippets and "No search results found" not in knowledge_snippets

    if has_knowledge:
        logger.info(f"[is_crypto_related] Вопрос '{question}' найден в базе знаний и автоматически классифицирован как криптовалютный.")
        return True

    system_prompt = PROMTS["system_prompt"]
    user_prompt = f"{PROMTS['user_prompt']} {question}\n\nReply with 'True' if the question is directly related to the topic of cryptocurrencies, otherwise reply with 'False'."

    total_tokens = count_output_tokens(system_prompt + user_prompt) + 4
    limit = get_user_limit(user_id)

    if limit - total_tokens < 0:
        logger.warning(f"[is_crypto_related] Недостаточно токенов. Остаток: {limit}, нужно: {total_tokens}")
        return False

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    response = llm(messages)
    update_user_limit(user_id, limit - total_tokens)

    model_answer = response.content.strip()
    logger.debug(f"[is_crypto_related] Ответ модели: '{model_answer}'")

    return model_answer == "True"


async def context_completion(question: str, user_id: int) -> str:
    """
    Переформулировать вопрос, если он явно ссылается
    на предыдущий контекст диалога. Если без контекста
    всё понятно, вернуть вопрос без изменений.
    """
    logger.debug(f"[context_completion] Получен вопрос: '{question}' для user_id={user_id}")

    history = get_user_history(user_id)
    if not history:
        logger.debug("[context_completion] История отсутствует. Возвращаем исходный вопрос без изменений.")
        return question

    history_list = []
    for entry in history:
        if "question" in entry and "response" in entry:
            history_list.append({
                "user": entry["question"],
                "assistant": entry["response"]
            })
        else:
            logger.warning(f"[context_completion] Пропущена некорректная запись истории: {entry}")

    logger.debug(f"[context_completion] Извлечено {len(history_list)} записей из истории.")

    system_prompt = (
        """You are an assistant that improves and clarifies user questions, making them fully self-contained and understandable without the context of the current dialogue.

        Workflow:
        1. Analyze the user's latest message along with previous messages in the conversation.
        2. Identify any ambiguous pronouns (such as: "this", "that", "such", "he", "she", "they", etc.) or references that only make sense within the conversation's context.
        3. Replace each such pronoun or vague reference with specific entities (e.g., names of objects, terms, people, or concepts) explicitly mentioned earlier in the dialogue.
        4. If the user's message includes unfamiliar terms or unclear wording, use the knowledge base to interpret their meaning and incorporate them accurately into the reformulated question.
        5. Do not change the original intent or meaning of the user's question. Your version should stay as close as possible to the original wording, but be fully clear and comprehensible on its own.
        6. If the user's message is already fully clear and self-contained without requiring pronoun replacement or clarification, return it unchanged.

        Your output should be a precise, self-sufficient question that can be fully understood by you and other GPT models without any additional context.
        """
    )

    history_text = ""
    for i, dialog in enumerate(history_list):
        user_text = dialog["user"]
        assistant_text = dialog["assistant"]
        history_text += (
            f"User question {i + 1}: {user_text}\n"
            f"Assistant response {i + 1}: {assistant_text}\n\n"
        )

        knowledge_snippets = knowledge_base_search(question)
        if knowledge_snippets and "No search results found" not in knowledge_snippets:
            knowledge_block = f"📚 Here are relevant excerpts from the knowledge base:\n{knowledge_snippets}\n\n"
        else:
            knowledge_block = ""

    user_prompt = (
        f"Knowledge base content: {knowledge_block}"
        f"Dialogue history:\n{history_text}\n"
        f"New question: '{question}'\n\n"
        "Return either the original question or a rephrased version of it with no references to prior context."
    )

    total_tokens = count_output_tokens(system_prompt + user_prompt) + 4
    limit = get_user_limit(user_id)

    logger.debug(f"[context_completion] Подсчитано total_tokens={total_tokens}, доступно limit={limit}")

    if limit - total_tokens < 0:
        logger.warning(
            f"[context_completion] Недостаточно токенов. Остаток: {limit}, нужно: {total_tokens}. "
            "Возвращаем исходный вопрос."
        )
        return question

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    response = llm(messages)
    new_limit = limit - total_tokens
    update_user_limit(user_id, new_limit)

    revised_question = response.content.strip()
    logger.debug(f"[context_completion] Модель вернула переформулированный вопрос: '{revised_question}'")

    return revised_question

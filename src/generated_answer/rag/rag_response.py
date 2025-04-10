import asyncio
import logging
import os
from typing import List, Dict, Union, Any

from dotenv import load_dotenv
from openai import BadRequestError, RateLimitError

from db.dbworker import get_user_limit, update_user_limit
from langchain.chains import (
    create_history_aware_retriever,
    create_retrieval_chain,
)
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from src.bot.bot_messages import MESSAGES
from src.services.count_token import count_output_tokens, count_input_tokens


load_dotenv()
logger = logging.getLogger(__name__)

API_KEY: str = os.getenv("GPT_SECRET_KEY_FASOLKAAI", "")
MODEL_NAME: str = os.getenv("MODEL_NAME", "")

if not API_KEY:
    raise ValueError("API-ключ OpenAI не найден. Проверьте файл .env.")

embeddings = OpenAIEmbeddings(
    openai_api_key=API_KEY, model="text-embedding-ada-002"
)

try:
    retriever = FAISS.load_local(
        "faiss_index_RU", embeddings, allow_dangerous_deserialization=True
    ).as_retriever(
        k=4, search_type="similarity", search_kwargs={"k": 6}, fetch_k=50
    )
    logger.info("FAISS индекс успешно загружен.")
except Exception as e:
    logger.error(f"Ошибка загрузки FAISS индекса: {e}")
    raise

try:
    llm = ChatOpenAI(
        model_name=MODEL_NAME,
        api_key=API_KEY,
        temperature=0.7,
        top_p=0.9,
        frequency_penalty=0.5,
        presence_penalty=0.6,
    )
    logger.info("ChatOpenAI успешно инициализирован.")
except Exception as e:
    logger.error(f"Ошибка инициализации модели: {e}")
    raise ValueError(
        "Не удалось инициализировать ChatOpenAI. Проверьте API-ключ."
    )


async def get_context_retriever_chain(
    llm_2: ChatOpenAI, prompt_text: str
) -> Any:
    """
    Создание цепочки для поиска контекста.

    Args:
        llm_2 (ChatOpenAI): LLM модель.
        prompt_text (str): Текст контекста.

    Returns:
        Any: Цепочка поиска.

    Raises:
        ValueError: Если параметры шаблона некорректны.
        RuntimeError: Если ошибка связана с созданием цепочки.
        Exception: Любая другая ошибка.
    """
    try:
        prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="history"),
                SystemMessagePromptTemplate.from_template(prompt_text),
                HumanMessagePromptTemplate.from_template("{input}"),
                HumanMessagePromptTemplate.from_template(
                    "Given the conversation above, generate a search query to retrieve information relevant to this discussion."
                ),
            ]
        )
        return create_history_aware_retriever(llm_2, retriever, prompt)
    except ValueError as e:
        logger.error(f"Ошибка параметров шаблона для контекста: {str(e)}")
        raise
    except RuntimeError as e:
        logger.error(
            f"Ошибка выполнения при создании контекстного ретривера: {str(e)}"
        )
        raise
    except Exception as e:
        logger.error(
            f"Непредвиденная ошибка создания цепочки поиска: {str(e)}"
        )
        raise


async def get_conversational_rag_chain(
    retriever_chain: Any, llm_2: ChatOpenAI, prompt_text: str
) -> Any:
    """
    Создание цепочки Retrieval-Augmented Generation (RAG).

    Args:
        retriever_chain (Any): Ретривер.
        llm_2 (ChatOpenAI): LLM модель.
        prompt_text (str): Текст контекста.

    Returns:
        Any: RAG цепочка.

    Raises:
        ValueError: Если параметры цепочки некорректны.
        KeyError: Если ключи данных в цепочке отсутствуют.
        Exception: Любая другая ошибка.
    """
    try:
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    prompt_text
                    + "\nDocument with information for responding to the user:\n\n{context}"
                ),
                MessagesPlaceholder(variable_name="history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )
        stuff_documents_chain = create_stuff_documents_chain(llm_2, prompt)
        return create_retrieval_chain(retriever_chain, stuff_documents_chain)
    except ValueError as e:
        logger.error(f"Ошибка параметров при создании RAG цепочки: {str(e)}")
        raise
    except KeyError as e:
        logger.error(
            f"Отсутствует необходимый ключ данных в RAG цепочке: {str(e)}"
        )
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка создания RAG цепочки: {str(e)}")
        raise


async def run_gpt(
    user_id: int,
    bot: Any,
    prompt_text: str,
    user_input: str,
    history: List[Dict[str, str]],
) -> Union[str, None]:
    """
    Обработка большого объема текста с использованием RAG (Retrieval-Augmented Generation).

    Args:
        user_id (int): Идентификатор пользователя.
        bot (Any): Экземпляр Telegram-бота.
        prompt_text (str): Текст начальной подсказки для модели.
        user_input (str): Ввод пользователя.
        history (List[Dict[str, str]]): История общения пользователя с ботом.

    Returns:
        Union[str, None]: Ответ от модели или None в случае ошибки.

    Raises:
        BadRequestError: Ошибка при некорректном запросе к модели.
        RateLimitError: Превышен лимит запросов к модели.
        Exception: Непредвиденная ошибка.
    """
    try:
        formatted_history = [
            (
                {"role": "user", "content": entry["question"]}
                if "question" in entry
                else {"role": "assistant", "content": entry["response"]}
            )
            for entry in history
            if "question" in entry and "response" in entry
        ]

        if len(formatted_history) != len(history) * 2:
            logger.warning(
                "Некорректный формат истории для пользователя. Пропущены некоторые записи."
            )

        total_tokens_input = count_input_tokens(
            history=history,
            user_input=user_input,
            prompt=prompt_text,
            model=MODEL_NAME,
        )
        logger.info(
            f"Общее количество токенов для запроса: {total_tokens_input}"
        )

        limit = get_user_limit(user_id)
        if limit - total_tokens_input <= 0:
            logger.info(f"Не хватает токенов: {limit - total_tokens_input}")
            await bot.send_message(user_id, MESSAGES["get_user_limit"]["ru"])
            return None

        retriever_chain = await get_context_retriever_chain(llm, prompt_text)
        conversation_rag_chain = await get_conversational_rag_chain(
            retriever_chain, llm, prompt_text
        )

        response = await asyncio.to_thread(
            conversation_rag_chain.invoke,
            {"history": formatted_history, "input": user_input},
        )

        response_text = response.get("answer", "")
        total_tokens_response = count_output_tokens(
            response_text, model=MODEL_NAME
        )

        total_tokens = total_tokens_input + total_tokens_response
        logger.info(
            f"Общее количество токенов (входные + ответ): {total_tokens}"
        )

        new_limit = limit - total_tokens
        update_user_limit(user_id, new_limit)
        logger.info(f"Не переформулированный ответ: {response_text}")
        return response_text
    except BadRequestError as e:
        logger.error(
            f"Ошибка при обработке запроса пользователя {user_id}: {e}"
        )
        return MESSAGES["bad_request_error"]["en"]
    except RateLimitError as e:
        logger.error(f"Ошибка большого количества запросов: {e}")
        return MESSAGES["rate_limit_error"]["en"]
    except KeyError as e:
        logger.error(f"Ошибка ключа данных пользователя {user_id}: {e}")
        return MESSAGES["key_error"]["en"]
    except ValueError as e:
        logger.error(
            f"Некорректное значение в данных для пользователя {user_id}: {e}"
        )
        return MESSAGES["value_error"]["en"]
    except Exception as e:
        import traceback

        trace = traceback.format_exc()
        logger.error(
            f"Непредвиденная ошибка для пользователя {user_id}:\n{trace}"
        )
        return MESSAGES["general_error"]["en"]

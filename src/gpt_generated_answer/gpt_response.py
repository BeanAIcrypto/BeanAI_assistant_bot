import asyncio
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union, Any

from dotenv import load_dotenv
from openai import BadRequestError, RateLimitError

from db.dbworker import get_user_limit, update_user_limit
from langchain.agents import AgentType, Tool, initialize_agent
from langchain.chains import (
    create_history_aware_retriever,
    create_retrieval_chain,
)
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.memory import ConversationBufferMemory
from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from src.bot.bot_messages import MESSAGES
from src.gpt_generated_answer.google_search import GoogleSearchAPIWrapper
from src.services.count_token import count_output_tokens, count_input_tokens
from src.bot.promt import PROMTS

load_dotenv()

logger = logging.getLogger(__name__)

API_KEY: str = os.getenv("GPT_SECRET_KEY_FASOLKAAI", "")
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
SEARCH_ENGINE_ID: str = os.getenv("SEARCH_ENGINE_GLOBAL_ID", "")
MODEL_NAME: str =  os.getenv("MODEL_NAME", "")
MODEL_NAME_MEM: str =  os.getenv("MODEL_NAME_MEM", "")
FAISS_INDEX_PATH: str = "faiss_index_RU"

if not API_KEY:
    raise ValueError("API-ключ OpenAI не найден. Проверьте файл .env.")

embeddings = OpenAIEmbeddings(
    openai_api_key=API_KEY,
    model="text-embedding-ada-002"
)

try:
    retriever = FAISS.load_local(
        "faiss_index_RU",
        embeddings,
        allow_dangerous_deserialization=True
    ).as_retriever(
        k=4,
        search_type="similarity",
        search_kwargs={'k': 6},
        fetch_k=50
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
        presence_penalty=0.6
    )
    llm_mem = ChatOpenAI(
        api_key=API_KEY,
        model_name=MODEL_NAME,
        temperature=0.5,
        top_p=0.9,
        frequency_penalty=0.5,
        presence_penalty=0.6
    )
    logger.info("ChatOpenAI успешно инициализирован.")
except Exception as e:
    logger.error(f"Ошибка инициализации модели: {e}")
    raise ValueError("Не удалось инициализировать ChatOpenAI. Проверьте API-ключ.")

google_search = GoogleSearchAPIWrapper(api_key=GOOGLE_API_KEY, search_engine_id=SEARCH_ENGINE_ID)

def reformulate_response(response_text: str, user_id: int) -> str:
    """
    Переформулирует ответ с использованием нового промта.

    Args:
        response_text (str): Исходный текст ответа для переформулировки.
        user_id (int): Идентификатор пользователя.

    Returns:
        str: Переформулированный ответ.

    Raises:
        ValueError: Если переформулировка невозможна.
        Exception: При возникновении непредвиденных ошибок.
    """
    try:
        reformulate_messages = [
            SystemMessage(content=PROMTS["mem_prompt"]["en"]),
            HumanMessage(content=f"Ответ: {response_text}\nПереформулируй:")
        ]

        reformulated_response = llm_mem(reformulate_messages).content.strip()

        total_tokens_reformulate = count_output_tokens(reformulated_response, model="gpt-4o")
        limit = get_user_limit(user_id)
        if limit - total_tokens_reformulate < 0:
            raise ValueError("Недостаточно токенов для выполнения переформулировки.")

        new_limit = limit - total_tokens_reformulate
        update_user_limit(user_id, new_limit)

        logger.info(f"Переформулированный ответ: {reformulated_response}")
        logger.info(f"Обновленный лимит токенов: {new_limit}")
        return reformulated_response

    except Exception as e:
        logger.error(f"Ошибка при переформулировке ответа для пользователя {user_id}: {e}")
        raise ValueError("Ошибка при переформулировке ответа.")


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
            return "Результаты поиска отсутствуют."

        results = "\n".join([doc.page_content for doc in docs])
        logger.info(f"Найдено {len(docs)} документов для запроса: {query}")
        return results
    except ValueError as e:
        logger.error(f"Ошибка поиска в базе знаний: {e}")
        return "Недопустимый запрос. Попробуйте снова."
    except RuntimeError as e:
        logger.error(f"Ошибка доступа к базе знаний: {e}")
        return "База знаний временно недоступна."
    except Exception as e:
        logger.error(f"Неизвестная ошибка во время поиска: {e}")
        return "Произошла ошибка при выполнении поиска. Попробуйте позже."


tools = [
    Tool(
        name="Knowledge Base",
        func=knowledge_base_search,
        description="Используется для ответов на вопросы на основе внутренней базы знаний."
    ),
    Tool(
        name="Google Search",
        func=google_search.run,
        description="Используется для поиска дополнительной информации через Google."
    )
]


def create_agent(prompt_text: str, history: Optional[List[Dict[str, str]]] = None):
    """
    Создание агента для обработки запросов.

    Args:
        prompt_text (str): Начальный текст для агента.
        history (Optional[List[Dict[str, str]]]): История общения.

    Returns:
        Any: Инициализированный агент.

    Raises:
        ValueError: Ошибка в переданных данных (например, пустая история или некорректный формат).
        RuntimeError: Ошибка инициализации агента.
    """
    try:
        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
        memory.clear()

        if prompt_text:
            memory.chat_memory.messages.append(
                SystemMessage(content=prompt_text + f"{datetime.now()}")
            )

        if history:
            for entry in history:
                if "question" in entry and "response" in entry:
                    memory.chat_memory.messages.append(HumanMessage(content=entry['question']))
                    memory.chat_memory.messages.append(AIMessage(content=entry['response']))
                else:
                    logger.warning(f"Пропущена некорректная запись истории: {entry}")

        agent = initialize_agent(
            tools=tools,
            llm=llm,
            agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
            memory=memory,
            verbose=True,
            handle_parsing_errors=True,
            agent_kwargs={
                "system_message": prompt_text
            }
        )
        logger.info("Агент успешно создан.")
        return agent
    except ValueError as e:
        logger.error(f"Ошибка создания агента: некорректные данные. {e}")
        raise ValueError("Ошибка в переданных данных для создания агента.")
    except RuntimeError as e:
        logger.error(f"Ошибка инициализации агента: {e}")
        raise RuntimeError("Не удалось инициализировать агента.")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при создании агента: {e}")
        raise


async def fix_user_query(user_query: str, user_id: int) -> str:
    """
    Исправляет ошибки в пользовательском запросе с использованием языковой модели.

    Args:
        user_query (str): Исходный запрос пользователя, который необходимо исправить.
        user_id (int): Уникальный идентификатор пользователя.

    Returns:
        str: Исправленный текст запроса.

    Raises:
        ValueError: Если язык не поддерживается или PROMTS для указанного языка отсутствует.
        RuntimeError: В случае ошибки при взаимодействии с языковой моделью.
    """

    try:
        limit = get_user_limit(user_id)
        messages = [
            SystemMessage(content=PROMTS['fix_user_input']["en"]),
            HumanMessage(content=f"**Вход:** {user_query}\n**Выход:**")
        ]

        total_tokens_input = count_input_tokens(
            history=[],
            user_input=user_query,
            prompt=PROMTS['fix_user_input']["en"],
            model="gpt-4"
        )
        logger.info(f"Количество входных токенов: {total_tokens_input}")

        response = llm(messages)
        corrected_text = response.content.strip()

        total_tokens_output = count_output_tokens(corrected_text, model="gpt-4")
        logger.info(f"Количество выходных токенов: {total_tokens_output}")

        total_tokens = total_tokens_input + total_tokens_output
        update_user_limit(user_id, limit-total_tokens)
        logger.info(f"Общее количество токенов: {total_tokens}")
        logger.info(f"Исправленный запрос пользователя: {corrected_text}")
        return corrected_text

    except ValueError as ve:
        logger.error(f"Ошибка в данных PROMTS: {ve}")
        raise
    except KeyError as ke:
        logger.error(f"Ошибка в ключах PROMTS: {ke}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при взаимодействии с LLM: {e}")
        raise RuntimeError(f"Ошибка при взаимодействии с языковой моделью: {e}")


async def run_agent(
    user_id: int,
    user_input: str,
    history: List[Dict[str, str]],
    prompt_text: str
) -> Union[str, Tuple[None, str]]:
    """
    Запуск агента для обработки пользовательского ввода.

    Args:
        user_id (int): Уникальный идентификатор пользователя.
        user_input (str): Ввод пользователя.
        history (List[Dict[str, str]]): История общения.
        prompt_text (str): Текст для настройки контекста агента.

    Returns:
        Union[str, Tuple[None, str]]: Ответ агента или сообщение об ошибке.

    Raises:
        ValueError: Некорректный ввод или превышение лимита токенов.
        ConnectionError: Проблемы с подключением к модели.
        RuntimeError: Ошибка при выполнении агента.
    """
    try:
        fix_user_input = await fix_user_query(user_input, user_id)
        limit = get_user_limit(user_id)
        total_tokens_input = count_input_tokens(history, fix_user_input, prompt_text, model=MODEL_NAME)

        if limit - total_tokens_input <= 0:
            logger.warning(f"Пользователь {user_id} превысил лимит токенов.")
            return None, MESSAGES["get_user_limit"]["en"]

        agent = create_agent(prompt_text, history)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, agent.invoke, fix_user_input)
        refined_response = response["output"]

        total_tokens_response = count_output_tokens(str(response), model=MODEL_NAME)
        total_tokens_used = total_tokens_input + total_tokens_response

        update_user_limit(user_id, limit - total_tokens_used)
        mem_response = reformulate_response(refined_response, user_id)
        return mem_response

    except ValueError as e:
        logger.error(f"Некорректный ввод пользователя {user_id}: {e}")
        return "Ошибка обработки вашего запроса. Попробуйте уточнить ввод."
    except ConnectionError as e:
        logger.error(f"Ошибка подключения к модели для пользователя {user_id}: {e}")
        return "Не удалось подключиться к модели. Повторите попытку позже."
    except RuntimeError as e:
        logger.error(f"Ошибка выполнения агента для пользователя {user_id}: {e}")
        return "Произошла внутренняя ошибка при обработке запроса."
    except BadRequestError as e:
        logger.error(f"Ошибка агента для пользователя {user_id}: {e}")
        return "Ваш запрос превышает лимит токенов."
    except RateLimitError as e:
        logger.error(f"Ошибка большого количества запросов за раз: {e}")
        return "Вы слишком часто задаёте вопрос. Пожалуйста, попробуйте позже."
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при обработке запроса для пользователя {user_id}: {e}")
        return MESSAGES["error_processing"]["en"]


async def get_context_retriever_chain(llm_2: ChatOpenAI, prompt_text: str) -> Any:
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
        prompt = ChatPromptTemplate.from_messages([
            MessagesPlaceholder(variable_name="history"),
            SystemMessagePromptTemplate.from_template(prompt_text),
            HumanMessagePromptTemplate.from_template("{input}"),
            HumanMessagePromptTemplate.from_template(
                "Учитывая приведенный выше разговор, составь поисковый запрос, чтобы получить информацию, относящуюся к этому разговору"
            ),
        ])
        return create_history_aware_retriever(llm_2, retriever, prompt)
    except ValueError as e:
        logger.error(f"Ошибка параметров шаблона для контекста: {str(e)}")
        raise
    except RuntimeError as e:
        logger.error(f"Ошибка выполнения при создании контекстного ретривера: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка создания цепочки поиска: {str(e)}")
        raise


async def get_conversational_rag_chain(
    retriever_chain: Any,
    llm_2: ChatOpenAI,
    prompt_text: str
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
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(prompt_text + "\nДокумент с информацией для ответа пользователю:\n\n{context}"),
            MessagesPlaceholder(variable_name="history"),
            HumanMessagePromptTemplate.from_template("{input}")
        ])
        stuff_documents_chain = create_stuff_documents_chain(llm_2, prompt)
        return create_retrieval_chain(retriever_chain, stuff_documents_chain)
    except ValueError as e:
        logger.error(f"Ошибка параметров при создании RAG цепочки: {str(e)}")
        raise
    except KeyError as e:
        logger.error(f"Отсутствует необходимый ключ данных в RAG цепочке: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка создания RAG цепочки: {str(e)}")
        raise


async def run_gpt(
    user_id: int,
    bot: Any,
    prompt_text: str,
    user_input: str,
    history: List[Dict[str, str]]
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
            {"role": "user", "content": entry['question']}
            if 'question' in entry else {"role": "assistant", "content": entry['response']}
            for entry in history if 'question' in entry and 'response' in entry
        ]

        if len(formatted_history) != len(history) * 2:
            logger.warning("Некорректный формат истории для пользователя. Пропущены некоторые записи.")

        total_tokens_input = count_input_tokens(history=history, user_input=user_input, prompt=prompt_text, model=MODEL_NAME)
        logger.info(f"Общее количество токенов для запроса: {total_tokens_input}")

        limit = get_user_limit(user_id)
        if limit - total_tokens_input <= 0:
            logger.info(f"Не хватает токенов: {limit - total_tokens_input}")
            await bot.send_message(user_id, MESSAGES["get_user_limit"]["en"])
            return None

        retriever_chain = await get_context_retriever_chain(llm, prompt_text)
        conversation_rag_chain = await get_conversational_rag_chain(retriever_chain, llm, prompt_text)

        response = await asyncio.to_thread(
            conversation_rag_chain.invoke,
            {"history": formatted_history, "input": user_input}
        )

        response_text = response.get('answer', '')
        total_tokens_response = count_output_tokens(response_text, model=MODEL_NAME)

        total_tokens = total_tokens_input + total_tokens_response
        logger.info(f"Общее количество токенов (входные + ответ): {total_tokens}")

        new_limit = limit - total_tokens
        update_user_limit(user_id, new_limit)
        logger.info(f"Не переформулированный ответ: {response_text}")
        mem_response = reformulate_response(response_text, user_id)
        return mem_response
    except BadRequestError as e:
        logger.error(f"Ошибка при обработке запроса пользователя {user_id}: {e}")
        return MESSAGES["bad_request_error"]["en"]
    except RateLimitError as e:
        logger.error(f"Ошибка большого количества запросов: {e}")
        return MESSAGES["rate_limit_error"]["en"]
    except KeyError as e:
        logger.error(f"Ошибка ключа данных пользователя {user_id}: {e}")
        return MESSAGES["key_error"]["en"]
    except ValueError as e:
        logger.error(f"Некорректное значение в данных для пользователя {user_id}: {e}")
        return MESSAGES["value_error"]["en"]
    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        logger.error(f"Непредвиденная ошибка для пользователя {user_id}:\n{trace}")
        return MESSAGES["general_error"]["en"]


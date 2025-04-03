import asyncio
import logging
import os
import re

from typing import List, Dict, Optional, Tuple, Union
from dotenv import load_dotenv
from langchain_core.output_parsers import JsonOutputParser

from db.dbworker import get_user_limit, update_user_limit
from langchain.agents import AgentType, Tool, initialize_agent
from langchain.memory import ConversationBufferMemory
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from src.bot.bot_messages import MESSAGES
from src.generated_answer.agent.web_search import openai_web_search
from src.services.count_token import count_output_tokens, count_input_tokens
from src.bot.promt import PROMTS

from src.generated_answer.agent.agent_answer_summarization import answer_summarization
from src.generated_answer.agent.generate_plan import generate_plan, parse_plan
from src.generated_answer.agent.faiss_search import knowledge_base_search
from src.generated_answer.agent.bot_link import bot_link


load_dotenv()
output_parser = JsonOutputParser()

logger = logging.getLogger(__name__)

API_KEY: str = os.getenv("GPT_SECRET_KEY_FASOLKAAI", "")
MODEL_NAME: str = os.getenv("MODEL_NAME", "")
FAISS_INDEX_PATH: str = "faiss_index_RU"

if not API_KEY:
    raise ValueError("API-ключ OpenAI не найден. Проверьте файл .env.")

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

tools = [
    Tool(
        name="Knowledge Base",
        func=knowledge_base_search,
        description="Used to answer questions based on the internal knowledge base.",
    ),
    Tool(
        name="OpenAI Web Search",
        func=openai_web_search,
        description="Used to search for additional information on the internet.",
    ),
]

def create_agent(
        prompt_text: str, history: Optional[List[Dict[str, str]]] = None
):
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
        memory = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )
        memory.clear()

        if prompt_text:
            memory.chat_memory.messages.append(
                SystemMessage(content=prompt_text)
            )

        if history:
            for entry in history:
                if "question" in entry and "response" in entry:
                    memory.chat_memory.messages.append(
                        HumanMessage(content=entry["question"])
                    )
                    memory.chat_memory.messages.append(
                        AIMessage(content=entry["response"])
                    )
                else:
                    logger.warning(
                        f"Пропущена некорректная запись истории: {entry}"
                    )

        agent = initialize_agent(
            tools=tools,
            llm=llm,
            agent=AgentType.CONVERSATIONAL_REACT_DESCRIPTION,
            memory=memory,
            verbose=True,
            handle_parsing_errors=True,
            agent_kwargs={"system_message": prompt_text},
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


def clean_agent_response(response: str) -> str:
    """
    Очищает ответ агента от ненужных завершающих символов ``` и многоточий.

    Args:
        response (str): Ответ агента.

    Returns:
        str: Очищенный ответ.
    """
    response = response.strip()

    if response.startswith("```") and response.endswith("```"):
        return response

    if response.endswith("```"):
        response = response.rstrip("`").strip()

    response = re.sub(r"\.{2,}$", "", response)

    return response


async def get_information_for_point_with_agent(point: str, agent, loop) -> str:
    """
    Использует агента для обработки каждого пункта плана.

    Args:
        point (str): Пункт плана.
        agent (AgentExecutor): Инициализированный агент LangChain.
        loop (asyncio.AbstractEventLoop): Текущий event loop.

    Returns:
        str: Сформированный ответ агента.
    """
    try:
        response = await loop.run_in_executor(None, agent.invoke, point)

        if isinstance(response, dict) and "output" in response and response["output"]:
            clean_response = clean_agent_response(response["output"])
            return f"🔹 *{point}*\n{clean_response}"
        else:
            logger.warning(f"Агент не вернул результат для пункта: {point}")
            return f"🔹 *{point}*\nError: the agent did not return a result."

    except Exception as e:
        logger.error(f"Ошибка при обработке пункта плана '{point}': {e}")
        return f"🔹 *{point}*\nError while processing the information."


async def run_agent(
        user_id: int,
        user_input: str,
        history: List[Dict[str, str]],
        prompt_text: str,
) -> Union[str, Tuple[None, str]]:
    try:

        plan_answer = await generate_plan(user_input, llm)
        plan_points = parse_plan(plan_answer)

        if not plan_points:
            logger.error("Ошибка: список пунктов плана пустой.")
            return "Ошибка: план ответа пуст."

        agent = create_agent(prompt_text, history)
        loop = asyncio.get_event_loop()

        responses = await asyncio.gather(*[
            get_information_for_point_with_agent(
                f"You are elaborating on the item: {point} from the following topic: {user_input}.", agent, loop) for
            point in plan_points
        ])

        total_tokens_input = count_input_tokens(
            history, user_input, prompt_text, model=MODEL_NAME
        )

        limit = get_user_limit(user_id)
        if limit - total_tokens_input <= 0:
            logger.warning(f"Пользователь {user_id} превысил лимит токенов.")
            return None, MESSAGES["get_user_limit"]["en"]

        final_answer = "\n\n".join(responses)
        logger.info(f"Ответ модели: {final_answer}")
        summarization_text = answer_summarization(final_answer)
        link_bot = await bot_link(user_input, user_id, llm)
        return summarization_text + link_bot

    except ValueError as e:
        logger.error(f"Некорректный ввод пользователя {user_id}: {e}")
        return "Error processing your request. Please try to clarify your input."
    except Exception as e:
        logger.error(f"Ошибка выполнения агента: {e}")
        return MESSAGES["error_processing"]["en"]

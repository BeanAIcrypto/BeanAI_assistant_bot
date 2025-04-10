import re
from datetime import datetime

from typing import List
from langchain.schema import SystemMessage
import logging

from src.generated_answer.agent.faiss_search import knowledge_base_search

logger = logging.getLogger(__name__)


def parse_plan(plan_text: str) -> List[str]:
    """
    Разбирает текст плана и извлекает отдельные пункты.

    Args:
        plan_text (str): Сформированный план.

    Returns:
        List[str]: Список пунктов плана.
    """
    points = re.split(r'\d+\)\s', plan_text)
    points = [point.strip() for point in points if point.strip()]
    logger.info(f"План ответа: {points}")
    return points


async def generate_plan(user_question: str, llm) -> str:
    """
    Генерирует план ответа на основе пользовательского запроса.

    Args:
        user_question (str): Вопрос пользователя.

    Returns:
        str: Сформированный план ответа.
    """
    try:
        kb_results = knowledge_base_search(user_question)

        plan_prompt = f"""
        You are an expert in cryptocurrencies and blockchain technologies. Your task is to create a response plan strictly focused on the specified topic and strictly within the scope of the user's question.

        User question: "{user_question}"

        Below are the results from the knowledge base search that may help you generate a more accurate and helpful plan:
        ---
        {kb_results}
        ---

        ⚠️ Strict requirements for the plan:

        1) List format:
           1) First item of the plan.
           2) Second item of the plan.
           ...
           N) Final item of the plan.
           Each item must begin with a number, followed by “)” and a space.

        2) Topical relevance:
           - If the question mentions specific technologies (e.g., “air-gapped wallet” or “indicators”),
             each item in the plan must explicitly describe or address these technologies.
           - It is prohibited to describe general scenarios or list cryptocurrencies/protocols not related to the question.

        3) Specificity and brevity:
           - Each item must be clear and concise, without unnecessary detail or filler content.
           - Do not use vague or general phrases — only specific information relevant to the question.

        4) Keywords:
           - If the question contains specific terms (e.g., “indicators”, “air-gapped”),
             each item in the plan must mention these terms or their direct synonyms.

        5) Relevance check:
           - Note that today’s date is: {datetime.now()}.
           - Only use facts from the knowledge base above if they are truly useful for the plan.

        Generate a detailed plan strictly following all the above constraints.
        """

        messages = [SystemMessage(content=plan_prompt)]
        response = llm(messages)
        text = response.content.strip()
        logger.info(f"План ответа для модели: {text}")
        return text

    except Exception as e:
        logger.error(f"Ошибка при генерации плана: {e}")

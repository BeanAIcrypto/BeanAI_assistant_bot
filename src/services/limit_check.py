import logging
import os
from dotenv import load_dotenv

from aiogram.types import Message
from src.bot.bot_messages import MESSAGES
from src.services.analytics_creating_target import analytics_creating_target

load_dotenv()
logger = logging.getLogger(__name__)

async def limit_check(limit: int, message: Message, user_id: int, user_name: str) -> bool:
    """
    Проверяет лимит запросов пользователя и отправляет уведомление, если лимит превышен или не установлен.

    Args:
        limit (int): Текущий лимит запросов пользователя.
        message (Message): Сообщение для отправки уведомления.
        user_id (int): ID пользователя, чей лимит проверяется.
        user_name (str): Имя пользователя для логирования.

    Returns:
        bool: True, если лимит не превышен, иначе False.

    Raises:
        Exception: Если произошла ошибка при проверке лимита.
    """
    try:
        if limit is None:
            logger.error(f"Лимит для пользователя {user_id} не найден.")
            return False

        if limit <= 0:
            await message.answer(MESSAGES["get_user_limit"]["en"])
            await analytics_creating_target(user_id, user_name, target_start_id=os.getenv("TARGET_START_ID_LIMIT"), value=None, unit=None)
            return False

        return True
    except Exception as e:
        logger.error(f"Ошибка при проверке лимита для пользователя {user_id}: {str(e)}")
        await message.reply("Произошла ошибка при проверке лимита. Попробуйте позже.")
        return False

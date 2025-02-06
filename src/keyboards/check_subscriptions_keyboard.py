import logging
import os
from typing import Literal
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def check_subscriptions_keyboard(language: Literal["en", "en"]) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для подписки в зависимости от языка.

    Args:
        language (Literal["en", "en"]): Язык пользователя ("en" или "en").

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой подписки.

    Raises:
        EnvironmentError: Если переменная окружения 'CHANNEL_LINK' отсутствует.
        ValueError: Если язык не поддерживается.
        RuntimeError: При любой другой неизвестной ошибке.
        Exception: При возникновении других ошибок.
    """
    try:
        channel_link = os.getenv("CHANNEL_LINK")
        if not channel_link:
            logger.error("Переменная окружения 'CHANNEL_LINK' не установлена")
            raise EnvironmentError("Переменная окружения 'CHANNEL_LINK' не установлена")

        if language == "en":
            buttons = [[InlineKeyboardButton(text='Подписаться', url=channel_link)]]
        elif language == "en":
            buttons = [[InlineKeyboardButton(text='Subscribe', url=channel_link)]]
        else:
            logger.warning(f"Неизвестный язык: {language}")
            raise ValueError(f"Unsupported language: {language}")

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        return keyboard

    except EnvironmentError as env_error:
        logger.error(f"Ошибка окружения: {env_error}")
        raise
    except ValueError as value_error:
        logger.error(f"Ошибка значения: {value_error}")
        raise
    except RuntimeError as runtime_error:
        logger.error(f"Неизвестная ошибка при создании клавиатуры для выбора языка: {runtime_error}")
        raise
    except Exception as error:
        logger.error(f"Неизвестная ошибка при создании клавиатуры: {error}")
        raise

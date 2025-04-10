import logging
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from src.bot.bot_messages import MESSAGES

logger = logging.getLogger(__name__)


def get_reminder_keyboard(language: str) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для напоминаний с вариантами стратегий.

    Args:
        language (str): Язык, на котором будут отображаться кнопки.

    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура с кнопками для выбора стратегии.

    Raises:
        KeyError: Если язык отсутствует в словаре сообщений.
        ValueError: Если язык не поддерживается.
        RuntimeError: При любой другой неизвестной ошибке.
        Exception: При возникновении других ошибок.
    """
    try:
        if (
            language not in MESSAGES["strategy_investment"]
            or language not in MESSAGES["improve_portfolio"]
        ):
            logger.error(f"Язык '{language}' не поддерживается.")
            raise ValueError(f"Unsupported language: {language}")

        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton(
                text=MESSAGES["strategy_investment"][language],
                callback_data="strategy_investment",
            ),
            InlineKeyboardButton(
                text=MESSAGES["improve_portfolio"][language],
                callback_data="improve_portfolio",
            ),
        )
        logger.info(
            f"Клавиатура для напоминаний успешно создана для языка: {language}"
        )
        return keyboard

    except KeyError as key_error:
        logger.error(
            f"Ошибка доступа к ключу словаря сообщений для языка '{language}': {key_error}"
        )
        raise
    except ValueError as value_error:
        logger.error(
            f"Некорректный язык '{language}' при создании клавиатуры: {value_error}"
        )
        raise
    except RuntimeError as runtime_error:
        logger.error(
            f"Неизвестная ошибка при создании клавиатуры для выбора языка: {runtime_error}"
        )
        raise
    except Exception as error:
        logger.error(
            f"Неизвестная ошибка при создании клавиатуры для языка '{language}': {error}"
        )
        raise

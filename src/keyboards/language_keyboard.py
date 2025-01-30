import logging
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

def create_language_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для выбора языка.

    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура с кнопками для выбора языка.

    Raises:
        MemoryError: Если произошла ошибка выделения памяти.
        RuntimeError: При любой другой неизвестной ошибке.
        Exception: При возникновении других ошибок.
    """
    try:
        buttons = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="🇬🇧 English")],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="🇷🇺 Русский")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        logger.info("Клавиатура для выбора языка успешно создана")
        return keyboard
    except RuntimeError as runtime_error:
        logger.error(f"Неизвестная ошибка при создании клавиатуры для выбора языка: {runtime_error}")
        raise
    except Exception as generic_error:
        logger.error(f"Общая ошибка при создании клавиатуры для выбора языка: {generic_error}")
        raise

def create_language_keyboard_start() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для выбора языка при начале программы.

    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура с кнопками для выбора языка.

    Raises:
        MemoryError: Если произошла ошибка выделения памяти.
        RuntimeError: При любой другой неизвестной ошибке.
        Exception: При возникновении других ошибок.
    """
    try:
        buttons = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="🇬🇧 English Start")],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="🇷🇺 Русский Старт")]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        logger.info("Клавиатура для выбора языка успешно создана")
        return keyboard
    except RuntimeError as runtime_error:
        logger.error(f"Неизвестная ошибка при создании клавиатуры для выбора языка: {runtime_error}")
        raise
    except Exception as generic_error:
        logger.error(f"Общая ошибка при создании клавиатуры для выбора языка: {generic_error}")
        raise

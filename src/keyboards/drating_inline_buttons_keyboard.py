import logging
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)


def drating_inline_buttons_keyboard(response_id: int) -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для оценки ответа.

    Args:
        response_id (int): Идентификатор ответа, для которого создается клавиатура.

    Returns:
        InlineKeyboardMarkup: Инлайн-клавиатура с кнопками для оценки.

    Raises:
        ValueError: Если response_id имеет недопустимое значение.
        RuntimeError: При любой другой неизвестной ошибке.
        Exception: При возникновении других ошибок.
    """
    try:
        if not isinstance(response_id, int) or response_id < 0:
            logger.warning(f"Некорректное значение response_id: {response_id}")
            raise ValueError(f"Некорректное значение response_id: {response_id}")

        buttons = [
            [InlineKeyboardButton(text=emoji, callback_data=f"rate_{emoji}_{response_id}")
             for emoji in ['👎', '😐', '👍']]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        logger.info(f"Инлайн-клавиатура для оценки создана для response_id: {response_id}")
        return keyboard

    except ValueError as value_error:
        logger.error(f"Ошибка значения при создании клавиатуры: {value_error}")
        raise
    except RuntimeError as runtime_error:
        logger.error(f"Неизвестная ошибка при создании клавиатуры для выбора языка: {runtime_error}")
        raise
    except Exception as error:
        logger.error(f"Неизвестная ошибка при создании инлайн-клавиатуры для response_id {response_id}: {error}")
        return InlineKeyboardMarkup()


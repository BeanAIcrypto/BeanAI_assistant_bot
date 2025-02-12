import logging
import os

from aiogram import Bot
from aiogram.types import ChatMember
from aiogram.utils.exceptions import ChatNotFound, Unauthorized
from src.keyboards.check_subscriptions_keyboard import (
    check_subscriptions_keyboard,
)


logger = logging.getLogger(__name__)

CHANNEL_ID = os.getenv("CHANNEL_ID")


async def check_subscription(user_id: int, bot: Bot) -> bool:
    """
    Проверяет, подписан ли пользователь на канал.

    Args:
        user_id (int): ID пользователя.
        bot (Bot): Экземпляр бота.

    Returns:
        bool: True, если пользователь подписан на канал, иначе False.

    Raises:
        ChatNotFound: Если канал не найден.
        Unauthorized: Если бот не имеет доступа к каналу.
        Exception: Для любых других ошибок, возникающих при проверке подписки.
    """
    try:
        if not CHANNEL_ID:
            logger.error(
                "CHANNEL_ID не установлен. Проверьте переменные окружения."
            )
            return False

        chat_member: ChatMember = await bot.get_chat_member(
            CHANNEL_ID, user_id
        )
        logger.info(f"Пользователь {user_id} статус {chat_member.status}.")
        if chat_member.status in ["member", "administrator", "creator"]:
            logger.info(f"Пользователь {user_id} подписан на канал.")
            return True
        else:
            logger.info(
                f"Пользователь {user_id} не подписан на канал. Статус: {chat_member.status}"
            )
            return False

    except ChatNotFound:
        logger.error(
            "Канал не найден. Проверьте CHANNEL_ID и убедитесь, что бот добавлен в канал."
        )
        return False
    except Unauthorized:
        logger.error(
            "Бот не имеет доступа к каналу. Проверьте права доступа бота."
        )
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке подписки: {e}")
        return False


async def subscription(user_id: int, language: str, message, bot: Bot) -> bool:
    """
    Проверяет подписку пользователя на канал и отправляет сообщение с просьбой подписаться, если необходимо.

    Args:
        user_id (int): ID пользователя.
        language (str): Язык для сообщения.
        message: Сообщение для ответа пользователю.
        bot (Bot): Экземпляр бота.

    Returns:
        bool: True, если пользователь подписан на канал, иначе False.

    Raises:
        Exception: Для любых ошибок, возникающих при проверке подписки.
    """
    try:
        logger.info(
            f"Проверка подписки для пользователя {user_id} на языке {language}"
        )

        if not await check_subscription(user_id, bot):
            sub_message = {
                "en": f"Подпишитесь на наш <a href='{os.getenv('CHANNEL_LINK')}'>Telegram-канал</a> 😎",
                "en": f"Please subscribe to our <a href='{os.getenv('CHANNEL_LINK')}'>Telegram channel</a> 😎",
            }.get(language, "Please subscribe to our channel.")

            logger.info(
                f"Пользователь {user_id} не подписан, отправлено сообщение с просьбой подписаться."
            )
            await message.reply(
                sub_message,
                parse_mode="HTML",
                reply_markup=check_subscriptions_keyboard(language),
            )
            return False

        logger.info(f"Пользователь {user_id} подписан.")
        return True
    except Exception as e:
        logger.error(
            f"Ошибка при проверке подписки для пользователя {user_id}: {str(e)}"
        )
        return False

from langchain_community.document_loaders import YoutubeLoader
import logging
from typing import Optional
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
)
from src.bot.bot_messages import MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING

logger = logging.getLogger(__name__)

async def you_tube_link_processing(
    url: str, user_id: int, message, bot
) -> Optional[str]:
    """
    Обрабатывает YouTube-ссылку и получает текст транскрипции, если субтитры доступны.

    Args:
        url (str): Ссылка на YouTube-видео.
        user_id (int): Идентификатор пользователя Telegram.
        message: Объект сообщения Telegram.
        bot: Telegram-бот.

    Returns:
        Optional[str]: Текст субтитров или None, если субтитры отсутствуют.
    """
    try:
        logger.info(f"[USER {user_id}] Начало обработки видео: {url}")

        # Загружаем субтитры
        loader = YoutubeLoader.from_youtube_url(
            url,
            add_video_info=False,
            language=["ru", "en", "auto"],
        )
        documents = loader.load()  # documents - это список объектов Document

        # Проверяем, есть ли транскрипция
        if not documents:
            logger.warning(f"[USER {user_id}] Видео {url} не содержит транскрипции.")
            await message.answer(MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING["no_transcript"])
            return None

        # Извлекаем текст из списка документов
        transcripts = "\n".join([doc.page_content for doc in documents])

        logger.info(f"[USER {user_id}] Успешно получена транскрипция (первые 500 символов): {transcripts[:500]}")

        return transcripts

    except NoTranscriptFound:
        logger.warning(f"[USER {user_id}] Не найдено доступных субтитров для видео {url}.")
        await message.answer(MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING["no_transcript"])
        return None

    except TranscriptsDisabled:
        logger.warning(f"[USER {user_id}] У видео {url} отключены субтитры.")
        await message.answer(MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING["transcripts_disabled"])
        return None

    except ConnectionError:
        logger.error(f"[USER {user_id}] Ошибка соединения при загрузке субтитров для видео {url}.")
        await message.answer(MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING["connection_error"])
        return None

    except TimeoutError:
        logger.error(f"[USER {user_id}] Превышено время ожидания при загрузке субтитров для видео {url}.")
        await message.answer(MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING["timeout_error"])
        return None

    except PermissionError:
        logger.error(f"[USER {user_id}] Ошибка прав доступа при обработке видео {url}.")
        await message.answer(MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING["permission_error"])
        return None

    except ImportError:
        logger.critical(
            '[SYSTEM] Ошибка импорта "youtube_transcript_api". Проверьте, что библиотека установлена (`pip install youtube-transcript-api`).'
        )
        await message.answer(MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING["unknown_error"])
        return None

    except ValueError:
        logger.error(f"[USER {user_id}] Ошибка значения при обработке видео {url}.")
        await message.answer(MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING["unknown_error"])
        return None

    except TypeError:
        logger.error(f"[USER {user_id}] Ошибка типа данных при обработке видео {url}.")
        await message.answer(MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING["unknown_error"])
        return None

    except Exception as e:
        logger.critical(f"[USER {user_id}] Непредвиденная ошибка при обработке видео {url}: {str(e)}", exc_info=True)
        await message.answer(MESSAGES_ERROR_YOU_TUBE_LINK_PROCESSING["unknown_error"])
        return None


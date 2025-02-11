import logging
import os
import uuid
from typing import Tuple

import aiohttp
from dotenv import load_dotenv

from db.dbworker import get_user_limit, update_user_limit
from src.bot.bot_messages import MESSAGES, MESSAGES_ERROR
from src.services.count_token import count_vois_tokens
from src.services.limit_check import limit_check
from src.services.clear_directory import clear_directory
from src.services.count_token import count_output_tokens

load_dotenv()
logger = logging.getLogger(__name__)

async def transcribe_voice_message(message, user_id: int, user_name: str, bot) -> str:
    """
    Обрабатывает транскрипцию голосового сообщения.

    Args:
        message: Сообщение Telegram с голосовым сообщением.
        user_id (int): Идентификатор пользователя Telegram.
        user_name (str): Имя пользователя Telegram.
        bot: Telegram-бот.
    Returns:
        Optional[str]: Текст транскрипции или None в случае ошибок.

    Raises:
        ValueError: Ошибка проверки лимита или данных.
        Exception: Общая ошибка обработки голосового сообщения.
    """
    request_id = str(uuid.uuid4())
    base_dir = os.path.join("downloads", str(user_id), request_id)
    os.makedirs(base_dir, exist_ok=True)
    audio_path = os.path.join(base_dir, "voice_response.mp3")
    try:

        new_file = await message.voice.get_file()
        await new_file.download(destination_file=audio_path)

        voice_token = await count_vois_tokens([audio_path])
        user_token = get_user_limit(user_id)
        remaining_limit = user_token - voice_token

        if not await limit_check(remaining_limit, message, user_id, user_name):
            logger.info(f'Пользователь {user_name} (ID: {user_id}) превысил дневной лимит.')
            await message.answer(MESSAGES_ERROR["limit_exceeded"]["en"])
            return None

        transcript_text, token = await transcribe_voice(audio_path, message, user_id, bot)

        if not transcript_text:
            logger.warning(f"Транскрипция вернула пустой результат для {audio_path}.")
            await message.answer(MESSAGES_ERROR["empty_transcription"]["en"])
            return None

        logger.info(f"Результат транскрипции: {transcript_text[:50]}")
        return transcript_text

    except ValueError as ve:
        logger.error(f"Ошибка проверки лимита или валидации данных: {ve}")
        await message.answer(MESSAGES_ERROR["limit_exceeded"]["en"])
        return None

    except Exception as e:
        logger.error(f"Ошибка обработки голосового сообщения: {e}")
        await message.answer(MESSAGES_ERROR["empty_transcription"]["en"])
        return None
    finally:
        await clear_directory(base_dir)



async def transcribe_voice(audio_path: str, message, user_id: int, bot) -> Tuple[str, str]:
    """
    Выполняет транскрипцию голосового сообщения с использованием модели OpenAI Whisper.

    Args:
        audio_path (str): Путь к аудиофайлу.
        message: Сообщение Telegram для контекста.
        user_id (int): Уникальный идентификатор пользователя.
        bot: Telegram-бот.
    Returns:
        Optional[str]: Текст транскрипции или None в случае ошибки.

    Raises:
        ValueError: Если ключ API OpenAI не установлен или возникла ошибка запроса.
        Exception: Общая ошибка при выполнении транскрипции.
    """
    try:
        api_key = os.getenv("GPT_SECRET_KEY_FASOLKAAI")
        if not api_key:
            raise ValueError("Ключ API OpenAI не установлен.")

        url = "https://api.openai.com/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {api_key}"}

        async with aiohttp.ClientSession() as session:
            with open(audio_path, "rb") as audio_file:
                data = aiohttp.FormData()
                data.add_field("model", "whisper-1")
                data.add_field("file", audio_file, filename=os.path.basename(audio_path))

                async with session.post(url, headers=headers, data=data) as response:
                    if response.status != 200:
                        error_message = await response.text()
                        raise ValueError(f"Ошибка запроса: {response.status} - {error_message}")

                    result = await response.json()
                    transcript_text = result.get("text")
                    if transcript_text:
                        token_count = count_output_tokens(transcript_text, model="gpt-4")
                        limit = get_user_limit(user_id)
                        if limit - token_count <= 0:
                            logger.warning("Недостаточно токенов.")
                            await bot.edit_message_text(text=MESSAGES["token_limit_exceeded"]["en"])
                            return
                        update_user_limit(user_id, limit - token_count)
                        logger.info(f"Транскрибированный текст содержит {token_count} токенов.")
                        logger.info(f"лимит пользователя: {limit - token_count}")

                    else:
                        logger.warning("Транскрипция вернула пустой текст.")
                        return None, 0

                    return transcript_text, token_count

    except ValueError as ve:
        logger.error(f"Ошибка валидации данных: {ve}")
        await message.answer("Произошла ошибка при проверке API ключа или данных.")
        return None

    except aiohttp.ClientError as ce:
        logger.error(f"Ошибка соединения с API OpenAI: {ce}")
        await message.answer("Произошла ошибка подключения к сервису транскрипции.")
        return None

    except Exception as e:
        logger.error(f"Ошибка транскрипции: {e}")
        await message.answer("Произошла ошибка при обработке аудиофайла.")
        return None

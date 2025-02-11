import asyncio
import yt_dlp
import os
import logging
import uuid
from typing import Optional, List

from src.bot.bot_messages import MESSAGES
from src.converter.voice_processing import transcribe_voice
from db.dbworker import get_user_limit, update_user_limit
from src.services.count_token import count_vois_tokens
from src.services.clear_directory import clear_directory


logger = logging.getLogger(__name__)
GPT_SECRET_KEY_FASOLKAAI = os.getenv("GPT_SECRET_KEY_FASOLKAAI")


def download_audio_from_youtube(url: str, output_dir: str) -> Optional[str]:
    """
    Загружает аудио с YouTube и сохраняет его в формате MP3 в заданную директорию.

    Args:
        url (str): Ссылка на YouTube-видео.
        output_dir (str): Директория для сохранения файла.

    Returns:
        Optional[str]: Путь к загруженному аудиофайлу или None в случае ошибки.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "youtube.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": output_file,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download([url])
            if error_code == 0:
                output_mp3 = os.path.join(output_dir, "youtube.mp3")
                logger.info(f"Аудиофайл успешно загружен: {output_mp3}")
                return output_mp3
    except yt_dlp.DownloadError as e:
        logger.error(f"Ошибка загрузки аудио с YouTube: {str(e)}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка загрузки аудио: {str(e)}")
    return None


async def split_audio_file(
    input_file: str, output_dir: str, segment_length: int = 600
) -> Optional[List[str]]:
    """
    Разбивает аудиофайл на части заданной длины, сохраняя их в указанную директорию.

    Args:
        input_file (str): Путь к входному аудиофайлу.
        output_dir (str): Директория для сохранения частей.
        segment_length (int): Длина сегмента в секундах. По умолчанию 600.

    Returns:
        Optional[List[str]]: Список путей к частям аудиофайла или None в случае ошибки.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)

        # Шаблон выходных файлов
        output_pattern = os.path.join(output_dir, "part_%03d.mp3")
        split_command = [
            "ffmpeg",
            "-i",
            input_file,
            "-f",
            "segment",
            "-segment_time",
            str(segment_length),
            "-c",
            "copy",
            output_pattern,
        ]
        process = await asyncio.create_subprocess_exec(
            *split_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info(f"Аудиофайл разбит на части в папке: {output_dir}")
            parts = [
                os.path.join(output_dir, f)
                for f in os.listdir(output_dir)
                if f.startswith("part_")
            ]
            return sorted(parts)
        else:
            logger.error(f"Ошибка при разбиении аудиофайла: {stderr.decode()}")
    except Exception as e:
        logger.error(f"Ошибка разбиения аудиофайла: {str(e)}")
    return None


async def transcribe_audio_part(
    audio_parts: List[str], message, user_id, bot
) -> str:
    """
    Выполняет транскрипцию частей аудиофайла.

    Args:
        audio_parts (List[str]): Список путей к частям аудиофайла.
        message: Объект сообщения Telegram для уведомлений.
        user_id (int): Уникальный идентификатор пользователя.
        bot: Telegram-бот.

    Returns:
        str: Полный текст транскрипции аудио.
    """
    full_transcript = []
    count_token = 0
    limit = get_user_limit(user_id)
    for idx, part in enumerate(audio_parts):
        try:
            logger.info(
                f"Транскрипция части {idx + 1}/{len(audio_parts)}: {part}"
            )
            transcribe_text, token = await transcribe_voice(
                part, message, user_id, bot
            )
            full_transcript.append(transcribe_text)
            count_token += token
        except Exception as e:
            logger.error(f"Ошибка транскрипции части {idx + 1}: {str(e)}")
    update_user_limit(user_id, limit - count_token)
    return "\n".join(full_transcript)


async def you_tube_link_processing(
    url: str, user_id: int, message, bot
) -> Optional[str]:
    """
    Основная функция для обработки YouTube-ссылки: загрузка аудио, разбиение на части и транскрипция.

    Args:
        url (str): Ссылка на YouTube-видео.
        user_id (int): Идентификатор пользователя Telegram.
        message: Объект сообщения Telegram для взаимодействия с пользователем.
        bot: Telegram-бот.
    Returns:
        Optional[str]: Полный текст транскрипции или None в случае ошибки.
    """
    request_id = str(uuid.uuid4())
    base_dir = f"downloads/{user_id}/{request_id}"

    audio_dir = os.path.join(base_dir, "audio")
    split_dir = os.path.join(base_dir, "parts")

    try:
        os.makedirs(audio_dir, exist_ok=True)

        audio_file = download_audio_from_youtube(url, audio_dir)
        if not audio_file:
            logger.error("Не удалось загрузить видео")
            await message.answer(
                MESSAGES["you_tube_link_processing_error_download"]["en"]
            )
            return None

        audio_parts = await split_audio_file(audio_file, split_dir)
        if not audio_parts:
            logger.error("Не удалось разбить аудио файл на части")
            await message.answer(
                MESSAGES["you_tube_link_processing_error"]["en"]
            )
            return None

        voice_token = await count_vois_tokens(audio_parts)
        user_token = get_user_limit(user_id)
        remaining_tokens = user_token - voice_token
        if remaining_tokens <= 0:
            logger.info(
                f"Пользователь превысил лимит на день: {user_token - voice_token}"
            )
            await message.answer(MESSAGES["count_vois_tokens"]["en"])
            return None

        update_user_limit(user_id, remaining_tokens)

        logger.info(
            f"Начинаем транскрипцию всех частей файла для пользователя {user_id}: {audio_file}"
        )
        full_transcript = await transcribe_audio_part(
            audio_parts, message, user_id, bot
        )
        return full_transcript

    except ValueError as ve:
        logger.error(f"Ошибка лимита токенов: {str(ve)}")
        await message.answer(MESSAGES["count_vois_tokens"]["en"])
    except RuntimeError as re:
        logger.error(f"Ошибка обработки аудиофайла: {str(re)}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при обработке видео: {str(e)}")
    finally:
        await clear_directory(base_dir)
    return None

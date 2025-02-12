import asyncio
import logging
from typing import List

import tiktoken

logger = logging.getLogger(__name__)


def count_output_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Подсчитывает количество токенов в заданном тексте для указанной модели.

    Args:
        text (str): Текст для подсчёта токенов.
        model (str): Название модели для подсчёта токенов (по умолчанию "gpt-4").

    Returns:
        int: Количество токенов в тексте.

    Raises:
        Exception: Для любых ошибок при подсчёте токенов.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        tokens = encoding.encode(text)
        logger.info(f"Токенов выходных данных: {len(tokens)}")
        return len(tokens)
    except Exception as e:
        logger.error(f"Ошибка подсчёта токенов: {e}")
        raise


def count_input_tokens(
    history: List[dict] = [],
    user_input: str = "",
    prompt: str = "",
    model: str = "gpt-4",
) -> int:
    """
    Подсчитывает общее количество токенов в истории чата и текущем запросе пользователя.

    Args:
        history (List[dict]): История чата в виде списка словарей с ключами 'question' и 'response'.
        user_input (str): Текущий ввод пользователя.
        prompt (str): системный промт.
        model (str): Название модели для подсчёта токенов (по умолчанию "gpt-4").

    Returns:
        int: Общее количество токенов.

    Raises:
        ValueError: Если отсутствуют обязательные ключи в записях истории.
        Exception: Для любых других ошибок.
    """
    try:
        messages = []

        if prompt.strip():
            messages.append({"role": "system", "content": prompt})

        for entry in history:
            if "question" not in entry or "response" not in entry:
                raise ValueError(
                    f"Отсутствуют обязательные ключи в записи истории: {entry}"
                )
            messages.append({"role": "user", "content": entry["question"]})
            messages.append(
                {"role": "assistant", "content": entry["response"]}
            )

        messages.append({"role": "user", "content": user_input})

        encoding = tiktoken.encoding_for_model(model)
        total_tokens = 0
        for msg in messages:
            role_tokens = encoding.encode(msg["role"])
            content_tokens = encoding.encode(msg["content"])
            total_tokens += len(role_tokens) + len(content_tokens)
        logger.info(f"Токенов входных данных: {total_tokens}")
        return total_tokens
    except ValueError as ve:
        logger.error(f"Ошибка в данных истории чата: {ve}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при подсчёте токенов: {e}")
        raise


async def get_audio_duration(audio_file: str) -> float:
    """
    Определяет продолжительность аудиофайла с использованием ffprobe.

    Args:
        audio_file (str): Путь к аудиофайлу.

    Returns:
        float: Продолжительность аудиофайла в секундах.

    Raises:
        ValueError: Если ffprobe возвращает некорректный результат.
        Exception: Для всех других ошибок при выполнении ffprobe.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            try:
                duration = float(stdout.strip())
                if duration < 0:
                    raise ValueError(
                        f"Отрицательная продолжительность: {duration}"
                    )
                return duration
            except ValueError as ve:
                logger.error(
                    f"Ошибка преобразования продолжительности в число: {ve}"
                )
                return 0.0
        else:
            logger.error(f"Ошибка ffprobe: {stderr.decode().strip()}")
            return 0.0
    except FileNotFoundError:
        logger.error("ffprobe не установлен или недоступен в PATH.")
        return 0.0
    except Exception as e:
        logger.error(f"Ошибка при получении продолжительности аудиофайла: {e}")
        return 0.0


async def count_vois_tokens(audio_parts: List[str]) -> int:
    """
    Оценивает количество токенов для аудиофайлов на основе их общей продолжительности.

    Args:
        audio_parts (List[str]): Список путей к частям аудиофайла.

    Returns:
        int: Оценочное количество токенов.

    Raises:
        ValueError: Если длительность аудиофайлов некорректна.
        Exception: Для всех других ошибок при обработке аудиофайлов.
    """
    try:
        durations = await asyncio.gather(
            *[get_audio_duration(part) for part in audio_parts]
        )
        total_duration = sum(durations)
        if total_duration <= 0:
            raise ValueError(
                "Общая длительность аудио равна нулю или отрицательная."
            )

        token_per_minute = 400
        estimated_tokens = (total_duration / 60) * token_per_minute
        logger.info(
            f"Оценочное количество токенов для аудио: {estimated_tokens}"
        )
        return int(estimated_tokens)
    except ValueError as ve:
        logger.error(f"Ошибка в оценке длительности аудио: {ve}")
        return 0
    except Exception as e:
        logger.error(f"Ошибка при подсчете токенов для аудио: {e}")
        return 0

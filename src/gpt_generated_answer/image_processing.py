import os
import base64
import uuid
from typing import Tuple

from dotenv import load_dotenv
import tiktoken
import requests
import logging
from langchain_openai import ChatOpenAI
from db.dbworker import get_user_limit
from src.bot.bot_messages import MESSAGES
from db.dbworker import update_user_limit
from src.services.count_token import count_input_tokens
from src.services.clear_directory import clear_directory
from aiogram import types
from langchain.schema import HumanMessage, SystemMessage


load_dotenv()
logger = logging.getLogger(__name__)

client = ChatOpenAI(model_name="gpt-4o-mini", openai_api_key=os.getenv("GPT_SECRET_KEY_FASOLKAAI"))


async def encode_image(image_path: str) -> str:
    """
    Кодирует изображение в формат Base64.

    Args:
        image_path (str): Путь к изображению.

    Returns:
        str: Строка в формате Base64.

    Raises:
        FileNotFoundError: Файл изображения не найден.
        IOError: Ошибка чтения файла изображения.
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except FileNotFoundError as e:
        logger.error(f"Файл изображения не найден: {e}")
        raise
    except IOError as e:
        logger.error(f"Ошибка чтения файла изображения: {e}")
        raise


async def downloads_image(
    message: types.Message, file_url: str
) -> Tuple[str, str]:
    """
    Загружает изображение по указанному URL в уникальную директорию.

    Args:
        message (types.Message): Сообщение Telegram.
        file_url (str): URL изображения.

    Returns:
        str: Путь к загруженному изображению или None, если загрузка не удалась.
    """
    user_id = message.from_user.id
    request_id = str(uuid.uuid4())
    base_dir = os.path.join("downloads", str(user_id), request_id)
    os.makedirs(base_dir, exist_ok=True)

    image_path = os.path.join(base_dir, "image.jpg")

    try:
        logger.info("URL изображения: %s", file_url)
        logger.info("Загрузка изображения...")
        response = requests.get(file_url)

        if response.status_code != 200:
            logger.error(
                "Ошибка загрузки изображения. Статус код: %s",
                response.status_code,
            )
            await message.reply(
                "Error loading the image. Try again."
            )
            return None

        with open(image_path, "wb") as f:
            f.write(response.content)
            logger.info("Изображение успешно загружено в %s", image_path)
        return image_path, base_dir
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Ошибка запроса при загрузке изображения: {e}", exc_info=True
        )
        await message.reply(
            "There was an error loading the image. Try again."
        )
    except Exception as e:
        logger.error(
            f"Неизвестная ошибка при работе с изображением: {e}", exc_info=True
        )
        await message.reply(
            "An unknown error occurred during image processing. "
        )


async def image_processing(
    message, question: str, bot, user_id: int, file_url: str, prompt: str
) -> str:
    """
    Обрабатывает изображение и отправляет запрос к OpenAI для получения описания.

    Args:
        message: Сообщение Telegram.
        question (str): Вопрос пользователя.
        bot: Экземпляр Telegram-бота.
        user_id (int): ID пользователя.
        file_url (str): Путь к картинке.
        prompt (str): Промт с текущей датой.

    Returns:
        None

    Raises:
        ValueError: Ошибка в ответе от OpenAI.
    """
    image_path, base_dir = await downloads_image(message, file_url)
    base64_image = await encode_image(image_path)
    logger.info("Изображение успешно загружено.")
    try:
        user_query = (
            message.caption if message.caption else "Опишите изображение."
        )
        logger.info("Подготовка текста запроса: %s", user_query)

        messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": prompt}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": question,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        },
                    },
                ],
            },
        ]

        logger.info("Подсчёт токенов в запросе...")
        encoding = tiktoken.encoding_for_model("gpt-4o")
        num_tokens = sum(len(encoding.encode(str(msg))) for msg in messages)
        limit = get_user_limit(user_id)

        if limit - num_tokens <= 0:
            logger.warning("Недостаточно токенов.")
            await bot.edit_message_text(
                text=MESSAGES["token_limit_exceeded"]["en"]
            )
            return

        logger.info("Отправка изображения и запроса в OpenAI...")
        response = client.invoke(messages)
        response_text = response.content

        total_tokens_response = count_input_tokens(
            user_input=response_text, model="gpt-4o"
        )
        update_user_limit(
            user_id, limit - (num_tokens + total_tokens_response)
        )

        logger.info(response_text)
        if response_text:
            logger.info("Успешно получен ответ от OpenAI.")
            return response_text
        else:
            raise ValueError("Ответ от OpenAI не содержит контента.")
    except ValueError as e:
        logger.error(f"Ошибка обработки ответа от OpenAI: {e}")
        await message.reply("The response from OpenAI does not include a description.")
    except Exception as e:
        logger.error(f"Ошибка обработки изображения: {e}")
        await message.reply("An error occurred during image processing.")
    finally:
        await clear_directory(base_dir)


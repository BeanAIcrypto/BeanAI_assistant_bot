import os
import re
import asyncio
import logging
import uuid

import psycopg2
from dotenv import load_dotenv
from aiogram import Dispatcher, types
from aiogram.types import ContentType, ContentTypes

from config.bot_config import bot, dp
from src.services.limit_check import limit_check
from src.services.analytics_creating_target import analytics_creating_target
from src.converter.document_processing import text_extraction_from_a_document
from src.converter.voice_processing import transcribe_voice_message
from src.converter.link_processing import link_processing
from src.converter.you_tube_link_processing import you_tube_link_processing
from src.gpt_generated_answer.process_user_message import process_user_message
from db.dbworker import (
    create_user,
    update_user_language,
    get_user_limit,
    get_user_history,
    update_dialog_score,
)
from src.bot.bot_messages import MESSAGES, MESSAGES_ERROR
from db.background_functions import start_background_tasks
from db.dbworker import get_user_status_you_tube, update_status_you_tube
from src.services.clear_directory import clear_directory


load_dotenv()

logger = logging.getLogger(__name__)
API_TOKEN = os.getenv("TG_TOKEN")

image_path = "downloads/image.jpg"


async def on_startup(dispatcher: Dispatcher) -> None:
    """
    Выполняет действия при старте бота:
    - Запускает фоновые задачи.
    - Устанавливает команды бота.
    - Удаляет вебхук, если он установлен.

    Args:
        dispatcher (Dispatcher): Диспетчер Aiogram.

    Raises:
        asyncio.CancelledError: Если фоновая задача была отменена.
        AttributeError: Если отсутствуют необходимые атрибуты.
        Exception: Любая другая ошибка.
    """
    try:
        asyncio.create_task(start_background_tasks(dp.bot))
        logger.info("Фоновая задача напоминания запущена")

        await set_default_commands(dispatcher)
        await dp.bot.delete_webhook(drop_pending_updates=True)
    except asyncio.CancelledError as cancel_error:
        logger.error(
            f"Фоновая задача была отменена: {cancel_error}", exc_info=True
        )
    except AttributeError as attr_error:
        logger.error(
            f"Ошибка атрибута в on_startup: {attr_error}", exc_info=True
        )
    except Exception as e:
        logger.error(
            f"Неизвестная ошибка при запуске on_startup: {str(e)}",
            exc_info=True,
        )


async def set_default_commands(dp: Dispatcher) -> None:
    """
    Устанавливает команды бота.

    Args:
        dp (Dispatcher): Диспетчер Aiogram.

    Raises:
        ConnectionError: Ошибка подключения.
        ValueError: Неверное значение.
        Exception: Любая другая ошибка.
    """
    try:
        await dp.bot.set_my_commands(
            [types.BotCommand("donate", "Donate/ Оформить донат")]
        )
        logger.info("Команды бота успешно установлены")
    except ConnectionError as conn_error:
        logger.error(
            f"Ошибка подключения при установке команд: {conn_error}",
            exc_info=True,
        )
    except ValueError as value_error:
        logger.error(
            f"Неверное значение при установке команд: {value_error}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"Неизвестная ошибка при установке команд: {str(e)}", exc_info=True
        )


@dp.message_handler(commands=["start"], mention_bot=True)
async def start(message: types.Message) -> None:
    """
    Обрабатывает команду /start:
    - Создает пользователя в базе данных.
    - Отправляет клавиатуру для выбора языка.

    Args:
        message (types.Message): Сообщение пользователя.

    Raises:
        psycopg2.Error: Ошибки взаимодействия с базой данных.
        Exception: Любая другая ошибка.
    """
    user_id = message.from_user.id
    user_name = message.from_user.username

    try:
        create_user(user_id, user_name)
        logger.info(
            f"Пользователь {user_name} (ID: {user_id}) добавлен в базу данных"
        )

        await message.reply(
            MESSAGES["handle_language_choice_first_message"]["en"]
        )
        logger.info(
            f"Пользователь получил привественное сообщение: {user_name}"
        )

        await analytics_creating_target(
            user_id,
            user_name,
            target_start_id=os.getenv("TARGET_START_ID_START"),
        )
    except psycopg2.Error as db_error:
        logger.error(
            f"Ошибка базы данных при обработке команды /start: {db_error}",
            exc_info=True,
        )
        await message.reply(MESSAGES["start_error"])
    except Exception as e:
        logger.error(
            f"Неизвестная ошибка в обработчике команды /start: {e}",
            exc_info=True,
        )
        await message.reply(MESSAGES["start_error"])


@dp.message_handler(commands=["donate"], auto_group=True, mention_bot=True)
async def donate(message: types.Message) -> None:
    """
    Обрабатывает команду /donate, отправляя пользователю ссылку на оплату.

    Args:
        message (types.Message): Сообщение с командой.

    Raises:
        KeyError: Если язык не установлен для пользователя.
        ValueError: Если язык пользователя не поддерживается.
        Exception: Любая другая ошибка.
    """
    user_id = message.from_user.id
    user_name = message.from_user.username

    try:

        await message.answer(MESSAGES["donate"]["en"], parse_mode="MarkdownV2")
        logger.info(
            f"Ссылка на оплату отправлена пользователю {user_name} (ID: {user_id})"
        )

    except KeyError as ke:
        logger.error(
            f"Ошибка языка для пользователя {user_name} (ID: {user_id}): {str(ke)}"
        )
        await message.answer(
            MESSAGES_ERROR["donate_handler_error_language_not_set"]["en"]
        )

    except ValueError as ve:
        logger.error(
            f"Неподдерживаемый язык для пользователя {user_name} (ID: {user_id}): {str(ve)}"
        )
        await message.answer(
            MESSAGES_ERROR["donate_handler_error_language_not_supported"]["en"]
        )

    except Exception as e:
        logger.error(
            f"Неизвестная ошибка в обработчике команды /donate для {user_name} (ID: {user_id}): {str(e)}"
        )
        await message.answer(
            MESSAGES_ERROR["donate_handler_unknown_error"]["en"]
        )


@dp.message_handler(
    auto_group=True, mention_bot=True, content_types=ContentType.VOICE
)
async def voice(message: types.Message) -> None:
    """
    Обрабатывает голосовые сообщения:
    - Выполняет транскрибацию.
    - Отправляет ответ пользователю.

    Args:
        message (types.Message): Сообщение пользователя.

    Raises:
        ValueError: Ошибка транскрибации.
        Exception: Любая другая ошибка.
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        user_name = message.from_user.username
        history = get_user_history(user_id)

        limit = get_user_limit(user_id)
        if not await limit_check(limit, message, user_id, user_name):
            return

        text = await transcribe_voice_message(message, user_id, user_name, bot)
        if not text:
            raise ValueError("Ошибка транскрибации голосового сообщения")

        logger.info(
            f"Пользователь {user_name} (ID: {user_id}) отправил голосовое сообщение: {text}"
        )

        await process_user_message(
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            history=history,
            prompt="text_voice",
            bot=bot,
            message=message,
        )
    except ValueError as value_error:
        logger.error(
            f"Ошибка обработки голосового сообщения: {value_error}",
            exc_info=True,
        )
        await message.reply(MESSAGES_ERROR["voice_error"]["en"])
    except Exception as e:
        logger.error(
            f"Неизвестная ошибка при обработке голосового сообщения: {e}",
            exc_info=True,
        )
        await message.reply(MESSAGES_ERROR["voice_error"]["en"])


@dp.message_handler(
    lambda message: re.search(
        r"https:\/\/(www\.)?(youtube\.com|youtu\.be)\/[^\s]+", message.text
    ),
    auto_group=True,
    mention_bot=True,
)
async def you_tube_link_handler(message: types.Message) -> None:
    """
    Обрабатывает сообщения с ссылками на YouTube:
    - Извлекает текст из видео.
    - Генерирует ответ пользователю.

    Args:
        message (types.Message): Сообщение с YouTube ссылкой.

    Raises:
        ValueError: Ошибка обработки ссылки.
        Exception: Любая другая ошибка.
    """
    user_id = message.from_user.id
    try:
        chat_id = message.chat.id
        user_name = message.from_user.username
        text = message.text

        limit = get_user_limit(user_id)
        if not await limit_check(limit, message, user_id, user_name):
            return

        url_match = re.search(
            r"https:\/\/(www\.)?(youtube\.com|youtu\.be)\/[^\s]+", text
        )
        if url_match:
            url = url_match.group(0)
        else:
            raise ValueError("Не удалось найти YouTube ссылку в тексте")

        logger.info(
            f"Получена ссылка: {url} от пользователя {user_name} (ID: {user_id})"
        )

        history = get_user_history(user_id)

        awaiting_message = await message.answer(
            MESSAGES["link_handler_await"]["en"]
        )

        link_text = await you_tube_link_processing(url, user_id, message, bot)
        if not link_text:
            raise ValueError("Ошибка извлечения текста из YouTube ссылки")

        question = f'Пользователь предоставил ссылку: "{url}". Содержание ссылки:\n{link_text}'
        logger.info(f"Из YouTube ссылки получен текст: {link_text[:1000]}")

        await process_user_message(
            user_id=user_id,
            chat_id=chat_id,
            text=question,
            history=history,
            prompt="you_tube_link",
            bot=bot,
            data_from_question=[text, url],
            message=message,
        )
        await awaiting_message.delete()

    except ValueError as value_error:
        logger.error(
            f"Ошибка обработки YouTube ссылки: {value_error}", exc_info=True
        )
        await message.reply(MESSAGES_ERROR["YouTube_link_handler_error"]["en"])
    except Exception as e:
        logger.error(
            f"Неизвестная ошибка при обработке YouTube ссылки: {e}",
            exc_info=True,
        )
        await message.reply(MESSAGES_ERROR["YouTube_link_handler_error"]["en"])


@dp.message_handler(
    lambda message: re.search(r"https?:\/\/[^\s]+", message.text),
    auto_group=True,
    mention_bot=True,
)
async def link_handler(message: types.Message) -> None:
    """
    Обрабатывает сообщения с ссылками:
    - Извлекает текст из ссылки.
    - Генерирует ответ пользователю.

    Args:
        message (types.Message): Сообщение с ссылкой.

    Raises:
        ValueError: Ошибка обработки ссылки.
        Exception: Любая другая ошибка.
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        user_name = message.from_user.username
        text = message.text

        limit = get_user_limit(user_id)
        if not await limit_check(limit, message, user_id, user_name):
            return

        url_match = re.search(r"https?:\/\/[^\s]+", text)
        if url_match:
            url = url_match.group(0)
        else:
            raise ValueError("Не удалось найти ссылку в тексте")

        logger.info(
            f"Получена ссылка: {url} от пользователя {user_name} (ID: {user_id})"
        )

        history = get_user_history(user_id)

        awaiting_message = await message.answer(
            MESSAGES["link_handler_await"]["en"]
        )

        link_text = await link_processing(url)
        if not link_text:
            raise ValueError("Ошибка извлечения текста из ссылки")

        question = f'Пользователь предоставил ссылку: "{url}". Содержание ссылки:\n{link_text}'
        logger.info(f"Из ссылки получен текст: {link_text[:1000]}")

        await process_user_message(
            user_id=user_id,
            chat_id=chat_id,
            text=question,
            history=history,
            prompt="link",
            bot=bot,
            data_from_question=[text, url],
            message=message,
        )
        await awaiting_message.delete()
    except ValueError as value_error:
        logger.error(f"Ошибка обработки ссылки: {value_error}", exc_info=True)
        await message.reply(MESSAGES_ERROR["link_handler_error"]["en"])
    except Exception as e:
        logger.error(
            f"Неизвестная ошибка при обработке ссылки: {e}", exc_info=True
        )
        await message.reply(MESSAGES_ERROR["link_handler_error"]["en"])


@dp.message_handler(
    auto_group=True, mention_bot=True, content_types=types.ContentTypes.TEXT
)
async def text_handler(message: types.Message) -> None:
    """
    Обрабатывает текстовые сообщения:
    - Выполняет проверку лимитов.
    - Отправляет ответ пользователю.

    Args:
        message (types.Message): Сообщение пользователя.

    Raises:
        ValueError: Ошибка обработки текста.
        Exception: Любая другая ошибка.
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        user_name = message.from_user.username
        text = message.text
        history = get_user_history(user_id)

        limit = get_user_limit(user_id)
        if not await limit_check(limit, message, user_id, user_name):
            return

        logger.info(
            f"Пользователь {user_name} (ID: {user_id}) отправил текстовое сообщение: {text}"
        )

        await process_user_message(
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            history=history,
            prompt="text_voice",
            bot=bot,
            message=message,
        )
    except ValueError as value_error:
        logger.error(
            f"Ошибка обработки текстового сообщения: {value_error}",
            exc_info=True,
        )
        await message.reply(MESSAGES_ERROR["text_error"]["en"])
    except Exception as e:
        logger.error(
            f"Неизвестная ошибка при обработке текстового сообщения: {e}",
            exc_info=True,
        )
        await message.reply(MESSAGES_ERROR["text_error"]["en"])


@dp.message_handler(
    auto_group=True, mention_bot=True, content_types=ContentType.DOCUMENT
)
async def document_handler(message: types.Message) -> None:
    """
    Обрабатывает загруженные документы:
    - Сохраняет документ на сервере.
    - Извлекает текст из документа.

    Args:
        message (types.Message): Сообщение с документом.

    Raises:
        FileNotFoundError: Файл документа не найден.
        ValueError: Ошибка обработки документа.
        Exception: Любая другая ошибка.
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        request_id = str(uuid.uuid4())
        user_name = message.from_user.username

        base_dir = os.path.join("downloads", str(user_id), request_id)
        os.makedirs(base_dir, exist_ok=True)

        document = message.document
        file_name = document.file_name
        file_path = os.path.join(base_dir, file_name)

        file_info = await message.bot.get_file(document.file_id)
        await file_info.download(destination_file=file_path)
        logger.info(f"Файл {file_name} загружен в папку downloads")

        limit = get_user_limit(user_id)
        if not await limit_check(limit, message, user_id, user_name):
            return

        text_extraction_function = text_extraction_from_a_document.get(
            document.mime_type
        )
        if not text_extraction_function:
            await message.answer(
                MESSAGES_ERROR["document_handler_error_type_document"]["en"]
            )
            return

        text_document = text_extraction_function(file_path)
        if not text_document:
            await message.answer(
                MESSAGES_ERROR["document_handler_error_none_document"]["en"]
            )
            return

        logger.info(
            f"Из файла {file_name} извлечен текст: {text_document[:1000]}"
        )

        question = f'Содержание документа "{file_name}":\n{text_document}'
        history = get_user_history(user_id)

        await process_user_message(
            user_id=user_id,
            chat_id=chat_id,
            text=question,
            history=history,
            prompt="document",
            bot=bot,
            data_from_question=[question, file_name],
            message=message,
        )
        logger.info(f"Файл {file_name} был удален после обработки.")
    except FileNotFoundError as file_error:
        logger.error(f"Файл документа не найден: {file_error}", exc_info=True)
        await message.reply(
            MESSAGES_ERROR["document_handler_file_not_found"]["en"]
        )
    except ValueError as value_error:
        logger.error(
            f"Ошибка обработки документа: {value_error}", exc_info=True
        )
        await message.reply(MESSAGES_ERROR["document_handler_error"]["en"])
    except Exception as e:
        logger.error(
            f"Неизвестная ошибка при обработке документа: {e}", exc_info=True
        )
        await message.reply(MESSAGES_ERROR["document_handler_error"]["en"])
    finally:
        await clear_directory(base_dir)


@dp.message_handler(
    content_types=ContentTypes.PHOTO, mention_bot=True, auto_group=True
)
async def handle_photo(message: types.Message) -> None:
    """
    Обрабатывает фотографии:
    - Сохраняет изображение.
    - Отправляет изображение для дальнейшей обработки.

    Args:
        message (types.Message): Сообщение с фотографией.

    Raises:
        FileNotFoundError: Файл изображения не найден.
        ValueError: Ошибка обработки изображения.
        Exception: Любая другая ошибка.
    """
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        user_name = message.from_user.username
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_path = file_info.file_path
        file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_path}"
        logger.info(f"Фотография загружена: {file_url}")

        limit = get_user_limit(user_id)
        if not await limit_check(limit, message, user_id, user_name):
            return

        question = f"Ссылка на изображение: {file_url}"
        history = get_user_history(user_id)

        await process_user_message(
            user_id=user_id,
            chat_id=chat_id,
            text=question,
            history=history,
            prompt="image",
            bot=bot,
            message=message,
            file_url=file_url,
        )
    except FileNotFoundError as file_error:
        logger.error(
            f"Файл изображения не найден: {file_error}", exc_info=True
        )
        await message.reply(
            MESSAGES_ERROR["photo_handler_file_not_found"]["en"]
        )
    except ValueError as value_error:
        logger.error(
            f"Ошибка обработки изображения: {value_error}", exc_info=True
        )
        await message.reply(MESSAGES_ERROR["photo_handler_error"]["en"])
    except Exception as e:
        logger.error(
            f"Неизвестная ошибка при обработке изображения: {e}", exc_info=True
        )
        await message.reply(MESSAGES_ERROR["photo_handler_error"]["en"])


@dp.message_handler(
    auto_group=True, mention_bot=True, content_types=ContentTypes.ANY
)
async def all_updates_handler(message: types.Message) -> None:
    """
    Обрабатывает неизвестные типы сообщений для обученных пользователей.

    Args:
        message (types.Message): Сообщение от пользователя.

    Raises:
        Exception: Любая ошибка при обработке сообщения.
    """
    user_id = message.from_user.id
    user_name = message.from_user.username

    try:
        logger.info(
            f"Пользователь {user_name} (ID: {user_id}) отправил сообщение неизвестного типа: {message.content_type}"
        )

        await message.answer(MESSAGES["all_updates_handler"]["en"])
        logger.info(
            f"Ответ на неизвестный тип сообщения отправлен пользователю {user_name} (ID: {user_id})."
        )
    except ValueError as ve:
        logger.error(
            f"Ошибка определения языка для пользователя {user_id}: {ve}",
            exc_info=True,
        )
        await message.reply(MESSAGES_ERROR["all_updates_handler_error"]["en"])
    except Exception as e:
        logger.error(
            f"Ошибка в обработчике неизвестных сообщений для пользователя {user_id}: {e}",
            exc_info=True,
        )
        await message.reply(MESSAGES_ERROR["all_updates_handler_error"]["en"])


@dp.callback_query_handler(
    lambda c: c.data.startswith("rate_"), mention_bot=True
)
async def process_callback_rating(callback_query: types.CallbackQuery) -> None:
    """
    Обрабатывает колбэк-оценки.

    Args:
        callback_query (types.CallbackQuery): Колбэк-запрос пользователя.

    Raises:
        ValueError: Ошибка разбора данных из колбэка.
        KeyError: Отсутствие языка у пользователя.
        Exception: Любая другая ошибка.
    """
    user_id = callback_query.from_user.id
    user_name = callback_query.from_user.username

    try:

        data = callback_query.data.split("_")
        if len(data) != 3:
            raise ValueError(
                f"Некорректный формат данных колбэка: {callback_query.data}"
            )

        rating = str(data[1])
        response_id = int(data[2])

        logger.info(
            f"Пользователь {user_name} (ID: {user_id}) выбрал оценку: {rating} для ответа {response_id}"
        )

        await bot.send_message(
            user_id, MESSAGES["process_callback_rating"]["en"]
        )

        await bot.edit_message_reply_markup(
            callback_query.message.chat.id,
            callback_query.message.message_id,
            reply_markup=None,
        )

        update_dialog_score(rating, response_id)
        logger.info(
            f"Оценка {rating} сохранена для сообщения с ID {response_id} пользователя {user_name} (ID: {user_id})"
        )

        await bot.answer_callback_query(callback_query.id)

    except ValueError as ve:
        logger.error(
            f"Ошибка разбора данных колбэка для пользователя {user_name} (ID: {user_id}): {ve}"
        )
        await bot.send_message(
            user_id, MESSAGES_ERROR["process_callback_rating_error"]["en"]
        )
    except KeyError as ke:
        logger.error(str(ke))
        await bot.send_message(user_id, MESSAGES["start"])
    except Exception as e:
        logger.error(
            f"Ошибка при обработке колбэка оценки для пользователя {user_name} (ID: {user_id}): {str(e)}"
        )
        await bot.send_message(
            user_id, MESSAGES_ERROR["process_callback_rating_error"]["en"]
        )


@dp.callback_query_handler(
    lambda c: c.data in ["strategy_investment", "improve_portfolio"],
    mention_bot=True,
)
async def process_callback_button(callback_query: types.CallbackQuery) -> None:
    """
    Обрабатывает выбор стратегии через callback-кнопки.

    Args:
        callback_query (types.CallbackQuery): Объект callback-запроса.

    Raises:
        Exception: Любая ошибка при обработке.
    """
    user_id = callback_query.from_user.id

    try:
        if callback_query.data == "strategy_investment":
            await bot.send_message(
                user_id,
                MESSAGES["process_callback_button_strategy_investment"]["en"],
                parse_mode="MarkdownV2",
            )
            logger.info(f"Пользователь {user_id} выбрал стратегию инвестиций.")
        elif callback_query.data == "improve_portfolio":
            await bot.send_message(
                user_id,
                MESSAGES["process_callback_button_improve_portfolio"]["en"],
                parse_mode="MarkdownV2",
            )
            logger.info(f"Пользователь {user_id} выбрал улучшение портфолио.")

        await callback_query.answer()

    except KeyError as ke:
        logger.error(f"Ошибка доступа к сообщениям: {ke}", exc_info=True)
        await bot.send_message(
            user_id, MESSAGES_ERROR["process_callback_button_error"]["en"]
        )
    except Exception as e:
        logger.error(
            f"Ошибка обработки кнопки стратегии для пользователя {user_id}: {str(e)}",
            exc_info=True,
        )
        await bot.send_message(
            user_id, MESSAGES_ERROR["process_callback_button_error"]["en"]
        )


@dp.my_chat_member_handler()
async def handle_chat_member_update(update: types.ChatMemberUpdated) -> None:
    """
    Обрабатывает обновления статуса чатов (удаление, блокировка).

    Args:
        update (types.ChatMemberUpdated): Объект обновления чата.

    Raises:
        Exception: Любая ошибка при обработке.
    """
    user_id = update.from_user.id
    user_name = update.from_user.first_name or "Unknown"

    try:
        if update.new_chat_member.status == "kicked":
            await analytics_creating_target(
                user_id,
                user_name,
                target_start_id=os.getenv("TARGET_START_ID_BLOCK"),
                value=None,
                unit=None,
            )
            logger.info(
                f"Пользователь {user_id} ({user_name}) заблокировал бота."
            )
        elif update.new_chat_member.status == "left":
            await analytics_creating_target(
                user_id,
                user_name,
                target_start_id=os.getenv("TARGET_START_ID_BLOCK"),
                value=None,
                unit=None,
            )
            logger.info(f"Пользователь {user_id} ({user_name}) удалил бота.")
    except Exception as e:
        logger.error(
            f"Ошибка обработки обновлений статуса чата для пользователя {user_id}: {e}",
            exc_info=True,
        )

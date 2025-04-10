import logging
from datetime import datetime

from openai import BadRequestError, RateLimitError
from aiogram.types import ChatActions

from db.dbworker import add_history_entry, get_user_limit, update_user_limit
from src.bot.bot_messages import MESSAGES, MESSAGES_ERROR
from src.bot.promt import PROMTS
from src.generated_answer.rag.rag_response import run_gpt
from src.generated_answer.agent.agent_response import run_agent
from src.generated_answer.image.image_processing import image_processing
from src.generated_answer.text_formatting import convert_markdown_to_markdownv2
from src.keyboards.drating_inline_buttons_keyboard import (
    drating_inline_buttons_keyboard,
)
from src.generated_answer.agent.agent_thematic import is_crypto_related, context_completion

logger = logging.getLogger(__name__)

async def smart_split_text(text, max_length=4000):
    """
    Разбивает текст по абзацам, сохраняя форматирование MarkdownV2.
    Никогда не разрывает Markdown-выделения и формулы.
    """
    paragraphs = text.split("\n")
    messages = []
    current_message = ""

    for paragraph in paragraphs:
        if len(current_message) + len(paragraph) + 1 <= max_length:
            current_message += paragraph + "\n"
        else:
            if current_message:
                messages.append(current_message.strip())
            current_message = paragraph + "\n"

    if current_message:
        messages.append(current_message.strip())

    return messages


async def process_user_message(
    user_id: int,
    chat_id: str,
    text: str,
    history: list,
    prompt: str,
    bot,
    message=None,
    data_from_question=None,
    file_url=None,
) -> None:
    """
    Обрабатывает сообщение пользователя, отправляет его модели и возвращает ответ.

    Args:
        user_id (int): Идентификатор пользователя.
        chat_id (int): Идентификатор чата.
        text (str): Текст сообщения.
        history (list): История диалога.
        prompt (str): Тип запроса.
        bot: Telegram-бот.
        message: Объект сообщения Telegram.
        data_from_question: Дополнительные данные для обработки запроса.
        file_url
    Raises:
        ValueError: Если ответ модели пустой.
        BadRequestError: Если запрос к модели превышает лимит токенов.
        RateLimitError: Если превышено ограничение на количество запросов.
        Exception: Для всех остальных непредвиденных ошибок.
    """
    try:
        await bot.send_chat_action(
            chat_id=message.chat.id, action=ChatActions.TYPING
        )
        await bot.send_chat_action(chat_id=chat_id, action="typing")
        first_message = await bot.send_message(
            chat_id=chat_id, text=MESSAGES["process_user_message"]["en"]
        )
        await bot.send_chat_action(
            chat_id=message.chat.id, action=ChatActions.TYPING
        )

        prompt_and_data = PROMTS[prompt]["en"] + f"{datetime.now()}"
        if prompt == "image":
            response = await image_processing(
                message, text, bot, user_id, file_url, prompt=prompt_and_data
            )
        elif prompt in ("you_tube_link", "link", "document"):
            response = await run_gpt(
                user_id,
                bot,
                prompt_text=prompt_and_data,
                user_input=text,
                history=history,
            )
            question, name_document_link = data_from_question
            text = f'User request: {question}. The user provided a link: "{name_document_link}"'
        else:
            context_question = await context_completion(text, user_id)
            thematic_check = await is_crypto_related(context_question, user_id)
            if thematic_check:
                response_gent = await run_agent(
                    user_id, context_question, history, prompt_text=prompt_and_data
                )
                response = response_gent
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="I only respond to questions related to cryptocurrencies, blockchain, finance, and development in these areas. If you have specific questions on any of these topics, please feel free to ask!"
                )
                return

        if not response:
            raise ValueError("Пустой ответ от модели")

        assistant_response_id = add_history_entry(user_id, text, response)
        if chat_id == user_id:
            rating_keyboard = drating_inline_buttons_keyboard(
                assistant_response_id
            )
            rating_message = MESSAGES["rating_request"].get("en")
        else:
            rating_keyboard = None
            rating_message = ""

        response_with_rating = response + "\n" + rating_message
        logger.info(f"Текс не переведенный в markdownv2{response_with_rating}")
        formatted_text = convert_markdown_to_markdownv2(response_with_rating)
        logger.info(f"Текс переведенный в markdownv2{formatted_text}")
        for part in await smart_split_text(formatted_text):
            await bot.send_message(
                chat_id=chat_id,
                text=part,
                reply_markup=rating_keyboard,
                parse_mode="MarkdownV2"
            )

    except ValueError as ve:
        logger.error(f"Ошибка: {ve}")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=first_message.message_id,
            text=MESSAGES_ERROR["error_response"]["en"],
        )
    except BadRequestError as e:
        logger.error(
            f"Ошибка при работе агента для пользователя {user_id}: {e}"
        )
        await bot.send_message(
            chat_id=chat_id, text=MESSAGES_ERROR["limit_token"]["en"]
        )
    except RateLimitError as e:
        logger.error(f"Ошибка большого количества запросов за раз: {e}")
        await bot.send_message(
            chat_id=chat_id, text=MESSAGES_ERROR["many_requests"]["en"]
        )
    except Exception as e:
        logger.error(f"Произошла ошибка обработки сообщения: {e}")
        await bot.send_message(
            chat_id=chat_id, text=MESSAGES_ERROR["error_response"]["en"]
        )
    finally:
        await bot.delete_message(
            chat_id=chat_id, message_id=first_message.message_id
        )

import logging
import re
from datetime import datetime

from dotenv import load_dotenv
from openai import BadRequestError, RateLimitError
from aiogram.types import ChatActions

from db.dbworker import add_history_entry, get_user_limit, update_user_limit
from src.bot.bot_messages import MESSAGES, MESSAGES_ERROR
from src.bot.promt import PROMTS
from src.gpt_generated_answer.gpt_response import run_agent, run_gpt
from src.gpt_generated_answer.image_processing import image_processing
from src.keyboards.drating_inline_buttons_keyboard import (
    drating_inline_buttons_keyboard,
)


load_dotenv()
logger = logging.getLogger(__name__)


def latex_to_unicode(text: str) -> str:
    """
    Преобразует LaTeX выражения в Unicode.

    Args:
        text (str): Текст, содержащий LaTeX выражения.

    Returns:
        str: Текст, преобразованный в Unicode.

    Raises:
        Exception: Логирует ошибку, если что-то пошло не так при преобразовании.
    """
    try:
        text = re.sub(
            r"\\\[(.*?)\\\]",
            lambda m: m.group(1).strip(),
            text,
            flags=re.DOTALL,
        )
        text = re.sub(
            r"\\\((.*?)\\\)",
            lambda m: m.group(1).strip(),
            text,
            flags=re.DOTALL,
        )
        text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
        text = re.sub(
            r"\\frac\{([^}]*)\}\{([^}]*)\}",
            lambda m: f"({m.group(1)})/({m.group(2)})",
            text,
        )

        greek_map = {
            r"\alpha": "α",
            r"\beta": "β",
            r"\gamma": "γ",
            r"\delta": "δ",
            r"\epsilon": "ε",
            r"\zeta": "ζ",
            r"\eta": "η",
            r"\theta": "θ",
            r"\iota": "ι",
            r"\kappa": "κ",
            r"\lambda": "λ",
            r"\mu": "μ",
            r"\nu": "ν",
            r"\xi": "ξ",
            r"\omicron": "ο",
            r"\pi": "π",
            r"\rho": "ρ",
            r"\sigma": "σ",
            r"\tau": "τ",
            r"\upsilon": "υ",
            r"\phi": "φ",
            r"\chi": "χ",
            r"\psi": "ψ",
            r"\omega": "ω",
            r"\Gamma": "Γ",
            r"\Delta": "Δ",
            r"\Theta": "Θ",
            r"\Lambda": "Λ",
            r"\Xi": "Ξ",
            r"\Pi": "Π",
            r"\Sigma": "Σ",
            r"\Upsilon": "Υ",
            r"\Phi": "Φ",
            r"\Psi": "Ψ",
            r"\Omega": "Ω",
        }
        for latex_cmd, uni_char in greek_map.items():
            text = text.replace(latex_cmd, uni_char)

        math_symbols = {
            r"\times": "×",
            r"\cdot": "⋅",
            r"\approx": "≈",
            r"\leq": "≤",
            r"\geq": "≥",
            r"\neq": "≠",
            r"\pm": "±",
            r"\mp": "∓",
            r"\to": "→",
            r"\leftarrow": "←",
            r"\Rightarrow": "⇒",
            r"\Leftarrow": "⇐",
            r"\leftrightarrow": "↔",
            r"\infty": "∞",
            r"\partial": "∂",
            r"\aleph": "ℵ",
            r"\hbar": "ℏ",
            r"\%": "%",
        }
        for latex_cmd, uni_char in math_symbols.items():
            text = text.replace(latex_cmd, uni_char)

        math_functions = {
            r"\sqrt": "√",
            r"\sum": "∑",
            r"\int": "∫",
            r"\prod": "∏",
            r"\lim": "lim",
            r"\ln": "ln",
            r"\sin": "sin",
            r"\cos": "cos",
            r"\tan": "tan",
            r"\log": "log",
            r"\exp": "exp",
        }
        for func, uni_char in math_functions.items():
            if func == r"\sqrt":
                text = re.sub(
                    r"\\sqrt\{([^}]*)\}", lambda m: "√" + m.group(1), text
                )
            else:
                text = text.replace(func, uni_char)

        superscript_map = {
            "0": "⁰",
            "1": "¹",
            "2": "²",
            "3": "³",
            "4": "⁴",
            "5": "⁵",
            "6": "⁶",
            "7": "⁷",
            "8": "⁸",
            "9": "⁹",
            "+": "⁺",
            "-": "⁻",
            "=": "⁼",
            "(": "⁽",
            ")": "⁾",
            "n": "ⁿ",
            "i": "ⁱ",
            "t": "ᵗ",
            "m": "ᵐ",
            "r": "ʳ",
            "s": "ˢ",
            "u": "ᵘ",
            "v": "ᵛ",
            "j": "ʲ",
            "d": "ᵈ",
            "g": "ᵍ",
            "a": "ᵃ",
            "b": "ᵇ",
            "c": "ᶜ",
            "f": "ᶠ",
            "k": "ᵏ",
            "l": "ˡ",
            "o": "ᵒ",
            "p": "ᵖ",
            "q": "ᑫ",
            "w": "ʷ",
            "x": "ˣ",
            "y": "ʸ",
            "z": "ᶻ",
        }

        def replace_superscript(match: re.Match) -> str:
            content = match.group(1)
            return "".join(superscript_map.get(ch, ch) for ch in content)

        text = re.sub(r"\^\{([^}]*)\}", replace_superscript, text)

        text = re.sub(
            r"\^(\w)",
            lambda m: superscript_map.get(m.group(1), m.group(1)),
            text,
        )

        subscript_map = {
            "0": "₀",
            "1": "₁",
            "2": "₂",
            "3": "₃",
            "4": "₄",
            "5": "₅",
            "6": "₆",
            "7": "₇",
            "8": "₈",
            "9": "₉",
            "+": "₊",
            "-": "₋",
            "=": "₌",
            "(": "₍",
            ")": "₎",
            "a": "ₐ",
            "e": "ₑ",
            "o": "ₒ",
            "x": "ₓ",
            "h": "ₕ",
            "k": "ₖ",
            "l": "ₗ",
            "m": "ₘ",
            "n": "ₙ",
            "p": "ₚ",
            "s": "ₛ",
            "t": "ₜ",
            "u": "ᵤ",
            "v": "ᵥ",
            "i": "ᵢ",
            "r": "ᵣ",
            "d": "ᵈ",
            "g": "ᵍ",
            "j": "ʲ",
            "c": "ₓ",
            "f": "ₓ",
            "b": "ₓ",
        }

        def replace_subscript(match: re.Match) -> str:
            content = match.group(1)
            return "".join(subscript_map.get(ch, ch) for ch in content)

        text = re.sub(r"\\?_\{([^}]*)\}", replace_subscript, text)

        text = re.sub(
            r"\\?_(\w)",
            lambda m: subscript_map.get(m.group(1), m.group(1)),
            text,
        )

    except Exception as e:
        logger.error(f"Ошибка преобразования LaTeX в Unicode: {str(e)}")

    return text


def convert_markdown_to_markdownv2(text: str) -> str:
    """
    Преобразует текст Markdown в формат MarkdownV2 для Telegram,
    обрабатывая блоки кода, специальные символы и LaTeX-выражения.

    Args:
        text (str): Текст в формате Markdown.

    Returns:
        str: Текст, преобразованный в формат MarkdownV2.
    """
    try:
        special_chars = r"\[\]()~`>#+\-=|{}.!"

        username_pattern = re.compile(r"(@[A-Za-z0-9_]{5,32})")

        usernames = {}

        def save_username(match):
            """Сохраняет юзернеймы временно, чтобы не экранировать _ дважды."""
            username = match.group(0)
            placeholder = f"%%USERNAME{len(usernames)}%%"
            usernames[placeholder] = username.replace("_", r"\_")
            return placeholder

        text = username_pattern.sub(save_username, text)

        def escape_special_chars(part: str) -> str:
            """Экранирует спецсимволы MarkdownV2, но не трогает _ внутри юзернеймов."""
            part = re.sub(
                r"([{}])".format(re.escape(special_chars)), r"\\\1", part
            )
            return part

        def process_text_part(part: str) -> str:
            """Обрабатывает обычный текст, не затрагивая кодовые блоки."""
            part = re.sub(r"(?<!\\)_", r"\_", part)
            part = re.sub(r"(?<!\*)\*(?!\*)", r"\*", part)
            part = re.sub(r"\*\*(.*?)\*\*", r"*\1*", part)
            part = re.sub(r"### (.*?)\n", r"__\1__\n", part)
            return escape_special_chars(part)

        code_block_pattern = re.compile(r"(```.*?```)", re.DOTALL)
        parts = code_block_pattern.split(text)

        processed_parts = [
            part if part.startswith("```") else process_text_part(part)
            for part in parts
        ]

        result = "".join(processed_parts)

        for placeholder, username in usernames.items():
            result = result.replace(placeholder, username)

        return result

    except Exception as e:
        logger.error(f"Ошибка перевода в MarkdownV2: {str(e)}")
        return text


def clean_agent_response(response: str) -> str:
    """
    Очищает ответ агента от ненужных завершающих символов ``` и многоточий.

    Args:
        response (str): Ответ агента.

    Returns:
        str: Очищенный ответ.
    """
    response = response.strip()

    if response.startswith("```") and response.endswith("```"):
        return response

    if response.endswith("```"):
        response = response.rstrip("`").strip()

    response = re.sub(r"\.{2,}$", "", response)

    return response


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
            text = f'Запрос пользователя: {question}. Пользователь предоставил ссылку: "{name_document_link}"'
        else:
            response_gent = await run_agent(
                user_id, text, history, prompt_text=prompt_and_data
            )
            response = clean_agent_response(response_gent)

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

        formatted_text = convert_markdown_to_markdownv2(response_with_rating)
        logger.info(formatted_text)
        await bot.send_message(
            chat_id=chat_id,
            text=formatted_text,
            reply_markup=rating_keyboard,
            parse_mode="MarkdownV2",
            reply_to_message_id=message.message_id,
        )

        await bot.delete_message(
            chat_id=chat_id, message_id=first_message.message_id
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

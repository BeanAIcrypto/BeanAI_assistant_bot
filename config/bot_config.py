import logging
import os
import sys

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from aiogram.bot.api import TelegramAPIServer

from config.filters import setup_filters
from src.utils.cli import parse_arguments


logger = logging.getLogger(__name__)
load_dotenv()
args = parse_arguments()


def setup_bot() -> None:
    """
    Инициализирует обработчики бота, чтобы избежать циклических зависимостей.
    """
    from src.bot import handlers


def check_env_variables() -> None:
    """
    Проверяет наличие обязательных переменных окружения и завершает работу, если они отсутствуют.

    Raises:
        SystemExit: Если отсутствуют обязательные переменные окружения.
    """
    required_vars = [
        "GPT_SECRET_KEY_FASOLKAAI",
        "MODEL_NAME",
        "MODEL_NAME_MEM",
        "TG_TOKEN",
        "CHANNEL_ID",
        "CHANNEL_LINK",
        "SERVICE_ACCOUNT_FILE",
        "SPREADSHEET_ID",
        "GRASPIL_API_KEY",
        "GOOGLE_API_KEY",
        "SEARCH_ENGINE_GLOBAL_ID",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(
            f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}. Завершение работы."
        )
        sys.exit(1)


try:
    if not args.init:
        check_env_variables()
        TG_TOKEN = os.getenv("TG_TOKEN")
        if not TG_TOKEN:
            logger.error("Отсутствует токен Telegram. Завершение работы.")
            sys.exit(1)

        server = TelegramAPIServer.from_base("https://tgrasp.co")
        bot = Bot(token=TG_TOKEN, server=server)
        dp = Dispatcher(bot, run_tasks_by_default=True)

        setup_filters(dp)
    else:
        logger.info(
            "Флаг init выбран, выполнение программы не требуется. Завершение работы."
        )
        sys.exit(0)
    setup_bot()
except KeyError as error:
    logger.error(f"Ошибка доступа к ключу окружения: {error}", exc_info=True)
    sys.exit(1)
except ValueError as error:
    logger.error(f"Ошибка значения: {error}", exc_info=True)
    sys.exit(1)
except Exception as error:
    logger.error(
        f"Неизвестная ошибка при запуске бота: {error}", exc_info=True
    )
    sys.exit(1)

from logs import logging_setup

import logging
from aiogram import executor

from config.bot_config import setup_bot, dp
from db.dbworker import create_db
from db.google_sheets import google_sheets
from src.bot.handlers import on_startup


logger = logging.getLogger(__name__)

if __name__ == '__main__':
    """
    Основной модуль для запуска Telegram-бота.

    Выполняет следующие задачи:
    1. Синхронизация с Google Sheets.
    2. Создание базы данных.
    3. Создание пользовательских хэшей.
    4. Настройка и запуск бота.

    Исключения обрабатываются с логированием ошибок.
    """
    try:
        google_sheets()
        logger.info('Google Sheets синхронизация запущена')

        create_db()
        logger.info('База данных создана')

        setup_bot()
        logger.info('Бот настроен и готов к работе')

        logger.info('Бот запущен и ожидает сообщения')
        executor.start_polling(dp, on_startup=on_startup)

    except ConnectionError as error:
        logger.error(f'Ошибка подключения к внешнему сервису: {str(error)}', exc_info=True)
    except FileNotFoundError as error:
        logger.error(f'Не найден файл конфигурации или зависимостей: {str(error)}', exc_info=True)
    except Exception as error:
        logger.error(f'Неизвестная ошибка при запуске бота: {str(error)}', exc_info=True)


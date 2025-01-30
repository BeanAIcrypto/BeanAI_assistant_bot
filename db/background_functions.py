import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiogram import Bot
from psycopg2 import OperationalError as DatabaseError

from db.database_connection import get_db_connection
from src.bot.bot_messages import MESSAGES
from src.keyboards.check_subscriptions_keyboard import check_subscriptions_keyboard
from src.keyboards.reminder_keyboard import get_reminder_keyboard


logger = logging.getLogger(__name__)


async def send_reminder_work(bot: Bot) -> None:
    """
    Отправляет напоминания пользователям об активности.

    Args:
        bot (Bot): Экземпляр бота.

    Raises:
        DatabaseError: Ошибка при взаимодействии с базой данных.
        ValueError: Ошибка в данных, например, неверно определена дата последнего взаимодействия.
        Exception: Общая ошибка при выполнении задачи.
    """
    try:
        logger.info("Начало отправки напоминаний для пользователей.")

        with get_db_connection() as connection:
            cursor = connection.cursor()

            for hours, column_name in [(24, 'reminder_24_sent'), (72, 'reminder_72_sent'), (168, 'reminder_168_sent')]:
                time_threshold = datetime.now() - timedelta(hours=hours)

                query = f"""
                    SELECT 
                        users.id, 
                        users.user_id, 
                        users.language, 
                        reminder.{column_name},
                        COALESCE(
                            (
                                SELECT MAX(user_history.created_at) 
                                FROM user_history 
                                WHERE user_history.user_id = users.user_id
                            ), 
                            users.created_at
                        ) AS last_interaction
                    FROM 
                        users
                    LEFT JOIN 
                        reminder 
                    ON 
                        users.user_id = reminder.user_id
                    WHERE 
                        COALESCE(
                            (
                                SELECT MAX(user_history.created_at) 
                                FROM user_history 
                                WHERE user_history.user_id = users.user_id
                            ), 
                            users.created_at
                        ) < %s
                        AND 
                        (reminder.{column_name} = 0 OR reminder.{column_name} IS NULL)
                    GROUP BY 
                        users.id, 
                        users.user_id, 
                        users.language, 
                        reminder.{column_name}, 
                        last_interaction;
                """

                cursor.execute(query, (time_threshold,))
                rows = cursor.fetchall()

                logger.info(f"Найдено {len(rows)} пользователей для отправки напоминаний на {hours} часов.")

                for table_id, user_id, language, _, last_interaction in rows:
                    message_key = f'send_reminder_{hours}h'
                    message_text = MESSAGES[message_key][language]

                    try:
                        if hours == 72:
                            reminder_keyboard = get_reminder_keyboard(language)
                            await bot.send_message(user_id, message_text, reply_markup=reminder_keyboard)
                        else:
                            await bot.send_message(user_id, message_text)

                        logger.info(f"Напоминание отправлено пользователю {user_id}: {message_text}")
                    except Exception as e:
                        logger.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
                        continue

                    cursor.execute(f'UPDATE reminder SET {column_name} = 1 WHERE user_id = %s', (user_id,))
                    connection.commit()
                    logger.info(f"Флаг {column_name} обновлен для пользователя {user_id}.")

    except DatabaseError as e:
        logger.error(f"Ошибка при взаимодействии с базой данных: {e}")
        raise
    except ValueError as e:
        logger.error(f"Некорректные данные при обработке напоминания: {e}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания: {e}")
        raise


async def send_subscription_reminder(bot: Bot) -> None:
    """
    Отправляет напоминания о подписке.

    Args:
        bot (Bot): Экземпляр бота.

    Raises:
        DatabaseError: Ошибка при взаимодействии с базой данных.
        ConnectionError: Ошибка соединения при отправке сообщений пользователю.
        ValueError: Некорректные данные.
        Exception: Общая ошибка при выполнении задачи.
    """
    try:
        logger.info("Начало отправки напоминаний о подписке.")

        time_24_hours_ago = datetime.now() - timedelta(hours=24)
        time_168_hours_ago = datetime.now() - timedelta(hours=168)

        with get_db_connection() as connection:
            cursor = connection.cursor()

            query = '''
                SELECT u.user_id,
                       u.language,
                       t.reminder_24_sent_subscription,
                       t.reminder_168_sent_subscription,
                       (SELECT MAX(created_at) 
                        FROM user_history 
                        WHERE user_history.user_id = u.user_id) AS last_interaction
                FROM users u
                JOIN reminder t ON u.user_id = t.user_id
                WHERE (t.reminder_24_sent_subscription = 0 OR t.reminder_168_sent_subscription = 0);
            '''
            cursor.execute(query)
            rows = cursor.fetchall()

            logger.info(f"Найдено {len(rows)} пользователей для отправки напоминаний о подписке.")

            for user_id, language, reminder_24_sent, reminder_168_sent, last_interaction in rows:
                if last_interaction is None:
                    logger.info(f"Пропуск пользователя {user_id}, так как нет взаимодействий.")
                    continue

                if last_interaction > datetime.now() - timedelta(minutes=30):
                    continue

                if not reminder_24_sent and last_interaction < time_24_hours_ago:
                    await bot.send_message(
                        user_id,
                        MESSAGES['send_subscription_reminder_24'][language] + os.getenv('CHANNEL_LINK'),
                        reply_markup=check_subscriptions_keyboard(language),
                    )
                    cursor.execute('UPDATE reminder SET reminder_24_sent_subscription = 1 WHERE user_id = %s', (user_id,))
                    connection.commit()

                if not reminder_168_sent and last_interaction < time_168_hours_ago:
                    await bot.send_message(
                        user_id,
                        MESSAGES['send_subscription_reminder_168'][language] + os.getenv('CHANNEL_LINK'),
                        reply_markup=check_subscriptions_keyboard(language),
                    )
                    cursor.execute('UPDATE reminder SET reminder_168_sent_subscription = 1 WHERE user_id = %s', (user_id,))
                    connection.commit()

    except DatabaseError as e:
        logger.error(f"Ошибка базы данных: {e}")
        raise
    except ConnectionError as e:
        logger.error(f"Ошибка соединения: {e}")
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки напоминаний: {e}")
        raise


async def start_background_tasks(bot: Bot) -> None:
    """
    Запускает фоновую задачу для отправки напоминаний каждые 24 часа.

    Args:
        bot (Bot): Экземпляр бота.

    Raises:
        asyncio.TimeoutError: Ошибка тайм-аута при ожидании выполнения задачи.
        ConnectionError: Ошибка при подключении к внешним сервисам (например, при отправке напоминаний).
        ValueError: Некорректные данные или ошибки логики при обработке задач.
        Exception: Общая ошибка при обработке фоновой задачи.
    """
    try:
        logger.info("Запуск фоновой задачи для отправки напоминаний.")
        while True:
            await send_reminder_work(bot)
            await send_subscription_reminder(bot)
            logger.info("Фоновые задачи выполнены, ожидаем следующий запуск.")
            await asyncio.sleep(86400)
    except asyncio.TimeoutError as e:
        logger.error(f"Ошибка тайм-аута при обработке фоновой задачи: {str(e)}")
        raise asyncio.TimeoutError(f"Ошибка тайм-аута: {str(e)}")
    except ConnectionError as e:
        logger.error(f"Ошибка подключения при обработке фоновой задачи: {str(e)}")
        raise ConnectionError(f"Ошибка подключения: {str(e)}")
    except ValueError as e:
        logger.error(f"Ошибка в логике фоновой задачи: {str(e)}")
        raise ValueError(f"Ошибка данных или логики: {str(e)}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при обработке фоновой задачи: {str(e)}")
        raise Exception(f"Неизвестная ошибка: {str(e)}")

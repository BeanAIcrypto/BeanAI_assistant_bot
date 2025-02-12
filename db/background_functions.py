import asyncio
import logging
import os
from datetime import datetime, timedelta
from aiogram import Bot
from psycopg2 import OperationalError as DatabaseError

from db.database_connection import get_db_connection
from src.bot.bot_messages import MESSAGES
from src.keyboards.check_subscriptions_keyboard import (
    check_subscriptions_keyboard,
)
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

            for hours, column_name in [
                (24, "reminder_24_sent"),
                (72, "reminder_72_sent"),
                (168, "reminder_168_sent"),
            ]:
                time_threshold = datetime.now() - timedelta(hours=hours)

                query = f"""
                    SELECT 
                        users.id, 
                        users.user_id, 
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
                        reminder.{column_name}, 
                        last_interaction;
                """

                cursor.execute(query, (time_threshold,))
                rows = cursor.fetchall()

                logger.info(
                    f"Найдено {len(rows)} пользователей для отправки напоминаний на {hours} часов."
                )

                for table_id, user_id, _, last_interaction in rows:
                    message_key = f"send_reminder_{hours}h"
                    message_text = MESSAGES[message_key]["en"]

                    try:
                        if hours == 72:
                            reminder_keyboard = get_reminder_keyboard("en")
                            await bot.send_message(
                                user_id,
                                message_text,
                                reply_markup=reminder_keyboard,
                            )
                        else:
                            await bot.send_message(user_id, message_text)

                        logger.info(
                            f"Напоминание отправлено пользователю {user_id}: {message_text}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Ошибка при отправке сообщения пользователю {user_id}: {e}"
                        )
                        continue

                    cursor.execute(
                        f"UPDATE reminder SET {column_name} = 1 WHERE user_id = %s",
                        (user_id,),
                    )
                    connection.commit()
                    logger.info(
                        f"Флаг {column_name} обновлен для пользователя {user_id}."
                    )

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

            query = """
                SELECT u.user_id,
                       t.reminder_24_sent_subscription,
                       t.reminder_168_sent_subscription,
                       (SELECT MAX(created_at) 
                        FROM user_history 
                        WHERE user_history.user_id = u.user_id) AS last_interaction
                FROM users u
                JOIN reminder t ON u.user_id = t.user_id
                WHERE (t.reminder_24_sent_subscription = 0 OR t.reminder_168_sent_subscription = 0);
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            logger.info(
                f"Найдено {len(rows)} пользователей для отправки напоминаний о подписке."
            )

            for (
                user_id,
                reminder_24_sent,
                reminder_168_sent,
                last_interaction,
            ) in rows:
                if last_interaction is None:
                    logger.info(
                        f"Пропуск пользователя {user_id}, так как нет взаимодействий."
                    )
                    continue

                if last_interaction > datetime.now() - timedelta(minutes=30):
                    continue

                if (
                    not reminder_24_sent
                    and last_interaction < time_24_hours_ago
                ):
                    await bot.send_message(
                        user_id,
                        MESSAGES["send_subscription_reminder_24"]["en"]
                        + os.getenv("CHANNEL_LINK"),
                        reply_markup=check_subscriptions_keyboard("en"),
                    )
                    cursor.execute(
                        "UPDATE reminder SET reminder_24_sent_subscription = 1 WHERE user_id = %s",
                        (user_id,),
                    )
                    connection.commit()
                    continue

                if (
                    not reminder_168_sent
                    and last_interaction < time_168_hours_ago
                ):
                    await bot.send_message(
                        user_id,
                        MESSAGES["send_subscription_reminder_168"]["en"]
                        + os.getenv("CHANNEL_LINK"),
                        reply_markup=check_subscriptions_keyboard("en"),
                    )
                    cursor.execute(
                        "UPDATE reminder SET reminder_168_sent_subscription = 1 WHERE user_id = %s",
                        (user_id,),
                    )
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
    Запускает фоновую задачу для отправки напоминаний с разными интервалами.

    - send_reminder_work() каждые 29 минут.
    - send_subscription_reminder() каждые 12 часов.
    """

    async def periodic_task(func, interval):
        """Запускает переданную функцию с указанным интервалом в секундах."""
        while True:
            try:
                await func(bot)
                logger.info(
                    f"Фоновая задача {func.__name__} выполнена, следующий запуск через {interval / 60:.1f} мин."
                )
            except asyncio.TimeoutError as e:
                logger.error(f"Ошибка тайм-аута в {func.__name__}: {str(e)}")
            except ConnectionError as e:
                logger.error(f"Ошибка подключения в {func.__name__}: {str(e)}")
            except ValueError as e:
                logger.error(f"Ошибка логики в {func.__name__}: {str(e)}")
            except Exception as e:
                logger.error(f"Неизвестная ошибка в {func.__name__}: {str(e)}")

            await asyncio.sleep(interval)

    asyncio.create_task(periodic_task(send_reminder_work, 29 * 60))
    asyncio.create_task(
        periodic_task(send_subscription_reminder, 12 * 60 * 60)
    )
    logger.info("Фоновые задачи запущены.")

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import logging
from dotenv import load_dotenv
import os
import csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}

EXPORT_DIR = "export_data"
INITIAL_LIMIT = 6666667

if not os.path.exists(EXPORT_DIR):
    os.makedirs(EXPORT_DIR)


def get_db_connection():
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as error:
        logger.error(f"Ошибка подключения к PostgreSQL: {error}")
        raise


def import_users_and_associated_tables():
    try:
        users_file = os.path.join(EXPORT_DIR, "users.csv")
        if not os.path.exists(users_file):
            logger.warning(f"Файл {users_file} не найден. Пропускаем импорт.")
            return

        with open(users_file, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            users = []
            user_limits = []
            reminders = []

            for row in reader:
                user_id = row.get("user_id")
                users.append(
                    [
                        user_id,
                        row.get("username", "unknown"),
                        row.get("created_at"),
                        row.get("subscription_reminder_sent", 0),
                    ]
                )

                user_limits.append([user_id])
                reminders.append([user_id])

        with get_db_connection() as conn:
            cursor = conn.cursor()

            users_query = """
            INSERT INTO users (user_id, username, created_at, subscription_reminder_sent)
            VALUES %s
            ON CONFLICT (user_id) DO NOTHING
            """
            execute_values(cursor, users_query, users)

            user_limit_query = """
            INSERT INTO user_limit (user_id)
            VALUES %s
            ON CONFLICT (user_id) DO NOTHING
            """
            execute_values(cursor, user_limit_query, user_limits)

            reminders_query = """
            INSERT INTO reminder (user_id)
            VALUES %s
            ON CONFLICT (user_id) DO NOTHING
            """
            execute_values(cursor, reminders_query, reminders)

            conn.commit()
            logger.info(
                "Пользователи и связанные таблицы успешно импортированы."
            )
    except Exception as error:
        logger.error(
            f"Ошибка при импорте пользователей и связанных таблиц: {error}"
        )
        raise


def import_user_history():
    try:
        history_file = os.path.join(EXPORT_DIR, "user_history.csv")
        if not os.path.exists(history_file):
            logger.warning(
                f"Файл {history_file} не найден. Пропускаем импорт."
            )
            return

        # Увеличение лимита размера поля
        csv.field_size_limit(10**6)

        with open(history_file, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            history = [
                [
                    row.get("user_id"),
                    row.get("question"),
                    row.get("response"),
                    row.get("dialog_score"),
                    row.get("created_at"),
                ]
                for row in reader
            ]

        with get_db_connection() as conn:
            cursor = conn.cursor()
            history_query = """
            INSERT INTO user_history (user_id, question, response, dialog_score, created_at)
            VALUES %s
            ON CONFLICT DO NOTHING
            """
            execute_values(cursor, history_query, history)
            conn.commit()
            logger.info("История пользователей успешно импортирована.")
    except Exception as error:
        logger.error(f"Ошибка при импорте истории пользователей: {error}")
        raise


if __name__ == "__main__":
    import_users_and_associated_tables()
    import_user_history()

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import psycopg2
from dotenv import load_dotenv
import redis

from db.google_sheets import append_row_to_google_sheet, update_google_sheet_row
from db.database_connection import get_db_connection

logger = logging.getLogger(__name__)

load_dotenv()

INITIAL_LIMIT: int = 6666667
r = redis.Redis(host=os.getenv("REDIS_HOST"), port=os.getenv("REDIS_PORT"), db=1)


def create_db() -> None:
    """
    Создает необходимые таблицы в базе данных PostgreSQL.

    Raises:
        psycopg2.ProgrammingError: Ошибка SQL синтаксиса.
        psycopg2.DatabaseError: Ошибка базы данных.
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            cursor.execute('''
                 CREATE TABLE IF NOT EXISTS users (
                     id SERIAL PRIMARY KEY,
                     user_id BIGINT UNIQUE,
                     username TEXT,
                     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                     subscription_reminder_sent INTEGER DEFAULT 0,
                     status_you_tube INTEGER DEFAULT 0
                 )
             ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_history (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    question TEXT,
                    response TEXT,
                    dialog_score TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')

            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS user_limit (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT UNIQUE,
                    user_limit REAL DEFAULT {INITIAL_LIMIT},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminder (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT UNIQUE,
                    reminder_24_sent INTEGER DEFAULT 0,
                    reminder_72_sent INTEGER DEFAULT 0,
                    reminder_168_sent INTEGER DEFAULT 0,
                    reminder_24_sent_subscription INTEGER DEFAULT 0,
                    reminder_168_sent_subscription INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')

            connection.commit()
            logger.info("Таблицы успешно созданы в базе данных.")
    except psycopg2.ProgrammingError as error:
        logger.error(f"Ошибка SQL синтаксиса при создании таблиц: {error}")
        raise
    except psycopg2.DatabaseError as error:
        logger.error(f"Ошибка базы данных при создании таблиц: {error}")
        raise
    except Exception as error:
        logger.error(f"Неизвестная ошибка при создании таблиц: {error}")
        raise


def create_user(user_id: int, username: str) -> None:
    """
    Добавляет нового пользователя в базу данных или обновляет информацию, если пользователь уже существует.

    Args:
        user_id (int): Уникальный идентификатор пользователя.
        username (str): Имя пользователя.

    Raises:
        psycopg2.IntegrityError: Ошибка целостности данных.
        psycopg2.DatabaseError: Ошибка базы данных.
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
            user = cursor.fetchone()

            if user is None:
                cursor.execute('INSERT INTO users (user_id, username) VALUES (%s, %s)', (user_id, username))
                cursor.execute('INSERT INTO reminder (user_id) VALUES (%s)', (user_id,))
                cursor.execute('INSERT INTO user_limit (user_id) VALUES (%s)', (user_id,))
                connection.commit()
                logger.info(f"Пользователь {user_id} добавлен в базу данных.")
            else:
                logger.info(f"Пользователь {user_id} уже существует в базе данных.")
    except psycopg2.IntegrityError as error:
        logger.error(f"Ошибка целостности данных при добавлении пользователя {user_id}: {error}")
    except psycopg2.DatabaseError as error:
        logger.error(f"Ошибка базы данных при добавлении пользователя {user_id}: {error}")
    except Exception as error:
        logger.error(f"Неизвестная ошибка при добавлении пользователя {user_id}: {error}")


def add_history_entry(user_id: int, question: str, response: str) -> Optional[int]:
    """
    Добавляет новую запись в историю пользователя.

    Args:
        user_id (int): Уникальный идентификатор пользователя.
        question (str): Вопрос пользователя.
        response (str): Ответ на вопрос.

    Returns:
        Optional[int]: Идентификатор записи в истории или None при ошибке.

    Raises:
        psycopg2.DatabaseError: Ошибка базы данных.
    """
    try:
        with get_db_connection() as connection:
            question = re.sub(r'[\x00-\x1F\x7F-\x9F]+', '', question)
            response = re.sub(r'[\x00-\x1F\x7F-\x9F]+', '', response)

            cursor = connection.cursor()
            cursor.execute(
                """INSERT INTO user_history (user_id, question, response) 
                VALUES (%s, %s, %s)
                RETURNING id;""",
                (user_id, question, response)
            )
            connection.commit()
            history_id = cursor.fetchone()[0]
            logger.info(f"Запись в историю для пользователя {user_id} успешно добавлена.")

            row_data = [history_id, question, response]
            append_row_to_google_sheet(row_data, 'history')

            return history_id
    except psycopg2.DatabaseError as error:
        logger.error(f"Ошибка базы данных при добавлении записи в историю для пользователя {user_id}: {error}")
        return None
    except Exception as error:
        logger.error(f"Неизвестная ошибка при добавлении записи в историю для пользователя {user_id}: {error}")
        return None


def get_user_status_you_tube(user_id: int) -> Optional[int]:
    """
        Получает статус обработке YouTube ссылки.

        Args:
            user_id (int): Уникальный идентификатор пользователя.

        Returns:
            Optional[int]: Статус 0, если видео не отправлено и 1, если видео в обработке.

        Raises:
            psycopg2.DataError: Ошибка данных.
            psycopg2.DatabaseError: Ошибка базы данных.
        """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT status_you_tube FROM users WHERE user_id = %s;', (user_id,))
            status = cursor.fetchone()[0]
            return status
    except psycopg2.DataError as error:
        logger.error(f"Ошибка данных при получении статуса обработки видео пользователя {user_id}: {error}")
        return None
    except psycopg2.DatabaseError as error:
        logger.error(f"Ошибка базы данных при получении статуса обработки видео пользователя {user_id}: {error}")
        return None
    except Exception as error:
        logger.error(f"Неизвестная ошибка при получении статуса обработки видео пользователя {user_id}: {error}")
        return None


def get_user_limit(user_id: int) -> Optional[float]:
    """
    Получает текущий лимит пользователя из базы данных.

    Args:
        user_id (int): Уникальный идентификатор пользователя.

    Returns:
        Optional[float]: Лимит пользователя или None, если лимит не найден.

    Raises:
        psycopg2.DataError: Ошибка данных.
        psycopg2.DatabaseError: Ошибка базы данных.
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT user_limit, created_at FROM user_limit WHERE user_id = %s', (user_id,))
            row = cursor.fetchone()
            if row:
                user_limit, last_update_time = row
                if datetime.now() - last_update_time > timedelta(days=1):
                    cursor.execute(
                        '''
                        UPDATE user_limit
                        SET user_limit = %s, created_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s
                        ''',
                        (INITIAL_LIMIT, user_id)
                    )
                    connection.commit()
                    logger.info(f"Лимит пользователя {user_id} сброшен до {INITIAL_LIMIT}")
                    return INITIAL_LIMIT
                return user_limit
            logger.warning(f"Лимит для пользователя {user_id} не найден.")
            return None
    except psycopg2.DataError as error:
        logger.error(f"Ошибка данных при получении лимита пользователя {user_id}: {error}")
        return None
    except psycopg2.DatabaseError as error:
        logger.error(f"Ошибка базы данных при получении лимита пользователя {user_id}: {error}")
        return None
    except Exception as error:
        logger.error(f"Неизвестная ошибка при получении лимита пользователя {user_id}: {error}")
        return None


def get_user_history(user_id: int) -> List[Dict[str, str]]:
    """
    Получает последние 5 записей из истории пользователя.

    Args:
        user_id (int): Уникальный идентификатор пользователя.

    Returns:
        List[Dict[str, str]]: Список записей истории пользователя.

    Raises:
        psycopg2.DatabaseError: Ошибка базы данных.
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                '''
                SELECT question, response 
                FROM user_history
                WHERE user_id = %s 
                ORDER BY id DESC
                LIMIT 5;
                ''',
                (user_id,)
            )
            history = cursor.fetchall()[::-1]
            logger.info(f"История для пользователя {user_id} успешно получена из базы данных.")
            return [{'question': row[0], 'response': row[1]} for row in history]
    except psycopg2.DatabaseError as error:
        logger.error(f"Ошибка базы данных при получении истории пользователя {user_id}: {error}")
        return []
    except Exception as error:
        logger.error(f"Неизвестная ошибка при получении истории пользователя {user_id}: {error}")
        return []


def update_user_limit(user_id: int, limit: int) -> None:
    """
    Обновляет лимит пользователя в таблице `user_limit` для указанного `user_id`.

    Args:
        user_id (int): Идентификатор пользователя.
        limit (int): Новый лимит пользователя.

    Raises:
        psycopg2.OperationalError: Ошибка соединения с базой данных PostgreSQL.
        psycopg2.DatabaseError: Общая ошибка базы данных PostgreSQL.
    """
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
                user_exists = cursor.fetchone()
                if user_exists:
                    cursor.execute(
                        'UPDATE user_limit SET user_limit = %s WHERE user_id = %s',
                        (limit, user_id)
                    )
                    connection.commit()
                    logger.info(f"Лимит {limit} пользователя {user_id} успешно обновлён в базе данных.")
                else:
                    logger.warning(f"Пользователь с user_id {user_id} не найден в таблице users.")

    except psycopg2.OperationalError as e:
        logger.error(f"Ошибка соединения с базой данных PostgreSQL при обновлении лимита пользователя {user_id}: {str(e)}")
    except psycopg2.DatabaseError as e:
        logger.error(f"Ошибка базы данных PostgreSQL при обновлении лимита пользователя {user_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при обновлении лимита пользователя {user_id}: {str(e)}")


def update_status_you_tube(user_id: int, status: int) -> None:
    """
        Обновляет статус обработки видео пользователя в таблице `users` для указанного `user_id`.

        Args:
            user_id (int): Идентификатор пользователя.
            status (int): Статус обработки видео.

        Raises:
            psycopg2.OperationalError: Ошибка соединения с базой данных PostgreSQL.
            psycopg2.DatabaseError: Общая ошибка базы данных PostgreSQL.
        """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE users SET status_you_tube = %s WHERE user_id = %s;", (status, user_id))
            connection.commit()

    except psycopg2.OperationalError as e:
        logger.error(f"Ошибка соединения с базой данных PostgreSQL при обновлении статуса обработки видео пользователя {user_id}: {str(e)}")
    except psycopg2.DatabaseError as e:
        logger.error(f"Ошибка базы данных PostgreSQL при обновлении статуса обработки видео пользователя {user_id}: {str(e)}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при обновлении статуса обработки видео пользователя {user_id}: {str(e)}")


def update_user_language(user_id: int, language: str) -> None:
    """
    Обновляет язык пользователя в базе данных и JSON-файле.

    Args:
        user_id (int): Уникальный идентификатор пользователя.
        language (str): Новый язык пользователя.

    Raises:
        psycopg2.DatabaseError: Ошибка базы данных.
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
            user_record = cursor.fetchone()

            if user_record:
                cursor.execute(
                    'UPDATE users SET language = %s WHERE user_id = %s',
                    (language, user_id)
                )
                connection.commit()
                logger.info(f"Язык пользователя {user_id} успешно обновлён в базе данных.")

                r.hset(f"user:{user_id}", "language", language)
                logger.info(f"Язык пользователя {user_id} успешно обновлён в Redis.")
            else:
                logger.warning(f"Пользователь с user_id {user_id} не найден в базе данных.")
    except psycopg2.DatabaseError as error:
        logger.error(f"Ошибка базы данных при обновлении языка пользователя {user_id}: {error}")
    except Exception as error:
        logger.error(f"Неизвестная ошибка при обновлении языка пользователя {user_id}: {error}")


def update_dialog_score(rating: str, response_id: int) -> None:
    """
    Обновляет оценку диалога для указанной записи в истории.

    Args:
        rating (str): Оценка ("👍" или "👎" или "😐").
        response_id (int): Идентификатор записи в истории.

    Raises:
        psycopg2.DatabaseError: Ошибка базы данных.
    """
    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute('SELECT * FROM user_history WHERE id = %s', (response_id,))

            cursor.execute(
                '''
                UPDATE user_history
                SET dialog_score = %s
                WHERE id = %s
                ''',
                (rating, response_id)
            )
            connection.commit()
            logger.info(f"Оценка для записи {response_id} успешно обновлена.")

            update_google_sheet_row(response_id, rating)

    except psycopg2.DatabaseError as error:
        logger.error(f"Ошибка базы данных при обновлении оценки диалога для записи {response_id}: {error}")
    except Exception as error:
        logger.error(f"Неизвестная ошибка при обновлении оценки диалога для записи {response_id}: {error}")

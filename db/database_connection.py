import logging
from typing import Dict
import os

import psycopg2
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

DB_CONFIG: Dict[str, str] = {
    'dbname': os.getenv('DB_NAME', ''),
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', ''),
    'port': os.getenv('DB_PORT', '')
}

def get_db_connection() -> psycopg2.extensions.connection:
    """
    Устанавливает соединение с базой данных PostgreSQL.

    Returns:
        psycopg2.extensions.connection: Соединение с базой данных.

    Raises:
        psycopg2.OperationalError: Ошибка операционного соединения.
        psycopg2.DatabaseError: Ошибка базы данных.
    """
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as error:
        logger.error(f"Ошибка операционного соединения с PostgreSQL: {error}")
        raise
    except psycopg2.DatabaseError as error:
        logger.error(f"Ошибка базы данных PostgreSQL: {error}")
        raise
    except Exception as error:
        logger.error(f"Неизвестная ошибка при подключении к PostgreSQL: {error}")
        raise

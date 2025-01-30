import logging
import os
import psycopg2
from typing import List, Optional

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import DefaultCredentialsError

from db.database_connection import get_db_connection

load_dotenv()
logger = logging.getLogger(__name__)

SERVICE_ACCOUNT_FILE: str = os.getenv('SERVICE_ACCOUNT_FILE')
SCOPES: List[str] = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID: str = os.getenv('SPREADSHEET_ID')

db_path: str = 'db/database.db'
db_exists: bool = os.path.exists(db_path)

max_sheet_length: int = 25000


def get_google_sheets_service() -> Optional[object]:
    """
    Авторизует и возвращает сервис Google Sheets API.

    Returns:
        Optional[object]: Объект сервиса Google Sheets API или None в случае ошибки.

    Raises:
        GoogleSheetsAuthError: Ошибка при авторизации Google Sheets API.
    """
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=credentials)
        logger.info("Авторизация Google Sheets успешна.")
        return service
    except DefaultCredentialsError as e:
        logger.error(f"Ошибка при авторизации Google Sheets: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при авторизации Google Sheets: {str(e)}")
        raise Exception(f"Ошибка при авторизации Google Sheets: {str(e)}")



def clear_google_sheet(service: object, sheet_name: str) -> None:
    """
    Очищает указанный диапазон листа Google Sheets.

    Args:
        service (object): Объект сервиса Google Sheets API.
        sheet_name (str): Имя листа или диапазон.

    Raises:
        GoogleSheetsClearError: Ошибка при очистке листа Google Sheets.
        Exception: Общая ошибка при попытке очистки листа.
    """
    try:
        service.spreadsheets().values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=sheet_name,
            body={}
        ).execute()
        logger.info(f"Диапазон {sheet_name} успешно очищен.")
    except HttpError as e:
        logger.error(f"Ошибка HTTP при очистке Google Sheets: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Ошибка при очистке Google Sheets: {str(e)}")
        raise Exception(f"Ошибка при очистке листа {sheet_name}: {str(e)}")


def get_data_user_from_psycopg2(table_name: str) -> List[List[Optional[str]]]:
    """
    Извлекает данные из PostgreSQL с фильтрацией по отрицательным оценкам.

    Args:
        table_name (str): Имя таблицы в базе данных.

    Returns:
        List[List[Optional[str]]]: Список строк с ограничением длины.

    Raises:
        psycopg2.OperationalError: Ошибка операционного соединения с базой данных.
        psycopg2.DatabaseError: Ошибка при выполнении запроса к базе данных.
        Exception: Общая ошибка при извлечении данных.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id, question, response, dialog_score FROM {table_name};")
            data = cursor.fetchall()
            limited_data = [
                [
                    item[:max_sheet_length] if isinstance(item, str) else item
                    for item in row
                ]
                for row in data
            ]
            logger.info(f"Данные из таблицы {table_name} успешно извлечены.")
            return limited_data
    except psycopg2.OperationalError as e:
        logger.error(f"Ошибка операционного соединения с базой данных PostgreSQL: {str(e)}")
        return []
    except psycopg2.DatabaseError as e:
        logger.error(f"Ошибка при выполнении запроса к базе данных PostgreSQL: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при извлечении данных из базы данных PostgreSQL: {str(e)}")
        return []


def append_data_to_sheet(service: object, data: List[List[Optional[str]]], sheet_name: str) -> None:
    """
    Добавляет данные в Google Sheets.

    Args:
        service (object): Объект сервиса Google Sheets API.
        data (List[List[Optional[str]]]): Данные для добавления.
        sheet_name (str): Имя листа или диапазон.

    Raises:
        googleapiclient.errors.HttpError: Ошибка HTTP при взаимодействии с Google Sheets API.
        Exception: Общая ошибка при добавлении данных в Google Sheets.
    """
    try:
        body = {'values': data}
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=sheet_name,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        logger.info(f"{result.get('updates').get('updatedCells')} ячеек добавлено в {sheet_name}.")
    except HttpError as e:
        logger.error(f"Ошибка HTTP при добавлении данных в Google Sheets: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при добавлении данных в Google Sheets: {str(e)}")


def append_row_to_google_sheet(
        row_data: List[Optional[str]],
        sheet_name: str,
        service: object=get_google_sheets_service()
) -> None:
    """
    Добавляет строку данных в Google Sheets.

    Args:
        service (object): Объект сервиса Google Sheets API.
        row_data (List[Optional[str]]): Данные для добавления.
        sheet_name (str): Имя листа или диапазон.

    Raises:
        googleapiclient.errors.HttpError: Ошибка HTTP при взаимодействии с Google Sheets API.
        Exception: Общая ошибка при добавлении строки в Google Sheets.
    """
    try:
        body = {'values': [row_data]}
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=sheet_name,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        logger.info(f"{result.get('updates').get('updatedCells')} ячеек добавлено в лист {sheet_name}.")
    except HttpError as e:
        logger.error(f"Ошибка HTTP при добавлении строки в Google Sheets: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при добавлении строки в Google Sheets: {str(e)}")


def get_google_sheet_data(sheet_name: str, service: object = get_google_sheets_service()) -> List[List[str]]:
    """
    Получает все данные с листа Google Sheets.

    Args:
        sheet_name (str): Имя листа или диапазон.
        service (object): Объект сервиса Google Sheets API.

    Returns:
        List[List[str]]: Данные из листа Google Sheets.

    Raises:
        HttpError: Ошибка HTTP при получении данных из Google Sheets.
    """
    try:
        sheet_data = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=sheet_name
        ).execute()
        return sheet_data.get("values", [])
    except HttpError as e:
        logger.error(f"Ошибка HTTP при получении данных из Google Sheets: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении данных из Google Sheets: {str(e)}")
        return []


def update_google_sheet_row(
        response_id: int,
        new_value: str,
        sheet_name: str = 'history',
        column_index: int = 3,
        service: object = get_google_sheets_service()
) -> None:
    """
    Обновляет значение в указанной строке Google Sheets по response_id.

    Args:
        response_id (int): Идентификатор записи для поиска.
        new_value (str): Новое значение для обновления.
        sheet_name (str): Имя листа или диапазон.
        column_index (int): Индекс столбца (начинается с 0).
        service (object): Объект сервиса Google Sheets API.

    Raises:
        HttpError: Ошибка HTTP при обновлении строки.
        Exception: Общая ошибка при обновлении строки Google Sheets.
    """
    try:
        sheet_data = get_google_sheet_data(sheet_name='history', service=get_google_sheets_service())
        updated = False

        for i, row in enumerate(sheet_data):
            if len(row) > 0 and str(row[0]) == str(response_id):
                if len(row) <= column_index:
                    row.extend([''] * (column_index - len(row) + 1))
                row[column_index] = new_value

                service.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{sheet_name}!A{i+1}",
                    valueInputOption="RAW",
                    body={"values": [row]}
                ).execute()

                logger.info(f"Строка с response_id {response_id} успешно обновлена.")
                updated = True
                break

        if not updated:
            logger.warning(f"Строка с response_id {response_id} не найдена в Google Sheets.")
    except HttpError as e:
        logger.error(f"Ошибка HTTP при обновлении строки в Google Sheets: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка при обновлении строки в Google Sheets: {str(e)}")


def google_sheets() -> None:
    """
    Синхронизирует данные из базы данных PostgreSQL с Google Sheets.

    Получает данные из базы данных, очищает соответствующий лист в Google Sheets,
    а затем добавляет данные о пользовательской истории.

    Raises:
        ConnectionError: Ошибка при подключении к Google Sheets.
        ValueError: Ошибка при обработке данных для синхронизации.
        Exception: Неопознанная ошибка при синхронизации с Google Sheets.
    """
    try:
        service = get_google_sheets_service()

        if service:
            clear_google_sheet(service, 'history')

            data_user_history = get_data_user_from_psycopg2('user_history')

            if data_user_history:
                append_data_to_sheet(service, data_user_history, 'history')
            else:
                logger.info("Нет данных с отрицательными оценками для синхронизации.")
        else:
            logger.error("Не удалось подключиться к Google Sheets.")

    except ConnectionError as e:
        logger.error(f"Ошибка подключения к Google Sheets: {str(e)}")
    except ValueError as e:
        logger.error(f"Ошибка данных при синхронизации с Google Sheets: {str(e)}")
    except Exception as e:
        logger.error(f"Неизвестная ошибка при синхронизации с Google Sheets: {str(e)}")

import json
import logging
import os
from datetime import datetime
from typing import Optional

import requests
import tzlocal

logger = logging.getLogger(__name__)

GRASPIL_API_KEY = os.getenv("GRASPIL_API_KEY")
GRASPIL_API_URL = "https://api.graspil.com/v1/send-target"

async def analytics_creating_target(
    user_id: int,
    user_name: str,
    target_start_id: int,
    value: Optional[float] = None,
    unit: Optional[str] = None
) -> None:
    """
    Отправляет целевое событие в API Graspil.

    Args:
        user_id (int): Идентификатор пользователя.
        user_name (str): Имя пользователя.
        target_start_id (int): Идентификатор целевого события.
        value (Optional[float]): Значение целевого события (опционально).
        unit (Optional[str]): Единица измерения значения (опционально).

    Returns:
        None: Функция не возвращает значения.

    Raises:
        Exception: Для любых ошибок в процессе отправки события.
    """
    try:
        local_timezone = tzlocal.get_localzone()
        current_time = datetime.now(local_timezone)
        formatted_time = current_time.strftime('%Y-%m-%dT%H:%M:%S%z')
        formatted_time = formatted_time[:-2] + ':' + formatted_time[-2:]

        event_data = {
            "target_id": target_start_id,
            "user_id": user_id,
            "date": formatted_time,
            "value": value,
            "unit": unit
        }

        headers = {
            "Api-Key": GRASPIL_API_KEY,
            "Content-Type": "application/json"
        }

        response = requests.post(GRASPIL_API_URL, headers=headers, json=event_data)

        if response.status_code == 200 and response.json().get("ok"):
            logger.info(f"Целевое событие для пользователя {user_name} (ID: {user_id}) успешно отправлено.")
        else:
            logger.error(f"Ошибка при отправке целевого события: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка в процессе отправки целевого события: {e}")

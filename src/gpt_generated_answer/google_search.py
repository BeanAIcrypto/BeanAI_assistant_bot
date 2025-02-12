import logging
import re
from typing import Any

import requests
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from langchain.tools import BaseTool

logger = logging.getLogger(__name__)


class GoogleSearchAPIWrapper(BaseTool):
    """
    Обёртка для выполнения поиска в Google и загрузки содержимого страниц.

    Атрибуты:
        name (str): Название инструмента.
        description (str): Описание функционала инструмента.
        api_key (str): API-ключ для Google Custom Search.
        search_engine_id (str): Идентификатор поисковой системы.
        service (Any): Сервис Google Custom Search API.
    """

    name: str = "Google Search"
    description: str = (
        "Инструмент для выполнения поиска в Google с загрузкой содержимого страниц."
    )
    api_key: str
    search_engine_id: str
    service: Any = None

    def __init__(self, **kwargs):
        """
        Инициализация инструмента GoogleSearchAPIWrapper.

        Args:
            **kwargs: Параметры для инициализации, включая api_key и search_engine_id.

        Raises:
            Exception: Если не удалось инициализировать Google API.
        """
        super().__init__(**kwargs)
        try:
            self.service = build(
                "customsearch", "v1", developerKey=self.api_key
            )
            logger.info(
                "Сервис Google Custom Search API успешно инициализирован."
            )
        except Exception as e:
            logger.error(f"Ошибка инициализации Google API: {e}")
            raise

    def _fetch_page_content(self, url: str) -> str:
        """
        Загрузка и парсинг содержимого веб-страницы.

        Args:
            url (str): URL страницы для загрузки.

        Returns:
            str: Текстовое содержимое страницы или сообщение об ошибке.

        Raises:
            requests.RequestException: Ошибки при выполнении HTTP-запроса.
            Exception: Ошибки при обработке страницы.
        """
        try:
            logger.info(f"Загрузка содержимого страницы: {url}")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            text = soup.get_text(separator="\n")

            # Очистка текста
            text = re.sub(r"\* .+\n", "", text)
            text = re.sub(r"\+\d+ \(\d+\) \d+-\d+-\d+", "", text)
            text = re.sub(r"\w+@\w+\.\w+", "", text)
            text = re.sub(r"__+", "", text)
            text = re.sub(r"https?://\S+", "", text)
            text = re.sub(r"\[\d+\]", "", text)
            text = re.sub(r"©\s?\d{4}.+\n", "", text)
            text = re.sub(r"All rights reserved.?\n", "", text)
            text = re.sub(r"\n\s*\n", "\n", text)
            text = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}", "", text)
            text = re.sub(r"\d{1,2}\.\d{1,2}\.\d{2,4}", "", text)
            text = re.sub(r"Follow us on .+\n", "", text)
            text = re.sub(r" {2,}", " ", text)

            return text.strip()
        except requests.RequestException as e:
            logger.error(f"Ошибка HTTP-запроса для страницы {url}: {e}")
            return "Не удалось загрузить содержимое страницы."
        except Exception as e:
            logger.error(f"Ошибка при обработке страницы {url}: {e}")
            return "Ошибка обработки содержимого страницы."

    def _run(self, query: str) -> str:
        """
        Выполнение синхронного поиска в Google.

        Args:
            query (str): Поисковый запрос.

        Returns:
            str: Результаты поиска с содержимым страниц или сообщение об ошибке.

        Raises:
            Exception: Ошибки при выполнении поиска или загрузке страниц.
        """
        try:
            logger.info(f"Выполняем поиск в Google по запросу: '{query}'")
            res = (
                self.service.cse()
                .list(q=query, cx=self.search_engine_id, num=1)
                .execute()
            )

            if "items" not in res:
                return "Результаты поиска не найдены."

            results = res["items"]
            detailed_results = []

            for item in results:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                page_content = self._fetch_page_content(link)

                detailed_results.append(
                    f"Заголовок: {title}\nОтрывок: {snippet}\nСсылка: {link}\nСодержимое:\n{page_content}"
                )

            return "\n\n".join(detailed_results)

        except Exception as e:
            logger.error(f"Ошибка при выполнении Google Search: {e}")
            return "Ошибка при выполнении поиска."

    async def _arun(self, query: str) -> str:
        """
        Асинхронный поиск в Google (не реализован).

        Args:
            query (str): Поисковый запрос.

        Returns:
            str: Исключение NotImplementedError.

        Raises:
            NotImplementedError: Если функция не реализована.
        """
        raise NotImplementedError("Асинхронная функция _arun не реализована.")

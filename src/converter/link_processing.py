import logging
import re

import aiohttp
import cloudscraper
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


logger = logging.getLogger(__name__)

def clean_text(text: str) -> str:
    """
    Очищает текст от нежелательных элементов, таких как списки, ссылки, лишние пробелы и строки.

    Args:
        text (str): Исходный текст для очистки.

    Returns:
        str: Очищенный текст.

    Raises:
        Exception: Ошибка при очистке текста.
    """
    try:
        text = re.sub(r"\* .+\n", "", text)  # Удаление списков с "*"
        text = re.sub(r"\+\d+ \(\d+\) \d+-\d+-\d+", "", text)  # Телефонные номера
        text = re.sub(r"\w+@\w+\.\w+", "", text)  # Email-адреса
        text = re.sub(r"__+", "", text)  # Линии из "_"
        text = re.sub(r"https?://\S+", "", text)  # URL-ссылки
        text = re.sub(r"\[\d+\]", "", text)  # Ссылки на источники
        text = re.sub(r"©\s?\d{4}.+\n", "", text)  # Копирайт
        text = re.sub(r"All rights reserved.?\n", "", text)  # Фразы о правах
        text = re.sub(r"\n\s*\n", "\n", text)  # Лишние пустые строки
        text = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}", "", text)  # Даты в формате 01/01/2020
        text = re.sub(r"\d{1,2}\.\d{1,2}\.\d{2,4}", "", text)  # Даты в формате 01.01.2020
        text = re.sub(r"Follow us on .+\n", "", text)  # Социальные ссылки
        text = re.sub(r" {2,}", " ", text)  # Лишние пробелы
        return text.strip()
    except Exception as e:
        logger.error(f"Ошибка при очистке текста: {e}")
        return text


def html_to_text(html_content: str) -> str:
    """
    Конвертирует HTML-контент в простой текст.

    Args:
        html_content (str): HTML-контент.

    Returns:
        str: Текст, извлечённый из HTML-контента.

    Raises:
        Exception: Ошибка при преобразовании HTML в текст.
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text(separator='\n').strip()
    except Exception as e:
        logger.error(f"Ошибка при преобразовании HTML в текст: {e}")
        return ""


async def process_dynamic_page(url: str) -> str:
    """
    Обрабатывает динамическую HTML-страницу с помощью Playwright, возвращая текстовое содержимое.

    Args:
        url (str): URL страницы для обработки.

    Returns:
        Optional[str]: Текстовое содержимое страницы или None в случае ошибки.

    Raises:
        ValueError: Если получен неверный ответ или страница требует JavaScript.
        Exception: Общая ошибка при обработке динамической страницы.
    """
    logger.info(f"Обработка динамической страницы: {url}")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                response = await page.goto(url, wait_until='networkidle', timeout=60000)
                await page.wait_for_timeout(10000)
            except PlaywrightTimeoutError:
                logger.error("Таймаут при загрузке динамической страницы.")
                await browser.close()
                return None

            if not response or response.status != 200:
                logger.error(f"Код ответа: {response.status if response else 'None'}")
                await browser.close()
                return None

            content = await page.content()
            if "Please enable JavaScript" in content or "Checking your browser" in content:
                logger.error("Доступ к странице запрещен: требуется JavaScript.")
                await browser.close()
                return None

            text_content = html_to_text(content)
            cleaned_text = clean_text(text_content)

            logger.info(f"Очищенный текст: {cleaned_text[:200]}...")
            await browser.close()
            return cleaned_text

    except PlaywrightTimeoutError as te:
        logger.error(f"Таймаут при обработке страницы {url}: {te}")
        return None

    except Exception as e:
        logger.error(f"Неизвестная ошибка при обработке динамической страницы {url}: {e}")
        return None


async def process_static_page(url: str) -> str:
    """
    Обрабатывает статическую HTML-страницу, возвращая текстовое содержимое.

    Args:
        url (str): URL страницы для обработки.

    Returns:
        Optional[str]: Текстовое содержимое страницы или None в случае ошибки.

    Raises:
        aiohttp.ClientError: Ошибка при выполнении HTTP-запроса.
        ValueError: Ошибка преобразования HTML в текст.
        Exception: Общая ошибка при обработке статической страницы.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Ошибка доступа к статической странице. Код ответа: {response.status}")
                    return None

                content = await response.text()

        text_content = html_to_text(content)
        cleaned_text = clean_text(text_content)

        logger.info(f"Очищенный текст: {cleaned_text[:200]}...")
        return cleaned_text

    except aiohttp.ClientError as ce:
        logger.error(f"Ошибка сети при обработке статической страницы {url}: {ce}")
        return None

    except ValueError as ve:
        logger.error(f"Ошибка преобразования HTML в текст для страницы {url}: {ve}")
        return None

    except Exception as e:
        logger.error(f"Неизвестная ошибка при обработке статической страницы {url}: {e}")
        return None


def process_with_cloudscraper(url: str) -> str:
    """
    Обрабатывает страницу с помощью Cloudscraper для обхода Cloudflare.

    Args:
        url (str): Ссылка для обработки.

    Returns:
        Optional[str]: Текстовое содержимое страницы или None в случае ошибки.

    Raises:
        Exception: Ошибка при обработке ссылки через Cloudscraper.
    """
    logger.info(f"Обработка ссылки через Cloudscraper: {url}")
    try:
        scraper = cloudscraper.create_scraper(browser='chrome')
        response = scraper.get(url)
        if response.status_code != 200:
            logger.error(f"Не удалось получить контент через Cloudscraper. Код: {response.status_code}")
            return None

        content = response.text
        text_content = html_to_text(content)
        cleaned_text = clean_text(text_content)
        logger.info(f"Очищенный текст (Cloudscraper): {cleaned_text[:200]}...")
        return cleaned_text
    except Exception as e:
        logger.error(f"Ошибка при обработке ссылки через Cloudscraper: {e}")
        return None


async def link_processing(url: str) -> str:
    """
    Обрабатывает URL, возвращая содержимое страницы.

    Сначала пытается получить статический контент. Если это не удалось
    или недостаточно данных, пытается обойти Cloudflare с помощью Cloudscraper.
    Если и это не помогло, использует Playwright для динамической загрузки страницы.

    Args:
        url (str): Ссылка для обработки.

    Returns:
        Optional[str]: Содержимое страницы или None в случае ошибки.

    Raises:
        ValueError: Ошибка при обработке статической или динамической страницы.
        Exception: Общая ошибка при обработке URL.
    """
    try:
        logger.info(f"Обработка ссылки: {url}")

        static_content = await process_static_page(url)
        if static_content and len(static_content.strip()) > 500:
            logger.info("Обработано как статическая страница.")
            return static_content

        logger.info("Обрабатывается через Cloudscraper.")
        cloudscraper_content = process_with_cloudscraper(url)
        if cloudscraper_content and len(cloudscraper_content.strip()) > 500:
            logger.info("Обработано через Cloudscraper.")
            return cloudscraper_content

        logger.info("Обрабатывается как динамическая страница.")
        dynamic_content = await process_dynamic_page(url)
        return dynamic_content

    except ValueError as ve:
        logger.error(f"Ошибка при обработке страницы: {ve}")
        return None

    except Exception as e:
        logger.error(f"Общая ошибка при обработке ссылки {url}: {e}")
        return None

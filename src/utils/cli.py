import argparse
import sys
import logging

logger = logging.getLogger(__name__)


def parse_arguments():
    """
    Анализирует входные параметры с помощью argparse.

    Returns:
        argparse.Namespace: Объект с аргументами командной строки.

    Raises:
        argparse.ArgumentError: Ошибка при парсинге аргументов.
        SystemExit: Выход из программы, если произошла ошибка.
    """
    try:
        parser = argparse.ArgumentParser(
            description="Парсинг входных параметров"
        )

        parser.add_argument(
            "--init",
            default=False,
            action="store_true",
            help="Флаг, указывающий на инициализацию без реального выполнения",
        )

        args = parser.parse_args()

        return args

    except argparse.ArgumentError as e:
        logger.error(f"Ошибка при парсинге аргументов: {e}")
        sys.exit(1)

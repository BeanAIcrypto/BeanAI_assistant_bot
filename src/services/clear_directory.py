import os
import logging


logger = logging.getLogger(__name__)


async def clear_directory(directory: str) -> None:
    """
    Удаляет указанную директорию вместе со всем её содержимым.

    Args:
        directory (str): Путь к директории, которую необходимо удалить.

    Returns:
        None

    Raises:
        FileNotFoundError: Если указанная директория не существует.
        PermissionError: Если недостаточно прав для удаления файлов или папок.
        OSError: Для других ошибок, связанных с удалением файлов или папок.
    """
    if os.path.exists(directory):
        for root, dirs, files in os.walk(directory, topdown=False):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    os.remove(file_path)
                except OSError as e:
                    logger.error(
                        f"Ошибка при удалении файла {file_path}: {str(e)}"
                    )
            for d in dirs:
                dir_path = os.path.join(root, d)
                try:
                    os.rmdir(dir_path)
                except OSError as e:
                    logger.error(
                        f"Ошибка при удалении папки {dir_path}: {str(e)}"
                    )
        try:
            os.rmdir(directory)
        except OSError as e:
            logger.error(f"Ошибка при удалении папки {directory}: {str(e)}")

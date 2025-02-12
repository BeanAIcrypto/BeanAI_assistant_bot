import logging

"""Настройка логирования."""
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/LOG_file.log"),
    ],
    force=True,
)

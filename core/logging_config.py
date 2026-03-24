import logging
import os


def get_logger():
    # Create logger
    logger = logging.getLogger("konnected_app")
    logger.setLevel(logging.INFO)

    if not logger.handlers:

        # Format of logs
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )

        # File handler (writes logs to file)
        file_handler = logging.FileHandler("app.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console handler (shows logs in terminal)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

logger = get_logger()
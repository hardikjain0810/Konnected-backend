import logging
import sys

def setup_logger():
    logger = logging.getLogger("konnected_app")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        # Console handler
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        stream_handler.setFormatter(stream_formatter)
        logger.addHandler(stream_handler)

        # File handler
        file_handler = logging.FileHandler("app.log")
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
    return logger

logger = setup_logger()

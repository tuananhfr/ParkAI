import logging
import sys
from datetime import datetime


def setup_logger(name="ParkAI", level=logging.INFO):
    """
    Setup logger với format đẹp cho console

    Args:
        name: Tên logger
        level: Log level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Xóa handlers cũ nếu có (tránh duplicate logs)
    if logger.handlers:
        logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Format: [2024-12-04 10:30:45] [INFO] Message
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


# Global logger instance
logger = setup_logger()

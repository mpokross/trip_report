import logging
import sys
from pathlib import Path
from typing import Optional, Union, Literal


def setup_logging(
        log_file: Optional[Union[str, Path]] = None,
        log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO',
        log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
) -> logging.Logger:
    """
    Centralized logging configuration for the IMCA Report Generator.
    
    Args:
        log_file: Optional path to log file. If None, logs to console.
        log_level: Logging level (default: INFO)
        log_format: Format of log messages
    
    Returns:
        Configured logger
    """
    # Convert log level to logging constant
    numeric_level = getattr(logging, log_level.upper())

    # Create logger
    logger = logging.getLogger('imca_report')
    logger.setLevel(numeric_level)

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if log_file is provided)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = 'imca_report') -> logging.Logger:
    """
    Get a child logger for a specific module.
    
    Args:
        name: Name of the logger (defaults to 'imca_report')
    
    Returns:
        Configured logger
    """
    return logging.getLogger(name)

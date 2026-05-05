from loguru import logger
from pathlib import Path
import sys

def setup_logger(logger_directory: str = "logs") -> bool:
    logger_path = Path(logger_directory)
    logger_path.mkdir(exist_ok=True)
    
    logger.remove()
    
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
               "<level>{message}</level>",
        colorize=True,
    )
    
    logger.add(
        logger_path / "debug.log",
        level="DEBUG",
        rotation="500 MB",
        encoding="utf-8",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        backtrace=True,
        diagnose=True,
    )
    
    logger.add(
        logger_path / "info.log",
        level="INFO",
        rotation="1024 MB",
        encoding="utf-8",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
    )
    
    logger.add(
        logger_path / "error.log",
        level="ERROR",
        rotation="100 MB",
        encoding="utf-8",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
        backtrace=True,
        diagnose=True,
    )
    
    logger.info("Логирование настроено | логи в: {}", logger_path.absolute())
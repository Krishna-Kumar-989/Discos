import logging
import sys
from pathlib import Path

def setup_logger(name: str, level_name: str = "INFO", log_file: Path = None) -> logging.Logger:
    """Set up and return a configured logger."""
    logger = logging.getLogger(name)
    

    if logger.hasHandlers():
        return logger
        
    level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(level)
    
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
    return logger

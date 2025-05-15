import logging
import os
from datetime import datetime

def initialize_test_logger(log_dir="test_logs"):
    """
    Initializes logging for test cases.
    Args:
        log_dir (str): Directory to save the log file. Default is "test_logs".
    """
    os.makedirs(log_dir, exist_ok=True)
    log_filename = datetime.now().strftime("test_%m-%d-%Y_%H-%M-%S.log")
    log_path = os.path.join(log_dir, log_filename)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Console output (so you can still see in terminal)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console_handler)

    # File output (persistent log file for test runs)
    file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%m-%d-%Y_%H-%M-%S"))
    logger.addHandler(file_handler)

    logger.info(f"Test logging initialized → {log_path}")

import os
import subprocess # Run ImageMagick CLI command
import logging # Logging setup
from datetime import datetime
import time
import shutil

# --- FUNCTION: Yields successive batches (sublists) from a list.
def split_into_batches(items, batch_size):
    """Splits a list into batches of size `batch_size`."""
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]


# --- FUNCTION: Generate all relevant file paths for a given input filename ---
def get_file_paths(filename, tmp_dir, input_dir, output_dir):
    base_name, _ = os.path.splitext(filename)
    return {
        "base_name": base_name,
        "path_to_file": os.path.join(input_dir, filename),
        "jpg_file": os.path.join(input_dir, filename),
        "pdf_file": os.path.join(tmp_dir, f"{base_name}.pdf"),
        "s3_pdf_key": f"{base_name}.pdf",
        "doc_output_dir": os.path.join(output_dir, base_name),
    }

# --- FUNCTION: Convert a .jpg file to .pdf using ImageMagick ---
def convert_jpg_to_pdf(jpg_path, pdf_path, image_magick_command="convert", filename=""):
    try:
        logging.info(f"Converting {filename} to PDF...")
        subprocess.run([image_magick_command, jpg_path, pdf_path], check=True)
    except subprocess.CalledProcessError as e:
        logging.error(f"ImageMagick failed to convert {jpg_path} to PDF: {e}")
        raise

# --- FUNCTION: Wipe and recreate the tmp_dir ---
def clean_tmp_folder(tmp_dir):
    try:
        shutil.rmtree(tmp_dir)  # Delete entire temp folder and contents
        os.makedirs(tmp_dir, exist_ok=True)  # Recreate clean folder
        logging.info("Cleaned up temporary directory.")
    except Exception as e:
        logging.error(f"Failed to clean temporary directory: {e}")

# --- FUNCTION: Initialize logging to both file and console ---
def initialize_logging(log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)

    log_filename = datetime.now().strftime("%m-%d-%Y_%H-%M-%S.log")
    log_path = os.path.join(log_dir, log_filename)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    # Root logger setup
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # Avoid duplicate logs if reinitialized
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logging.info("Logging initialized.")
    return log_path

# --- FUNCTION: Add total runtime to logs ---
def log_runtime(start_time):
    hrs, rem = divmod(time.time() - start_time, 3600)
    mins, secs = divmod(rem, 60)
    logging.info(f"Pipeline completed in {int(hrs)}h {int(mins)}m {int(secs)}s.")

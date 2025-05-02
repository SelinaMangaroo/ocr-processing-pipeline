import os # File and path handling
import subprocess # Run ImageMagick CLI command
import glob # File matching for cleanup
import logging # Logging setup
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
tmp_dir = os.environ.get("TMP_DIR")
image_magick_command = os.environ.get("IMAGE_MAGICK_COMMAND", "convert")

# --- FUNCTION:    Splits a list into smaller batches of size `batch_size`.
def split_into_batches(list, batch_size):
    for i in range(0, len(list), batch_size):
        yield list[i:i + batch_size]

# --- FUNCTION: Convert a .jpg file to .pdf using ImageMagick ---
# TODO: magick does not work on Linux, use convert instead, make this configurable
def convert_jpg_to_pdf(jpg_path, pdf_path):
    subprocess.run([image_magick_command, jpg_path, pdf_path], check=True)

# --- FUNCTION: Clean up all temporary files in tmp_dir ---
def clean_tmp_folder():
    for file in glob.glob(os.path.join(tmp_dir, "*")):
        os.remove(file)
    logging.info("Cleaned up temporary files.")

# --- FUNCTION: Logging setup ---
def initialize_logging(log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    log_filename = datetime.now().strftime("%m-%d-%Y_%H-%M-%S.log")
    log_path = os.path.join(log_dir, log_filename)

    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

    logging.info("Logging initialized.")
    return log_path

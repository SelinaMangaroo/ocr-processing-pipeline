from utils.aws_utils import *
from utils.helpers import *
from utils.chatgpt_utils import *
import os    
import logging
import time
import boto3  # AWS SDK for Python
from openai import OpenAI
from dotenv import load_dotenv
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Load environment variables ---
load_dotenv()
bucket_name = os.environ.get("BUCKET_NAME")
region = os.environ.get("REGION")
tmp_dir = os.environ.get("TMP_DIR")
input_dir = os.environ.get("INPUT_DIR")
output_dir = os.environ.get("OUTPUT_DIR")
batch_size = int(os.environ.get("BATCH_SIZE", 10))  # Default batch size is 10
image_magick_command = os.environ.get("IMAGE_MAGICK_COMMAND", "convert")
api_key = os.environ.get("OPENAI_API_KEY")
model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")  # fallback default

# --- Initialize logging ---
log_path = initialize_logging()
logging.info("Textract processing pipeline started.")

start_time = time.time()  # Start tracking time

# --- Ensure directories exist ---
os.makedirs(tmp_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

# --- AWS Client ---
s3 = boto3.client('s3', region_name=region)
textract = boto3.client('textract', region_name=region) # Create Textract client for OCR processing

# --- ChatGPT Client ---
chat_gpt_client = OpenAI(api_key=api_key)

# --- Read all files ---
if not input_dir or not os.path.isdir(input_dir):
    logging.error("INPUT_DIR is not set or does not exist.")
    exit(1)

# --- Use max_workers Based on CPU Count ---
max_threads = min(8, multiprocessing.cpu_count() * 2)

def prepare_file_for_textract(filename):
    """
    Prepares a file for Textract processing by converting it to PDF and uploading it to S3.
    Args:
        filename (str): The name of the file to process.
    Returns:
        tuple: Base name and job information.
    """
    try:
        paths = get_file_paths(filename, tmp_dir, input_dir, output_dir)
        base_name = paths["base_name"]
        os.makedirs(paths["doc_output_dir"], exist_ok=True)

        convert_to_pdf(paths["path_to_file"], paths["pdf_file"], image_magick_command, filename)

        upload_file_to_s3(paths["pdf_file"], s3, bucket_name, paths["s3_pdf_key"])

        job_id = start_textract_job(paths["s3_pdf_key"], textract, bucket_name)

        return base_name, {
            "job_id": job_id,
            "doc_output_dir": paths["doc_output_dir"],
            "s3_pdf_key": paths["s3_pdf_key"],
        }
    except Exception as e:
        logging.error(f"Error processing {filename}: {e}")
        return None

def process_textract_result(base_name, job_info):
    """
    Processes the Textract result by waiting for completion and extracting text and coordinates.
    Args:
        base_name (str): The base name of the file.
        job_info (dict): Job information including job ID and output directory.
    """
    job_id = job_info["job_id"]
    doc_output_dir = job_info["doc_output_dir"]

    logging.info(f"Waiting on Textract for: {base_name}.pdf")

    if wait_for_completion(job_id, textract):
        extract_and_save_text_and_coords(job_id, base_name, doc_output_dir, textract)
        logging.info(f"Textract complete: {base_name}")

        raw_path = os.path.join(doc_output_dir, base_name + ".raw.txt")
        with open(raw_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        corrected_path = correct_text_with_chatgpt(raw_text, base_name, doc_output_dir, chat_gpt_client, model_name)

        if corrected_path and os.path.exists(corrected_path):
            with open(corrected_path, "r", encoding="utf-8") as cf:
                corrected_text = cf.read()
            extract_entities_with_chatgpt(corrected_text, base_name, doc_output_dir, chat_gpt_client, model_name)
        else:
            logging.warning(f"Corrected text not found for {base_name}, using raw text.")
            extract_entities_with_chatgpt(raw_text, base_name, doc_output_dir, chat_gpt_client, model_name)

files = [
    f for f in os.listdir(input_dir)
    if f.lower().endswith((".jpg", ".jpeg"))
]
batches = list(split_into_batches(files, batch_size))

# --- Process in batches ---
for batch_index, current_batch in enumerate(batches):
    logging.info(f"Processing batch {batch_index + 1} of {len(batches)}")

    jobs = {}
    
    # --- Parallel file preparation ---
    # Use ThreadPoolExecutor to prepare files for Textract in parallel
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [executor.submit(prepare_file_for_textract, filename) for filename in current_batch]
        for future in as_completed(futures):
            result = future.result()
            if result:
                base_name, job_info = result
                jobs[base_name] = job_info

    # --- Parallel result processing ---
    # Use ThreadPoolExecutor to process Textract results in parallel
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = [executor.submit(process_textract_result, base_name, job_info) for base_name, job_info in jobs.items()]
        for future in as_completed(futures):
            future.result()

    clean_tmp_folder(tmp_dir)
    delete_all_files_in_bucket(s3, bucket_name)

log_runtime(start_time)
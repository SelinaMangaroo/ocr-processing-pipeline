from utils.aws_utils import *
from utils.helpers import *
from utils.chatgpt_utils import *

import boto3  # AWS SDK for Python
import os     # File and path handling
import logging
import shutil
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()
bucket_name = os.environ.get("BUCKET_NAME")
tmp_dir = os.environ.get("TMP_DIR")
input_dir = os.environ.get("INPUT_DIR")
output_dir = os.environ.get("OUTPUT_DIR")
region = os.environ.get("REGION")
batch_size = int(os.environ.get("BATCH_SIZE", 10))  # Default batch size is 10

# --- Initialize logging ---
log_path = initialize_logging()
logging.info("Textract processing pipeline started.")

# --- Ensure directories exist ---
os.makedirs(tmp_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)

# --- AWS Client ---
s3 = boto3.client('s3', region_name=region)

# --- Read all files ---
if not input_dir or not os.path.isdir(input_dir):
    logging.error("INPUT_DIR is not set or does not exist.")
    exit(1)

files = [
    f for f in os.listdir(input_dir)
    if f.lower().endswith((".jpg", ".jpeg"))
]
batches = list(split_into_batches(files, batch_size))

# --- Process in batches ---
for batch_index, current_batch in enumerate(batches):
    logging.info(f"Processing batch {batch_index + 1} of {len(batches)}")

    jobs = {}
    successfully_processed_jpgs = []
    successfully_processed_pdfs = []

    for filename in current_batch:
        base_name = os.path.splitext(filename)[0]
        local_path = os.path.join(input_dir, filename)
        local_jpg = os.path.join(tmp_dir, filename)
        local_pdf = os.path.join(tmp_dir, base_name + ".pdf")
        s3_jpg_key = filename
        s3_pdf_key = base_name + ".pdf"

        doc_output_dir = os.path.join(output_dir, base_name)
        os.makedirs(doc_output_dir, exist_ok=True)

        try:
            # Upload JPG to S3
            s3.upload_file(local_path, bucket_name, s3_jpg_key)
            logging.info(f"Uploaded to S3: {s3_jpg_key}")

            # Copy to tmp_dir for processing
            shutil.copy(local_path, local_jpg)

            # Convert to PDF
            logging.info(f"Converting {filename} to PDF...")
            convert_jpg_to_pdf(local_jpg, local_pdf)

            # Upload PDF to S3
            s3.upload_file(local_pdf, bucket_name, s3_pdf_key)
            logging.info(f"Uploaded PDF to S3: {s3_pdf_key}")

            # Save local copy
            shutil.copy(local_pdf, os.path.join(doc_output_dir, base_name + ".pdf"))

            # Start Textract
            job_id = start_textract_job(s3_pdf_key)

            # Store job info and corresponding file keys
            jobs[base_name] = {
                "job_id": job_id,
                "doc_output_dir": doc_output_dir,
                "s3_jpg_key": s3_jpg_key,
                "s3_pdf_key": s3_pdf_key,
            }

        except Exception as e:
            logging.error(f"Error uploading or preparing {filename}: {e}")

    # --- Process Textract results for batch ---
    for base_name, job_info in jobs.items():
        job_id = job_info["job_id"]
        doc_output_dir = job_info["doc_output_dir"]
        s3_jpg_key = job_info["s3_jpg_key"]
        s3_pdf_key = job_info["s3_pdf_key"]

        logging.info(f"Waiting on Textract for: {base_name}.pdf")

        if wait_for_completion(job_id):
            extract_and_save_text_and_coords(job_id, base_name, doc_output_dir)
            logging.info(f"Textract complete: {base_name}")

            raw_path = os.path.join(doc_output_dir, base_name + ".raw.txt")
            with open(raw_path, "r", encoding="utf-8") as f:
                raw_text = f.read()

            corrected_path = correct_text_with_chatgpt(raw_text, base_name, doc_output_dir)

            if corrected_path and os.path.exists(corrected_path):
                with open(corrected_path, "r", encoding="utf-8") as cf:
                    corrected_text = cf.read()
                extract_entities_with_chatgpt(corrected_text, base_name, doc_output_dir)
            else:
                logging.warning(f"Corrected text not found for {base_name}, using raw text.")
                extract_entities_with_chatgpt(raw_text, base_name, doc_output_dir)

            # Mark these keys as successfully processed
            successfully_processed_jpgs.append(s3_jpg_key)
            successfully_processed_pdfs.append(s3_pdf_key)

    # --- Cleanup temp files and S3 objects ---
    clean_tmp_folder()

    if successfully_processed_jpgs:
        delete_files_from_s3(successfully_processed_jpgs)
        logging.info(f"Deleted {len(successfully_processed_jpgs)} JPGs from S3.")

    if successfully_processed_pdfs:
        delete_files_from_s3(successfully_processed_pdfs)
        logging.info(f"Deleted {len(successfully_processed_pdfs)} PDFs from S3.")

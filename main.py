from utils.aws_utils import *
from utils.helpers import *
from utils.chatgpt_utils import *

import boto3 # AWS SDK for Python
import os # File and path handling
import logging # Logging setup
import shutil # For copying files
from dotenv import load_dotenv # Load environment variables

load_dotenv()
bucket_name = os.environ.get("BUCKET_NAME")
tmp_dir = os.environ.get("TMP_DIR")
input_dir = os.environ.get("INPUT_DIR")
output_dir = os.environ.get("OUTPUT_DIR")
region = os.environ.get("REGION")
batch_size = int(os.environ.get("BATCH_SIZE", 10))  # Default to 10

# --- Setup logging to file and console ---
log_path = initialize_logging()
logging.info("Textract processing pipeline started.")

# --- Ensure required directories exist ---
os.makedirs(tmp_dir, exist_ok=True) # Temp dir for intermediate files
os.makedirs(output_dir, exist_ok=True) # Output dir for results

# --- Initialize AWS S3 client ---
s3 = boto3.client('s3', region_name=region) # Auth via credentials in ~/.aws

# --- Initialize trackers ---
uploaded_from_input = [] # Tracks input JPGs uploaded to S3 input_dir
uploaded_temp_pdfs = [] # Tracks PDFs uploaded to S3 for Textract

# --- Upload images to S3 if INPUT_DIR is set ---
if input_dir and os.path.isdir(input_dir):
    logging.info(f"Uploading images from input directory: {input_dir}")
    uploaded_from_input = upload_files_to_s3(input_dir)

# --- Gather all JPGs in the S3 bucket ---
all_jpg_keys = list_s3_jpg_files()  # Returns all .jpg/.jpeg keys in the bucket
batches = list(split_into_batches(all_jpg_keys, batch_size)) # Break into batches

# --- Process each batch of images ---
for batch_index, current_batch in enumerate(batches):
    logging.info(f"Processing batch {batch_index + 1} of {len(batches)}")

    jobs = {}                                  # Tracks active Textract jobs: base_name --> (job_id, output_dir)
    successfully_processed_jpgs = []           # S3 keys for .jpgs that completed successfully
    successfully_processed_pdfs = []           # S3 keys for PDFs that completed successfully

    # --- Convert JPGs to PDFs and start Textract jobs ---
    for jpg_key in current_batch:
        filename = os.path.basename(jpg_key)                    # e.g., image1.jpg
        base_name = os.path.splitext(filename)[0]               # e.g., image1
        local_jpg = os.path.join(tmp_dir, filename)             # Path to save JPG locally
        local_pdf = os.path.join(tmp_dir, base_name + ".pdf")   # Converted PDF path 
        s3_pdf_key = base_name + ".pdf"                         # PDF key for S3

        doc_output_dir = os.path.join(output_dir, base_name)    # Directory for Textract results
        os.makedirs(doc_output_dir, exist_ok=True)

        try:
            # Download JPG from S3
            logging.info(f"Downloading: {jpg_key}")
            s3.download_file(bucket_name, jpg_key, local_jpg)

            # Convert to PDF
            logging.info(f"Converting to PDF...")
            convert_jpg_to_pdf(local_jpg, local_pdf)

            # Upload PDF to S3 for Textract
            logging.info(f"Uploading PDF to S3: {s3_pdf_key}")
            s3.upload_file(local_pdf, bucket_name, s3_pdf_key)
            uploaded_temp_pdfs.append(s3_pdf_key)

            # Save a local copy of the PDF
            shutil.copy(local_pdf, os.path.join(doc_output_dir, base_name + ".pdf"))

            # Start Textract job and store job info
            job_id = start_textract_job(s3_pdf_key)
            jobs[base_name] = (job_id, doc_output_dir)

        except Exception as e:
            logging.error(f"Error processing {filename}: {e}")

    # --- Poll and collect Textract results for this batch ---
    for base_name, (job_id, doc_output_dir) in jobs.items():
        logging.info(f"Waiting on Textract for: {base_name}.pdf")
        
        if wait_for_completion(job_id): # Block until job finishes or fails
            extract_and_save_text_and_coords(job_id, base_name, doc_output_dir)
            logging.info(f"Done with: {base_name}.pdf")

            # Read raw OCR text
            with open(os.path.join(doc_output_dir, base_name + ".raw.txt"), 'r', encoding='utf-8') as f:
                raw_text = f.read()

            # Send raw text to ChatGPT for cleanup
            corrected_path = correct_text_with_chatgpt(raw_text, base_name, doc_output_dir)

            # Send cleaned-up text to ChatGPT for entity extraction
            if corrected_path and os.path.exists(corrected_path):
                with open(corrected_path, 'r', encoding='utf-8') as cf:
                    corrected_text = cf.read()
                extract_entities_with_chatgpt(corrected_text, base_name, doc_output_dir)
            else:
                logging.warning(f"Could not find corrected text for {base_name}, extracting entities from raw text instead.")
                extract_entities_with_chatgpt(raw_text, base_name, doc_output_dir)

            # Mark JPGs and PDFs as successfully processed
            for ext in [".jpg", ".jpeg"]:
                temp_key = base_name + ext
                if temp_key in current_batch:
                    successfully_processed_jpgs.append(temp_key)
            successfully_processed_pdfs.append(base_name + ".pdf")

    clean_tmp_folder()

    # Delete only successfully processed files from S3
    if successfully_processed_jpgs:
        delete_files_from_s3(successfully_processed_jpgs)
        logging.info(f"Deleted {len(successfully_processed_jpgs)} JPGs from S3 after batch {batch_index + 1}.")

    if successfully_processed_pdfs:
        delete_files_from_s3(successfully_processed_pdfs)
        logging.info(f"Deleted {len(successfully_processed_pdfs)} PDFs from S3 after batch {batch_index + 1}.")

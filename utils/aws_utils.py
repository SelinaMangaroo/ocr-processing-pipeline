import os
import time
import logging
import json

def upload_file_to_s3(file_path, s3, bucket_name, s3_key):
    try:
        s3.upload_file(file_path, bucket_name, s3_key)
        logging.info(f"[UPLOAD] {os.path.basename(file_path)} → s3://{bucket_name}/{s3_key}")
    except Exception as e:
        logging.error(f"[UPLOAD ERROR] {file_path}: {e}")

def delete_all_files_in_bucket(s3, bucket_name):
    try:
        response = s3.list_objects_v2(Bucket=bucket_name)
        objects = response.get('Contents', [])
        if not objects:
            logging.info("No files to delete in S3 bucket.")
            return

        delete_keys = [{'Key': obj['Key']} for obj in objects]
        result = s3.delete_objects(Bucket=bucket_name, Delete={'Objects': delete_keys})
        total = len(result.get('Deleted', []))
        logging.info(f"Deleted {total} files from S3 bucket '{bucket_name}'.")

    except Exception as e:
        logging.error(f"Error deleting files from S3: {e}")

# --- FUNCTION: Fetch Textract results and save as .txt and .json ---
def extract_and_save_text_and_coords(job_id, base_name, doc_output_dir, textract):
    lines = []
    word_info = []

    next_token = None
    while True:
        response = textract.get_document_text_detection(JobId=job_id, NextToken=next_token) if next_token else textract.get_document_text_detection(JobId=job_id)
        
        for block in response.get('Blocks', []):
            if block['BlockType'] == 'LINE':
                lines.append(block['Text'])
            elif block['BlockType'] == 'WORD':
                word_info.append({
                    "text": block['Text'],
                    "confidence": block['Confidence'],
                    "boundingBox": block['Geometry']['BoundingBox']
                })

        next_token = response.get('NextToken')
        if not next_token:
            break

    # Save plain text
    with open(os.path.join(doc_output_dir, f"{base_name}.raw.txt"), 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    # Save word-level bounding box data
    with open(os.path.join(doc_output_dir, f"{base_name}.coords.json"), 'w', encoding='utf-8') as jf:
        json.dump(word_info, jf, indent=2)

    logging.info(f"Saved text and coordinates for {base_name}")

def start_textract_job(s3_pdf_key, textract, bucket_name):
    try:
        response = textract.start_document_text_detection(
            DocumentLocation={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': s3_pdf_key
                }
            }
        )
        logging.info(f"Started Textract job for {s3_pdf_key} (JobId: {response['JobId']})")
        return response['JobId']
    except Exception as e:
        logging.error(f"Failed to start Textract job for {s3_pdf_key}: {e}")
        raise

def wait_for_completion(job_id, textract, max_retries=30, delay=3):
    for _ in range(max_retries):
        result = textract.get_document_text_detection(JobId=job_id)
        status = result['JobStatus']
        if status == 'SUCCEEDED':
            return True
        elif status == 'FAILED':
            logging.error(f"Textract job failed: {result.get('StatusMessage')}")
            return False
        time.sleep(delay)
    logging.error(f"Textract job {job_id} timed out.")
    return False

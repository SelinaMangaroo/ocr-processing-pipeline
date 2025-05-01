import boto3
import os
import time
import logging
import json
from dotenv import load_dotenv

load_dotenv()
region = os.environ.get("REGION")
bucket_name = os.environ.get("BUCKET_NAME")

s3 = boto3.client('s3', region_name=region) # Create S3 client
textract = boto3.client('textract', region_name=region) # Create Textract client for OCR processing

# --- FUNCTION: Uploads all .jpg or .jpeg files from a local directory to the configured S3 bucket.
# Returns a list of successfully uploaded S3 object keys.
def upload_files_to_s3(dir):
    uploaded_keys = []
    for fname in os.listdir(dir):  # Loop through files in the directory
        if fname.lower().endswith(('.jpg', '.jpeg')):  # Only process image files
            path = os.path.join(dir, fname)  # Full path
            s3_key = fname  # S3 object key (same as filename)
            try:
                s3.upload_file(path, bucket_name, s3_key)  # Upload to S3
                logging.info(f"Uploaded {fname} to S3 as {s3_key}")
                uploaded_keys.append(s3_key)   # Track uploaded files
            except Exception as e:
                logging.error(f"Failed to upload {fname} to S3: {e}")
    return uploaded_keys  # Return list of successfully uploaded S3 keys

# --- FUNCTION: Deletes a list of object keys from the configured S3 bucket.
def delete_files_from_s3(s3_keys):
    for key in s3_keys:
        try:
            s3.delete_object(Bucket=bucket_name, Key=key)
            logging.info(f"Deleted {key} from S3 after processing.")
        except Exception as e:
            logging.error(f"Failed to delete {key} from S3: {e}")

# --- FUNCTION: Lists all .jpg and .jpeg files in the root of the configured S3 bucket.
# Handles pagination if the number of files exceeds the S3 response limit.
# Returns a list of S3 keys.
def list_s3_jpg_files():
    keys = []
    continuation_token = None # Used for paginating through large buckets

    while True:
        if continuation_token:
            response = s3.list_objects_v2(Bucket=bucket_name, ContinuationToken=continuation_token)
        else:
            response = s3.list_objects_v2(Bucket=bucket_name)

        # Add valid image keys to the list
        keys.extend(
            obj['Key'] for obj in response.get('Contents', []) 
            if obj['Key'].lower().endswith(('.jpg', '.jpeg'))
        )

        if response.get('IsTruncated'):  # Check if there are more results
            continuation_token = response['NextContinuationToken']
        else:
            break

    return keys

# --- FUNCTION: Fetch Textract results and save as .txt and .json ---
def extract_and_save_text_and_coords(job_id, base_name, doc_output_dir):
    pages = []
    
   # Fetch initial page of results
    response = textract.get_document_text_detection(JobId=job_id)
    pages.append(response)

    # Fetch all paginated results if present
    # Textract responses are paginated, so large documents are returned in chunks.
    # You make an initial request using the JobId
    # If the response includes a "NextToken", there are more results to get
    # This loop ensures you collect all result pages, not just the first
    while response.get('NextToken'):
        response = textract.get_document_text_detection(JobId=job_id, NextToken=response['NextToken'])
        pages.append(response)
        
    lines = [] # Stores text line-by-line for .txt output
    word_info = [] # Stores word-level bounding boxes for .json output

    # Parse each block in each page
    # Every Textract response contains a list of "Blocks"
    # A Block is one detected element — like a LINE, WORD, TABLE, etc.
    for page in pages:
        for block in page['Blocks']:
            if block['BlockType'] == 'LINE':
                lines.append(block['Text'])  # Collect lines for .txt
                # Each LINE represents a full line of text Textract detected, saved in reading order into the lines list
                # Later used to generate a .txt file that resembles what a person would read
            elif block['BlockType'] == 'WORD':
                word_info.append({
                    "text": block['Text'],
                    "confidence": block['Confidence'],
                    "boundingBox": block['Geometry']['BoundingBox']
                })
                # Each WORD block contains: The text of the word, A confidence score (0–100), A bounding box with Top, Left, Width, and Height values
                # These values are ratios (0 to 1) relative to the full page size

    # Save plain text output
    with open(os.path.join(doc_output_dir, base_name + ".raw.txt"), 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    # Save JSON with word-level coordinates
    with open(os.path.join(doc_output_dir, base_name + ".coords.json"), 'w', encoding='utf-8') as jf:
        json.dump(word_info, jf, indent=2)

    logging.info(f"Saved text and coordinates for {base_name}")
    

# --- FUNCTION: Start an asynchronous Textract job on a PDF stored in S3 ---
def start_textract_job(s3_pdf_key):
    response = textract.start_document_text_detection(
        DocumentLocation={'S3Object': {'Bucket': bucket_name, 'Name': s3_pdf_key}}
    )
    return response['JobId'] # Return the unique job ID

# --- FUNCTION: Wait until a Textract job completes or fails ---
# Textract async jobs are not instant, this function ensures you don’t try to read results before the job is ready
# Prevents premature access or errors
def wait_for_completion(job_id):
    while True:
        result = textract.get_document_text_detection(JobId=job_id)
        status = result['JobStatus']
        if status == 'SUCCEEDED':
            return True
        elif status == 'FAILED':
            logging.error(f"Textract job failed: {result.get('StatusMessage')}")
            return False
        time.sleep(5) # Wait 5 seconds before checking again

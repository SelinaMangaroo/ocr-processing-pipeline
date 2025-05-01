# OCR Processing Pipeline

This project is a batch OCR (Optical Character Recognition) pipeline that uses **AWS Textract** and **OpenAI's ChatGPT** to process scanned .jpg images. It extracts raw text, corrects OCR errors, and structures key entities (e.g. people, companies, dates) from historical documents such as theater letters.

---

## Features

- Converts .jpg images to .pdf using ImageMagick
- Runs asynchronous AWS Textract OCR jobs
- Uses OpenAI's GPT to:
  - Correct OCR errors
  - Extract entities
- Handles file uploads to S3 bucket
- Supports batching with configurable size
- Deletes processed files from S3 after batch completion
- Logs all operations to timestamped log files

---

## Project Structure

```
ocr-processing-pipeline/
├── utils/                        # Utility modules 
│   ├── aws_utils.py              # AWS Textract, S3, and OCR logic
│   ├── chatgpt_utils.py          # GPT-based text correction and entity extraction
│   ├── helpers.py                # PDF conversion, logging, etc.
├── logs/                         # Runtime logs
├── output/                       # Output text, JSON, corrected results
├── venv/                         # Virtual environment (not tracked in version control)
├── main.py                       # Entry point for the pipeline     
├── .gitignore                    # Specifies files/directories to exclude from Git
├── README.md                     # Project documentation
├── requirements.txt              # List of dependencies
```


---

## Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/ocr-processing-pipeline.git
cd ocr-processing-pipeline
```

2. Create a virtual environment and install dependencies:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
**ImageMagick** must be installed system-wide, it's not a Python package.

```
brew install imagemagick
```

1. Set up your .env file with the following keys:

```
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
BUCKET_NAME=your_s3_bucket_name
REGION=us-east-1
TMP_DIR=./tmp
INPUT_DIR=./input
OUTPUT_DIR=./output
BATCH_SIZE=10
```

4. Run the pipeline:
```
python main.py
```
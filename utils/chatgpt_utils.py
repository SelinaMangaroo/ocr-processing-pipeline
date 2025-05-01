import os
import logging
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")  # fallback default

client = OpenAI(api_key=api_key)

# --- FUNCTION: Sends raw OCR text to ChatGPT for spelling and punctuation correction,
# and saves the corrected text to a `.corrected.txt` file in the output folder.
# The AI is instructed not to add or infer any extra content.

def correct_text_with_chatgpt(text, base_name, doc_output_dir):
    try:
        logging.info(f"Sending text to ChatGPT for correction: {base_name}")

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that only corrects spelling, OCR mistakes, and punctuation errors in text. "
                        "Do not add or infer any additional content. Keep the original meaning intact. If the text already seems correct, leave it as is, and if you are unsure, leave it as is. "
                    )
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.0
        )

        corrected_text = response.choices[0].message.content.strip()

        corrected_path = os.path.join(doc_output_dir, base_name + ".corrected.txt")
        with open(corrected_path, 'w', encoding='utf-8') as f:
            f.write(corrected_text)

        logging.info(f"Corrected text saved: {corrected_path}")
        return corrected_path

    except Exception as e:
        logging.error(f"Failed to correct text for {base_name}: {e}")
        return None
    
# --- FUNCTION: Sends text to ChatGPT and asks it to extract structured entities (People, Productions,
# Companies, Theaters, Dates). Saves the result as a JSON file.
# Falls back to saving raw text if the output is not valid JSON.
def extract_entities_with_chatgpt(text, base_name, doc_output_dir):
    try:
        logging.info(f"Extracting entities with ChatGPT for: {base_name}")

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that extracts structured data from OCR-scanned historical letters. "
                        "Return your answer as a **valid JSON object**, with the following keys: "
                        "`People`, `Productions`, `Companies`, `Theaters`, and `Dates`. "
                        "Each value should be a list of strings. If no items are found for a category, return an empty list. "
                        "Do not include any explanation or formatting — only the JSON object."
                    )
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.2
        )

        entity_data = response.choices[0].message.content.strip()
        
        # Try to parse as JSON to ensure validity
        try:
            parsed = json.loads(entity_data)
            # Save the parsed, pretty-printed JSON
            entity_path = os.path.join(doc_output_dir, base_name + ".entities.json")
            with open(entity_path, 'w', encoding='utf-8') as f:
                json.dump(parsed, f, indent=2)
            logging.info(f"Entity extraction saved: {entity_path}")
            return entity_path
        except json.JSONDecodeError:
            # Save raw output for debugging
            error_path = os.path.join(doc_output_dir, base_name + ".entities_raw.txt")
            with open(error_path, 'w', encoding='utf-8') as f:
                f.write(entity_data)
            logging.warning(f"Entity extraction result was not valid JSON. Raw output saved: {error_path}")
            return None

    except Exception as e:
        logging.error(f"Failed to extract entities for {base_name}: {e}")
        return None

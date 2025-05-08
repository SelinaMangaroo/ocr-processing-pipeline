import os
import logging
import json

def correct_text_with_chatgpt(text, base_name, doc_output_dir, client, model_name):
    """
    Sends OCR text to ChatGPT for basic correction, then saves it to a .corrected.txt file.

    Args:
        text (str): Raw OCR output.
        base_name (str): Base filename.
        doc_output_dir (str): Directory to save the corrected file.
        client (OpenAI): Pre-initialized OpenAI client.
        model_name (str): Model name (e.g. "gpt-4o-mini").

    Returns:
        str or None: Path to corrected file or None on failure.
    """
    try:
        logging.info(f"Correcting OCR text for: {base_name}")
        
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
        logging.error(f"ChatGPT correction failed for {base_name}: {e}")
        return None

def extract_entities_with_chatgpt(text, base_name, doc_output_dir, client, model_name):
    """
    Sends OCR text to ChatGPT and extracts named entities as JSON. 
    Falls back to saving raw output if JSON decoding fails.

    Args:
        text (str): OCR text to analyze.
        base_name (str): File name without extension.
        doc_output_dir (str): Path to store results.
        client (OpenAI): Pre-initialized OpenAI client.
        model_name (str): ChatGPT model (e.g., gpt-4o-mini).

    Returns:
        str or None: Path to saved JSON (or None if extraction failed).
    """
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

        result = response.choices[0].message.content.strip()

        # Attempt to parse valid JSON
        try:
            parsed = json.loads(result)
            entity_path = os.path.join(doc_output_dir, base_name + ".entities.json")
            with open(entity_path, 'w', encoding='utf-8') as f:
                json.dump(parsed, f, indent=2)
            logging.info(f"Entity extraction saved: {entity_path}")
            return entity_path
        except json.JSONDecodeError:
            raw_path = os.path.join(doc_output_dir, base_name + ".entities_raw.txt")
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(result)
            logging.warning(f"Invalid JSON for {base_name}. Raw output saved: {raw_path}")
            return None

    except Exception as e:
        logging.error(f"Entity extraction failed for {base_name}: {e}")
        return None

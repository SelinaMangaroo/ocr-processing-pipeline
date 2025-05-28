import os
import logging
import json
import re

def correct_text_with_chatgpt(text, base_name, doc_output_dir, client, model_name, save=True):
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
        # corrected_path = os.path.join(doc_output_dir, base_name + ".corrected.txt")

        # with open(corrected_path, 'w', encoding='utf-8') as f:
        #     f.write(corrected_text)

        # logging.info(f"Corrected text saved: {corrected_path}")
        # return corrected_path
        
        if save:
            corrected_path = os.path.join(doc_output_dir, base_name + ".corrected.txt")
            with open(corrected_path, 'w', encoding='utf-8') as f:
                f.write(corrected_text)
            logging.info(f"Corrected text saved: {corrected_path}")
            return corrected_path
        else:
            return corrected_text
        

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


def extract_page_and_split_letters(corrected_text_path, client, model_name):
    """
    Extracts the page number from the first line of corrected text,
    and uses ChatGPT to determine and split multiple letters if they exist.

    Args:
        corrected_text_path (str): Path to the corrected text file.
        client: OpenAI client.
        model_name (str): ChatGPT model .

    Returns:
        dict: {
            "page_number": int or None,
            "letters": [str, ...]  # list of one or more letters
        }
    """
    try:
        with open(corrected_text_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            return {"page_number": None, "letters": []}

        first_line = lines[0].strip()
        full_text = ''.join(lines)

        # Extract page number from the first line
        try:
            page_number = int(first_line.strip())
        except ValueError:
            page_number = None

        # Prompt to detect/split multiple letters
        prompt = (
            "The following is OCR-corrected text from scanned historical documents. "
            "Please detect if there are **multiple letters** present. Each letter typically starts with a recipient block (e.g. a name and address) followed by a greeting."
            "(e.g., 'Dear', 'Friend', 'Dear Sir:' or 'Gentlemen:' and etc.), or a name and date line, and ends with a sign-off like 'Sincerely yours' or 'Yours truly' or 'Yours sincerely,' etc."
            "Split the text into a **JSON array of full letters** — one string per letter. Return the full content of each letter, "
            "including greetings and sign-offs. If it’s just one letter, return a list with one string."
            "IMPORTANT: Only return a JSON list — do NOT include any explanation or notes. Do not add any additional content, do not alter the text."
            f"Text:\n{full_text}"
        )

        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        result = response.choices[0].message.content.strip()

        # Try to parse the list from GPT response
        try:
            letters = json.loads(result)
            if not isinstance(letters, list):
                letters = [full_text]
        except json.JSONDecodeError:
            letters = [full_text]

        return {
            "page_number": page_number,
            "letters": letters
        }

    except Exception as e:
        logging.error(f"Failed to extract page and split letters for {corrected_text_path}: {e}")
        return {"page_number": None, "letters": []}

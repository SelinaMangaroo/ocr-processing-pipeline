import os
import pytest

# This decorator tells pytest to run the test multiple times, once for each value of base_name.
@pytest.mark.parametrize("base_name", [
    name for name in os.listdir("bucket_output")
    if os.path.isdir(os.path.join("bucket_output", name))
])

# Accepts a 10% difference by default.
def test_word_count_consistency(base_name, output_dir="bucket_output", tolerance=0.10):
    """
    Test that the word count of the raw and corrected text files are consistent.
    The difference in word count should not exceed a specified tolerance.
    """
    
    # Paths to the raw and corrected text files
    raw_path = os.path.join(output_dir, base_name, f"{base_name}.raw.txt")
    corrected_path = os.path.join(output_dir, base_name, f"{base_name}.corrected.txt")
    
    # Check if the files exist
    assert os.path.exists(raw_path), f"Missing raw file: {raw_path}"
    assert os.path.exists(corrected_path), f"Missing corrected file: {corrected_path}"

    # Read the contents of the files
    with open(raw_path, 'r', encoding='utf-8') as rf:
        raw_text = rf.read()
    with open(corrected_path, 'r', encoding='utf-8') as cf:
        corrected_text = cf.read()

    # Calculate word counts
    raw_words = len(raw_text.split())
    corrected_words = len(corrected_text.split())
    
    # Calculate the difference and allowed tolerance
    delta = abs(raw_words - corrected_words) #Absolute difference in word count.
    allowed = max(1, int(raw_words * tolerance))  # Never allow 0-word diff

    # Assert that the difference is within the allowed tolerance. If the word count delta is too high, the test fails.
    assert delta <= allowed, (
        f"[{base_name}] Word count delta too high: raw={raw_words}, corrected={corrected_words}, allowed={allowed}"
    )

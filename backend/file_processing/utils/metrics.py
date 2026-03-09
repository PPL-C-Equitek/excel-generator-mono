from difflib import SequenceMatcher

def calculate_accuracy(ground_truth: str, extracted: str) -> float:
    """
    Calculates the accuracy (similarity ratio) of the extracted text 
    compared to the ground truth string using SequenceMatcher.
    """
    if not ground_truth and not extracted:
        return 1.0
    matcher = SequenceMatcher(None, ground_truth, extracted)
    return matcher.ratio()


import os
import re
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import docx
import spacy
from spacy.pipeline import EntityRuler

# ------------------ CONFIG & NLP SETUP ------------------
RESUME_FOLDER = "resumes"

# Load spaCy and add the EntityRuler
nlp = spacy.load("en_core_web_sm")
ruler = nlp.add_pipe("entity_ruler", before="ner")

# Define smart patterns: (Label, Pattern)
# This handles variations like "ML" for "Machine Learning"
patterns = [
    {"label": "PYTHON", "pattern": [{"LOWER": "python"}]},
    {"label": "PYTHON", "pattern": [{"LOWER": "python3"}]},
    {"label": "SQL", "pattern": [{"LOWER": "sql"}]},
    {"label": "SQL", "pattern": [{"LOWER": "postgresql"}]},
    {"label": "MACHINE_LEARNING", "pattern": [{"LOWER": "machine"}, {"LOWER": "learning"}]},
    {"label": "MACHINE_LEARNING", "pattern": [{"LOWER": "ml"}]},
    {"label": "DATA_ANALYSIS", "pattern": [{"LOWER": "data"}, {"LOWER": "analysis"}]},
    {"label": "DATA_ANALYSIS", "pattern": [{"LOWER": "data"}, {"LOWER": "analytics"}]},
]
ruler.add_patterns(patterns)

# ------------------ TEXT EXTRACTION ------------------

def extract_text_from_pdf(file_path):
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"Error reading PDF {file_path}: {e}")
    return text

def extract_text_from_docx(file_path):
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_scanned_pdf(file_path):
    text = ""
    # Note: Requires poppler and tesseract installed on the OS
    pages = convert_from_path(file_path)
    for page in pages:
        text += pytesseract.image_to_string(page) + "\n"
    return text

# ------------------ NLP SKILL EXTRACTION ------------------

def get_skills_with_nlp(text):
    """Uses spaCy to find entities defined in our patterns"""
    doc = nlp(text)
    # Use a set to avoid counting the same skill twice (e.g., Python and Python3)
    skills_found = set()
    for ent in doc.ents:
        if ent.label_ in ["PYTHON", "SQL", "MACHINE_LEARNING", "DATA_ANALYSIS"]:
            skills_found.add(ent.label_)
    return list(skills_found)

# ------------------ PROCESS ------------------

def process_resume(file_path):
    ext = file_path.lower().split('.')[-1]
    text = ""

    if ext == "pdf":
        text = extract_text_from_pdf(file_path)
        if len(text.strip()) < 50:
            text = extract_text_from_scanned_pdf(file_path)
    elif ext == "docx":
        text = extract_text_from_docx(file_path)
    elif ext in ["jpg", "jpeg", "png"]:
        text = pytesseract.image_to_string(Image.open(file_path))
    
    if not text:
        return 0, []

    skills = get_skills_with_nlp(text)
    return len(skills), skills

def main():
    if not os.path.exists(RESUME_FOLDER):
        os.makedirs(RESUME_FOLDER)
        print(f"Created '{RESUME_FOLDER}' folder. Add resumes and run again.")
        return

    results = []
    for filename in os.listdir(RESUME_FOLDER):
        path = os.path.join(RESUME_FOLDER, filename)
        score, skills = process_resume(path)
        results.append({"name": filename, "score": score, "skills": skills})

    # Sort by score
    sorted_resumes = sorted(results, key=lambda x: x['score'], reverse=True)

    print(f"\n{'FILENAME':<25} | {'SCORE':<5} | {'SKILLS FOUND'}")
    print("-" * 60)
    for r in sorted_resumes:
        print(f"{r['name']:<25} | {r['score']:<5} | {', '.join(r['skills'])}")

if __name__ == "__main__":
    main()
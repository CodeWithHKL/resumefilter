import os
import re
import pdfplumber
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import docx
import spacy

# ------------------ CONFIG ------------------
# List of skills to filter resumes
REQUIRED_SKILLS = ["python", "sql", "machine learning", "data analysis"]

# Folder containing resumes
RESUME_FOLDER = "resumes"

# Load spaCy English model
nlp = spacy.load("en_core_web_sm")

# ------------------ TEXT EXTRACTION ------------------

def extract_text_from_pdf(file_path):
    """Extract text from a normal PDF"""
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except:
        pass
    return text

def extract_text_from_docx(file_path):
    """Extract text from a DOCX file"""
    doc = docx.Document(file_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text

def extract_text_from_image(file_path):
    """Extract text from image using Tesseract OCR"""
    image = Image.open(file_path)
    return pytesseract.image_to_string(image)

def extract_text_from_scanned_pdf(file_path):
    """Convert PDF pages to images and run OCR on each page"""
    text = ""
    pages = convert_from_path(file_path)
    for page in pages:
        text += pytesseract.image_to_string(page) + "\n"
    return text

# ------------------ TEXT CLEANING ------------------

def clean_text(text):
    """Lowercase, remove punctuation, extra spaces"""
    text = text.lower()
    text = re.sub(r'\n', ' ', text)
    text = re.sub(r'[^a-z0-9 ]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

# ------------------ NLP / SKILL EXTRACTION ------------------

def extract_skills(text):
    """Return list of skills found in resume text"""
    text = clean_text(text)
    skills_found = [skill for skill in REQUIRED_SKILLS if skill in text]
    return skills_found

# ------------------ PROCESS RESUME ------------------

def process_resume(file_path):
    ext = file_path.lower().split('.')[-1]
    
    if ext == "pdf":
        text = extract_text_from_pdf(file_path)
        # If almost no text, assume scanned PDF and OCR it
        if len(text.strip()) < 50:
            text = extract_text_from_scanned_pdf(file_path)
    elif ext == "docx":
        text = extract_text_from_docx(file_path)
    elif ext in ["jpg", "jpeg", "png"]:
        text = extract_text_from_image(file_path)
    else:
        print(f"Unsupported file type: {file_path}")
        return None, None

    skills = extract_skills(text)
    score = len(skills)
    return score, skills

# ------------------ FILTER / RANK RESUMES ------------------

def filter_resumes(folder_path):
    results = []
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        score, skills = process_resume(file_path)
        if score is not None:
            results.append((filename, score, skills))
    
    # Sort by number of skills matched (descending)
    results.sort(key=lambda x: x[1], reverse=True)
    return results

# ------------------ MAIN ------------------

if __name__ == "__main__":
    if not os.path.exists(RESUME_FOLDER):
        print(f"Folder '{RESUME_FOLDER}' not found. Create it and put resumes inside.")
    else:
        print("Processing resumes...")
        ranked_resumes = filter_resumes(RESUME_FOLDER)
        print("\n--- Ranked Resumes ---")
        for fname, score, skills in ranked_resumes:
            print(f"{fname}: {score} skills matched -> {skills}")
import os
import spacy
import pdfplumber
import docx
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from spacy.pipeline import EntityRuler

# ------------------ NLP DYNAMIC SETUP ------------------

def setup_nlp_with_keywords(keywords_list):
    """Dynamically creates a spaCy model with the user's keywords."""
    nlp = spacy.load("en_core_web_sm")
    # Using 'entity_ruler' to add custom matching logic
    if "entity_ruler" not in nlp.pipe_names:
        ruler = nlp.add_pipe("entity_ruler", before="ner")
    else:
        ruler = nlp.get_pipe("entity_ruler")

    patterns = []
    for skill in keywords_list:
        clean_skill = skill.strip().lower()
        # We create a pattern that matches the skill regardless of case
        patterns.append({"label": "SKILL", "pattern": [{"LOWER": clean_skill}]})
    
    ruler.add_patterns(patterns)
    return nlp

# ------------------ EXTRACTION FUNCTIONS ------------------

def extract_text(file_path):
    ext = file_path.lower().split('.')[-1]
    text = ""
    
    try:
        if ext == "pdf":
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            # Fallback for scanned PDFs
            if len(text.strip()) < 50:
                pages = convert_from_path(file_path)
                text = "\n".join([pytesseract.image_to_string(p) for p in pages])
        elif ext == "docx":
            doc = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs])
        elif ext in ["jpg", "jpeg", "png"]:
            text = pytesseract.image_to_string(Image.open(file_path))
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        
    return text

# ------------------ MAIN INTERACTIVE LOOP ------------------

def main():
    folder = "resumes"
    if not os.path.exists(folder):
        os.makedirs(folder)
        print(f"Folder '{folder}' created. Please add files and restart.")
        return

    # 1. Get User Input
    print("--- Dynamic Resume Ranker ---")
    user_input = input("Enter the skills you want to search for (separated by commas): ")
    target_skills = [s.strip().lower() for s in user_input.split(",") if s.strip()]
    
    if not target_skills:
        print("No skills entered. Exiting.")
        return

    # 2. Setup NLP
    print(f"Initializing AI with skills: {target_skills}...")
    nlp = setup_nlp_with_keywords(target_skills)

    # 3. Process Files
    results = []
    files = [f for f in os.listdir(folder) if f.split('.')[-1] in ['pdf', 'docx', 'jpg', 'png']]
    
    if not files:
        print("No supported resumes found in the folder.")
        return

    for filename in files:
        print(f"Scanning {filename}...")
        path = os.path.join(folder, filename)
        raw_text = extract_text(path)
        
        # Run NLP Analysis
        doc = nlp(raw_text)
        found_skills = list(set([ent.text.lower() for ent in doc.ents if ent.label_ == "SKILL"]))
        
        score = len(found_skills)
        results.append((filename, score, found_skills))

    # 4. Display Results
    results.sort(key=lambda x: x[1], reverse=True)
    
    print("\n" + "="*50)
    print(f"{'CANDIDATE':<25} | {'SCORE':<5} | {'MATCHED SKILLS'}")
    print("-" * 50)
    for name, score, matches in results:
        print(f"{name[:25]:<25} | {score:<5} | {', '.join(matches)}")

if __name__ == "__main__":
    main()
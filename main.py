import io
import os
import spacy
import pdfplumber
import docx
import pytesseract
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pdf2image import convert_from_bytes
from PIL import Image
from typing import List

app = FastAPI(title="AI Resume Parser API")

# Load base spaCy model once on startup
base_nlp = spacy.load("en_core_web_sm")

# ------------------ HELPERS ------------------

def extract_text_from_bytes(file_bytes, filename):
    ext = filename.lower().split('.')[-1]
    text = ""
    
    try:
        if ext == "pdf":
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            
            # OCR Fallback
            if len(text.strip()) < 50:
                pages = convert_from_bytes(file_bytes)
                text = "\n".join([pytesseract.image_to_string(p) for p in pages])
                
        elif ext == "docx":
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([p.text for p in doc.paragraphs])
            
        elif ext in ["jpg", "jpeg", "png"]:
            text = pytesseract.image_to_string(Image.open(io.BytesIO(file_bytes)))
            
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        
    return text

# ------------------ API ENDPOINTS ------------------

@app.post("/rank-resumes")
async def rank_resumes(
    skills: str = Form(...), 
    files: List[UploadFile] = File(...)
):
    """
    Accepts a comma-separated string of skills and a list of files.
    Returns a ranked JSON list of candidates.
    """
    # 1. Prepare the Dynamic NLP Model
    target_skills = [s.strip().lower() for s in skills.split(",") if s.strip()]
    if not target_skills:
        raise HTTPException(status_code=400, detail="No skills provided")

    # Create a local copy of the model for this request's specific keywords
    # Using a fresh EntityRuler for each request to keep it dynamic
    nlp = spacy.load("en_core_web_sm")
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    
    patterns = [{"label": "SKILL", "pattern": [{"LOWER": s}]} for s in target_skills]
    ruler.add_patterns(patterns)

    # 2. Process each file
    results = []
    for file in files:
        content = await file.read()
        raw_text = extract_text_from_bytes(content, file.filename)
        
        doc = nlp(raw_text)
        found_matches = list(set([ent.text.lower() for ent in doc.ents if ent.label_ == "SKILL"]))
        
        results.append({
            "filename": file.filename,
            "score": len(found_matches),
            "matched_skills": sorted(found_matches)
        })

    # 3. Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        "requested_skills": target_skills,
        "total_files_processed": len(files),
        "rankings": results
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
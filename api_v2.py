import io
import os
import time  # New: To track time
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
            
            # OCR Fallback for scanned PDFs
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
    Accepts keywords and a list of files. 
    Calculates time per resume and total processing time.
    """
    # Start the total timer for the entire request
    overall_start_time = time.time()

    # 1. Prepare the Dynamic NLP Model
    target_skills = [s.strip().lower() for s in skills.split(",") if s.strip()]
    if not target_skills:
        raise HTTPException(status_code=400, detail="No skills provided")

    # Reuse the base model and add the ruler
    nlp = spacy.load("en_core_web_sm")
    if "entity_ruler" not in nlp.pipe_names:
        ruler = nlp.add_pipe("entity_ruler", before="ner")
    else:
        ruler = nlp.get_pipe("entity_ruler")
    
    patterns = [{"label": "SKILL", "pattern": [{"LOWER": s}]} for s in target_skills]
    ruler.add_patterns(patterns)

    # 2. Process each file
    results = []
    for file in files:
        # Start timer for THIS specific resume
        resume_start_time = time.time()
        
        content = await file.read()
        raw_text = extract_text_from_bytes(content, file.filename)
        
        doc = nlp(raw_text)
        found_matches = list(set([ent.text.lower() for ent in doc.ents if ent.label_ == "SKILL"]))
        
        # End timer for THIS specific resume
        resume_end_time = time.time()
        # Calculate duration with 3 decimal places
        duration_per_resume = round(resume_end_time - resume_start_time, 3)
        
        results.append({
            "filename": file.filename,
            "score": len(found_matches),
            "matched_skills": sorted(found_matches),
            "time_taken_sec": duration_per_resume  # New: Individual time
        })

    # 3. Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # End the total timer
    overall_end_time = time.time()
    total_time = round(overall_end_time - overall_start_time, 3)
    
    return {
        "requested_skills": target_skills,
        "total_files_processed": len(files),
        "total_processing_time_sec": total_time,  # New: Total time
        "average_time_per_resume": round(total_time / len(files), 3) if files else 0,
        "rankings": results
    }

if __name__ == "__main__":
    import uvicorn
    # host 0.0.0.0 allows other machines on your Wi-Fi to call this API
    uvicorn.run(app, host="0.0.0.0", port=8000)
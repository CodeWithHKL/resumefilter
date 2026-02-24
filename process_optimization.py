import io
import time
import spacy
import pdfplumber
import docx
import pytesseract
import asyncio
from concurrent.futures import ProcessPoolExecutor
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pdf2image import convert_from_bytes
from PIL import Image
from typing import List

app = FastAPI(title="High-Performance AI Resume Parser")

# 1. Global Executor for Multiprocessing
# This allows the API to use all available CPU cores.
executor = ProcessPoolExecutor()

# 2. Optimized Text Extraction & NLP (The "Worker" Function)
def process_single_resume(file_bytes, filename, target_skills):
    """
    This function runs in a separate process to avoid blocking the main thread.
    """
    ext = filename.lower().split('.')[-1]
    text = ""
    start_time = time.time()

    try:
        # --- Text Extraction ---
        if ext == "pdf":
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            if len(text.strip()) < 50: # OCR Fallback
                pages = convert_from_bytes(file_bytes)
                text = "\n".join([pytesseract.image_to_string(p) for p in pages])
        elif ext == "docx":
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([p.text for p in doc.paragraphs])
        elif ext in ["jpg", "jpeg", "png"]:
            text = pytesseract.image_to_string(Image.open(io.BytesIO(file_bytes)))

        # --- NLP Matching ---
        # We use a 'blank' model for speed since we only need the EntityRuler
        nlp = spacy.blank("en")
        ruler = nlp.add_pipe("entity_ruler")
        patterns = [{"label": "SKILL", "pattern": [{"LOWER": s}]} for s in target_skills]
        ruler.add_patterns(patterns)
        
        doc = nlp(text)
        found_matches = list(set([ent.text.lower() for ent in doc.ents if ent.label_ == "SKILL"]))
        
        return {
            "filename": filename,
            "score": len(found_matches),
            "matched_skills": sorted(found_matches),
            "time_taken_sec": round(time.time() - start_time, 3)
        }
    except Exception as e:
        return {"filename": filename, "error": str(e), "score": 0, "time_taken_sec": 0}

# ------------------ API ENDPOINTS ------------------

@app.post("/rank-resumes")
async def rank_resumes(
    skills: str = Form(...), 
    files: List[UploadFile] = File(...)
):
    overall_start_time = time.time()
    target_skills = [s.strip().lower() for s in skills.split(",") if s.strip()]
    
    if not target_skills:
        raise HTTPException(status_code=400, detail="No skills provided")

    # 3. Read all files into memory concurrently (Async)
    # This is much faster than reading one-by-one in a loop
    async def read_file(file: UploadFile):
        return await file.read(), file.filename

    file_data = await asyncio.gather(*[read_file(f) for f in files])

    # 4. Offload heavy CPU work to the ProcessPool (Parallel)
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(executor, process_single_resume, content, name, target_skills)
        for content, name in file_data
    ]
    
    results = await asyncio.gather(*tasks)

    # 5. Sort and Calculate Stats
    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    total_time = round(time.time() - overall_start_time, 3)
    
    return {
        "requested_skills": target_skills,
        "total_files_processed": len(files),
        "total_processing_time_sec": total_time,
        "average_time_per_resume": round(total_time / len(files), 3) if files else 0,
        "rankings": results
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
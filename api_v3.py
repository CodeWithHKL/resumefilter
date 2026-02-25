import io
import os
import time
import spacy
import pdfplumber
import docx
import pytesseract
import asyncio
import json
from concurrent.futures import ProcessPoolExecutor
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from pdf2image import convert_from_bytes
from PIL import Image
from typing import List

app = FastAPI(title="Safe Real-Time Resume Parser")

# --- 1. WORKER LIMIT ---
half_cpu = max(1, os.cpu_count() // 2)
executor = ProcessPoolExecutor(max_workers=half_cpu)

# --- 2. GLOBAL LIMITS ---
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB per file
MAX_RESUME_COUNT = 300           # Strict limit on total files per request

def process_single_resume(file_bytes, filename, target_skills):
    ext = filename.lower().split('.')[-1]
    text = ""
    start_time = time.time()

    try:
        if ext == "pdf":
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                text = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
            if len(text.strip()) < 50:
                pages = convert_from_bytes(file_bytes)
                text = "\n".join([pytesseract.image_to_string(p) for p in pages])
        elif ext == "docx":
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n".join([p.text for p in doc.paragraphs])
        elif ext in ["jpg", "jpeg", "png"]:
            text = pytesseract.image_to_string(Image.open(io.BytesIO(file_bytes)))

        nlp = spacy.blank("en")
        ruler = nlp.add_pipe("entity_ruler")
        patterns = [{"label": "SKILL", "pattern": [{"LOWER": s}]} for s in target_skills]
        ruler.add_patterns(patterns)
        
        doc = nlp(text)
        found_matches = list(set([ent.text.lower() for ent in doc.ents if ent.label_ == "SKILL"]))
        
        return {
            "status": "success",
            "filename": filename,
            "score": len(found_matches),
            "matched_skills": sorted(found_matches),
            "time_taken_sec": round(time.time() - start_time, 3)
        }
    except Exception as e:
        return {"status": "error", "filename": filename, "error": str(e)}

@app.post("/rank-resumes")
async def rank_resumes(
    skills: str = Form(...), 
    files: List[UploadFile] = File(...)
):
    # A. Check total file count before anything else
    if len(files) > MAX_RESUME_COUNT:
        raise HTTPException(
            status_code=400, 
            detail=f"Too many files! Maximum allowed is {MAX_RESUME_COUNT}, but you sent {len(files)}."
        )

    target_skills = [s.strip().lower() for s in skills.split(",") if s.strip()]
    if not target_skills:
        raise HTTPException(status_code=400, detail="No skills provided")

    # B. Check every file size (Individual Safety)
    for file in files:
        if file.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File {file.filename} exceeds 5MB limit."
            )

    async def stream_results():
        async def read_file(file: UploadFile):
            return await file.read(), file.filename
        
        file_data = await asyncio.gather(*[read_file(f) for f in files])

        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, process_single_resume, content, name, target_skills)
            for content, name in file_data
        ]

        for task in asyncio.as_completed(tasks):
            result = await task
            yield json.dumps(result) + "\n"

    return StreamingResponse(stream_results(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
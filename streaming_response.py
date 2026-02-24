import io
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

app = FastAPI(title="Real-Time Streaming Resume Parser")

# 1. Global Executor for Multiprocessing
executor = ProcessPoolExecutor()

# 2. Worker Function
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

# ------------------ API ENDPOINTS ------------------

@app.post("/rank-resumes")
async def rank_resumes(
    skills: str = Form(...), 
    files: List[UploadFile] = File(...)
):
    target_skills = [s.strip().lower() for s in skills.split(",") if s.strip()]
    if not target_skills:
        raise HTTPException(status_code=400, detail="No skills provided")

    async def stream_results():
        # Step A: Read files into memory
        async def read_file(file: UploadFile):
            return await file.read(), file.filename
        
        file_data = await asyncio.gather(*[read_file(f) for f in files])

        # Step B: Create tasks
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, process_single_resume, content, name, target_skills)
            for content, name in file_data
        ]

        # Step C: Yield results as they finish
        # asyncio.as_completed lets us grab results the millisecond they are ready
        for task in asyncio.as_completed(tasks):
            result = await task
            # Yield as a JSON string with a newline so the client can split them
            yield json.dumps(result) + "\n"

    return StreamingResponse(stream_results(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
# Resume Parser API
## Latest version : api_v3.py

A **FastAPI-based resume ranking system** that processes multiple resumes in real-time and ranks them based on matching keywords.

Supports:

- ✅ PDF
- ✅ DOCX
- ✅ JPG / JPEG / PNG (OCR)
- ✅ Streaming NDJSON responses
- ✅ Multi-core parallel processing
- ✅ Strict safety limits

---

# 📌 Features

## Built-in processing rules and rate limit

- Maximum **300 resumes per request**
- Maximum **5MB per file**
- Uses **50% of available CPU cores**
- Per-file error isolation

---

## ⚡ Performance Optimized

- Async file reading
- ProcessPoolExecutor for CPU-heavy OCR tasks
- Real-time streaming response (no waiting for all resumes to finish)

---

## 🧠 Smart Skill Matching

- Uses spaCy `EntityRuler`
- Dynamically builds skill patterns from user input
- Case-insensitive matching
- Returns:
  - Match score
  - Matched skills
  - Processing time

---

# 🏗️ Tech Stack

- FastAPI
- spaCy
- pdfplumber
- pytesseract (OCR)
- pdf2image
- Pillow
- uvicorn
- asyncio
- concurrent.futures

---

# 📦 Installation & Setup

## 1️⃣ Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/safe-resume-parser.git
cd safe-resume-parser
```

## 2️⃣ Create Virtual Environment

```Windows
python -m venv venv
venv\Scripts\activate

OR

via Anaconda
conda create -n resumefilter python=version
conda activate resumefilter
```

## 3️⃣ Install Dependencies

```
pip install -r requirements.txt
```

## 4️⃣ Install Tesseract OCR

(https://github.com/tesseract-ocr/tesseract)

## ▶️ Running the Server
```
Option 1: Run directly
python main.py

OR

Option 2: Run with uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Server will start at: http://localhost:8000
Swagger docs: http://localhost:8000/docs
```
## 📡 API Endpoint
```
POST /rank-resumes
curl -X POST "http://localhost:8000/rank-resumes" \
  -F "skills=python,fastapi,sql,aws" \
  -F "files=@resume1.pdf" \
  -F "files=@resume2.docx"
```

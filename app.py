from flask import Flask, render_template, request, jsonify
import os
import json
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
from werkzeug.utils import secure_filename
from PIL import Image
import re

# ---------------------------------------------------------------------
# INITIAL SETUP
# ---------------------------------------------------------------------

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
DATA_FOLDER = "data"
IMG_FOLDER = "static/img"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(IMG_FOLDER, exist_ok=True)

QUESTION_JSON = os.path.join(DATA_FOLDER, "QuestionBank.json")

# ---------------------------------------------------------------------
# MAIN EXTRACTION FUNCTION
# ---------------------------------------------------------------------

def extract_from_pdf(pdf_path, exam_prefix="ENEM24_F1"):
    """
    Extract text and images from a PDF and return a structured list of questions.
    """
    results = []
    doc = fitz.open(pdf_path)
    full_text = ""

    # --- STEP 1: EXTRACT ALL TEXT ---
    for page in doc:
        full_text += page.get_text("text") + "\n"

    # --- STEP 2: SPLIT QUESTIONS BY PATTERN “QUESTÃO X” ---
    parts = re.split(r"(?:QUEST[AÃ]O\s+\d+)", full_text)
    questions = [p.strip() for p in parts if p.strip()]

    for i, qtext in enumerate(questions, start=1):
        qid = f"{exam_prefix}_Q{i:03d}"
        results.append({
            "id": qid,
            "matéria": "Indefinida",
            "tema": "Indefinido",
            "texto": qtext[:800],  # preview text
            "enunciado": "",
            "alternativas": [],
            "imagens": [],
            "correta": None
        })

    # --- STEP 3: EXTRACT IMAGES FROM PAGES ---
    for page_index, page in enumerate(doc):
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            img_name = f"{exam_prefix}_P{page_index+1}_I{img_index+1}.{image_ext}"
            img_path = os.path.join(IMG_FOLDER, img_name)

            with open(img_path, "wb") as f:
                f.write(image_bytes)

            # Associate images with questions roughly by page number
            if results:
                results[min(page_index, len(results) - 1)]["imagens"].append(
                    f"static/img/{img_name}"
                )

    # --- STEP 4: OCR BACKUP (for scanned PDFs) ---
    ocr_pages = convert_from_path(pdf_path)
    for i, page_img in enumerate(ocr_pages):
        text = pytesseract.image_to_string(page_img)
        if text.strip():
            if i < len(results):
                results[i]["texto"] += "\n[OCR supplement]\n" + text
            else:
                results.append({
                    "id": f"{exam_prefix}_Q{i+1:03d}",
                    "matéria": "OCR",
                    "tema": "Extra",
                    "texto": text,
                    "enunciado": "",
                    "alternativas": [],
                    "imagens": [],
                    "correta": None
                })

    doc.close()
    return results

# ---------------------------------------------------------------------
# FLASK ROUTES
# ---------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_pdf():
    """
    Handle PDF upload, extract data, and save to QuestionBank.json.
    """
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    questions = extract_from_pdf(path)

    # merge with existing QuestionBank.json
    if os.path.exists(QUESTION_JSON):
        with open(QUESTION_JSON, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = []

    existing.extend(questions)
    with open(QUESTION_JSON, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    return jsonify({
        "message": f"{len(questions)} questions extracted and added to QuestionBank.json",
        "count": len(questions)
    })


@app.route("/questions")
def get_questions():
    """
    Return the JSON content of QuestionBank.json
    """
    if not os.path.exists(QUESTION_JSON):
        with open(QUESTION_JSON, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(QUESTION_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)

# ---------------------------------------------------------------------
# START APP
# ---------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")

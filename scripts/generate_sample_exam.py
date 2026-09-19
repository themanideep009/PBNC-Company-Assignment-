"""
Generate comprehensive sample test documents for Pragati Bharati evaluation:
1. sample_exam_digital.pdf    - Clean digital PDF with MCQs and options
2. sample_exam_multi_page.pdf - Multi-page PDF (Question 2 spans page 1 to page 2)
3. sample_exam_scanned.pdf    - Scanned-style raster PDF (for OCR testing)
4. sample_exam_scan.png       - High-resolution scan image (PNG)
5. sample_answer_key.pdf      - Dedicated answer key PDF document
6. corrupt_file.pdf           - Corrupted PDF to demonstrate error handling
7. spoofed_exe.pdf            - Executable disguised as PDF to demonstrate MIME validation
"""

from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io

OUTPUT_DIR = Path("sample_data/inputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_digital_exam_pdf():
    """Create a clean, digital single-page exam paper."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    text = """Pragati Bharati Foundation — Annual Scholarship Exam
Subject: Science and Mathematics | Time: 2 Hours | Marks: 100
--------------------------------------------------------------------------------

1. What is the primary organelle responsible for ATP production in eukaryotic cells?
(A) Nucleus
(B) Mitochondria
(C) Ribosome
(D) Endoplasmic Reticulum

2. Which chemical element has the highest thermal conductivity at room temperature?
(A) Diamond (Carbon)
(B) Silver
(C) Copper
(D) Aluminum

3. State True or False:
Sound waves travel faster in water than in air.

4. Solve for x in the quadratic equation: x^2 - 7x + 12 = 0.
(A) x = 3, 4
(B) x = 2, 6
(C) x = -3, -4
(D) x = 1, 12

5. Briefly explain the law of conservation of energy and give one real-world example.
"""
    rect = fitz.Rect(50, 50, 545, 800)
    page.insert_textbox(rect, text, fontsize=11, fontname="helv")
    pdf_path = OUTPUT_DIR / "sample_exam_digital.pdf"
    doc.save(str(pdf_path))
    doc.close()
    print(f"Created: {pdf_path}")


def create_multi_page_exam_pdf():
    """Create a 2-page exam paper where Question 2 spans across page 1 and page 2."""
    doc = fitz.open()
    
    # Page 1
    page1 = doc.new_page(width=595, height=842)
    p1_text = """Pragati Bharati Advanced Examination — Mathematics Paper
Page 1 of 2
================================================================================

1. If the function f(x) = 2x + 5 is continuous on [0, 10], what is f(4)?
(A) 11
(B) 13
(C) 15
(D) 17

2. Consider the following complex geometric sequence where the first term is a = 3
and the common ratio is r = 2. A student calculates the sum of the first 8 terms
using the standard formula for the sum of a geometric series.
(Question continues on next page...)
"""
    page1.insert_textbox(fitz.Rect(50, 50, 545, 800), p1_text, fontsize=11, fontname="helv")

    # Page 2
    page2 = doc.new_page(width=595, height=842)
    p2_text = """Pragati Bharati Advanced Examination — Mathematics Paper
Page 2 of 2
================================================================================

(Continued from Question 2):
Based on the geometric sequence above, determine the exact sum S_8 of the series:
(A) S_8 = 765
(B) S_8 = 381
(C) S_8 = 1530
(D) S_8 = 255

3. Which of the following numbers is an irrational number?
(A) 3.14
(B) sqrt(2)
(C) 22/7
(D) 0.333...
"""
    page2.insert_textbox(fitz.Rect(50, 50, 545, 800), p2_text, fontsize=11, fontname="helv")

    pdf_path = OUTPUT_DIR / "sample_exam_multi_page.pdf"
    doc.save(str(pdf_path))
    doc.close()
    print(f"Created: {pdf_path}")


def create_scan_image_and_pdf():
    """Create a scanned exam image (PNG) and an image-only scanned PDF."""
    img = Image.new("RGB", (1240, 1754), color=(248, 248, 246))  # A4 at ~150 DPI with slight off-white paper tone
    draw = ImageDraw.Draw(img)

    lines = [
        "Pragati Bharati — Entrance Test (Scanned Copy)",
        "Section A: Physics and Chemistry",
        "----------------------------------------------------------------",
        "",
        "1. What is the SI unit of electric potential difference?",
        "   (A) Ampere",
        "   (B) Volt",
        "   (C) Ohm",
        "   (D) Joule",
        "",
        "2. What is the chemical formula of ozone gas?",
        "   (A) O2",
        "   (B) O3",
        "   (C) CO2",
        "   (D) H2O",
        "",
        "3. Which particle in an atom carries a neutral electric charge?",
        "   (A) Proton",
        "   (B) Electron",
        "   (C) Neutron",
        "   (D) Positron",
    ]

    y = 80
    for line in lines:
        draw.text((100, y), line, fill=(20, 20, 20))
        y += 40

    # Add slight blur to mimic real scanner optical resolution
    scanned_img = img.filter(ImageFilter.GaussianBlur(radius=0.4))
    
    # Save PNG image
    img_path = OUTPUT_DIR / "sample_exam_scan.png"
    scanned_img.save(img_path, format="PNG")
    print(f"Created: {img_path}")

    # Convert scanned image into a scanned PDF
    pdf_doc = fitz.open()
    img_bytes = io.BytesIO()
    scanned_img.save(img_bytes, format="JPEG", quality=85)
    img_bytes.seek(0)
    
    rect = fitz.Rect(0, 0, 595, 842)
    pdf_page = pdf_doc.new_page(width=595, height=842)
    pdf_page.insert_image(rect, stream=img_bytes.getvalue())
    
    scanned_pdf_path = OUTPUT_DIR / "sample_exam_scanned.pdf"
    pdf_doc.save(str(scanned_pdf_path))
    pdf_doc.close()
    print(f"Created: {scanned_pdf_path}")


def create_answer_key_pdf():
    """Create a separate answer key PDF to demonstrate cross-document linking."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    text = """Pragati Bharati Foundation — Official Answer Key
Exam Code: PB-2026-SCI-MATH
================================================================================

Answers & Explanations:

1. Answer: (B) Mitochondria
   Explanation: Mitochondria generate most of the chemical energy needed to power the biochemical reactions.

2. Answer: (A) Diamond (Carbon)
   Explanation: Diamond has thermal conductivity exceeding 2000 W/(m·K), significantly higher than silver.

3. Answer: True
   Explanation: Sound speed in freshwater is approximately 1480 m/s compared to 343 m/s in air.

4. Answer: (A) x = 3, 4
   Explanation: Factoring (x - 3)(x - 4) = 0 gives roots 3 and 4.

5. Answer: Review
   Explanation: Long answer question graded by human evaluator.
"""
    page.insert_textbox(fitz.Rect(50, 50, 545, 800), text, fontsize=11, fontname="helv")
    pdf_path = OUTPUT_DIR / "sample_answer_key.pdf"
    doc.save(str(pdf_path))
    doc.close()
    print(f"Created: {pdf_path}")


def create_corrupt_and_spoofed_files():
    """Create corrupt and spoofed files to demonstrate error handling & security."""
    # Corrupt PDF
    corrupt_path = OUTPUT_DIR / "corrupt_file.pdf"
    with open(corrupt_path, "wb") as f:
        f.write(b"%PDF-1.4\nDeliberately malformed content without xref or EOF marker\x00\xff")
    print(f"Created: {corrupt_path}")

    # Spoofed exe as pdf
    spoofed_path = OUTPUT_DIR / "spoofed_exe.pdf"
    with open(spoofed_path, "wb") as f:
        f.write(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 200)
    print(f"Created: {spoofed_path}")


if __name__ == "__main__":
    create_digital_exam_pdf()
    create_multi_page_exam_pdf()
    create_scan_image_and_pdf()
    create_answer_key_pdf()
    create_corrupt_and_spoofed_files()
    print("\nAll sample documents generated successfully!")

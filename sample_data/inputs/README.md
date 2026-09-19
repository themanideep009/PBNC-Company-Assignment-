# Sample Input Documents

Place your test documents here:

## Required Sample Files

1. **Clean digital PDF** (`sample_exam_digital.pdf`)
   - A digitally-generated exam paper with embedded text layer
   - Should have numbered questions with MCQ options

2. **Scanned/rotated PDF** (`sample_exam_scanned.pdf`)
   - A scanned exam paper (image-based PDF)
   - May contain slight rotation or noise

3. **Image file** (`sample_question.png` or `.jpg`)
   - A photograph/scan of a single page of questions

4. **Deliberately corrupt file** (`corrupt_file.pdf`)
   - A malformed PDF for testing graceful failure handling

5. **Question paper + answer key pair**
   - `sample_question_paper.pdf` — The exam questions
   - `sample_answer_key.pdf` — The corresponding answer key

## Creating Test Files

You can create a simple test PDF using Python:

```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("sample_exam_digital.pdf", pagesize=letter)
c.drawString(72, 750, "Sample Examination Paper")
c.drawString(72, 720, "")
c.drawString(72, 700, "1. Which of the following is a prime number?")
c.drawString(100, 680, "(A) 4")
c.drawString(100, 660, "(B) 7")
c.drawString(100, 640, "(C) 9")
c.drawString(100, 620, "(D) 12")
c.drawString(72, 590, "2. State True or False: The Earth is flat.")
c.drawString(72, 560, "3. Define photosynthesis. [2 marks]")
c.drawString(72, 530, "4. Explain the water cycle in detail. [10 marks]")
c.save()
```

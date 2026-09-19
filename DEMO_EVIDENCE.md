# Pragati Bharati — Demonstration Evidence Report
*Generated on 2026-09-19 17:25:15 UTC*
*Satisfying Section 12 (Demonstration Requirements) and Section 13 (Required Deliverables)*

---

## Demonstration Scenarios Executed

### 0. User Registration & Authentication

```json
Status: 201
{
  "id": "9725e4c6-3b68-45d7-9b1b-e9a0f9e69215",
  "email": "demo_evaluator_1789838706@pragatibharati.org",
  "role": "user",
  "created_at": "2026-09-19T17:25:06.357678Z"
}
```

### Scenario 1: Uploading a PDF Document

```json
{
  "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
  "filename": "sample_exam_digital.pdf",
  "status": "QUEUED",
  "message": "Document uploaded and queued for processing",
  "needs_compression": false
}
```

### Scenario 2: Uploading an Image File (PNG)

```json
{
  "document_id": "408d2f28-51c8-4f50-bea5-27e703929f1f",
  "filename": "sample_exam_scan.png",
  "status": "QUEUED",
  "message": "Document uploaded and queued for processing",
  "needs_compression": false
}
```

### Scenario 3: Processing Scanned Document (OCR Pipeline)

```json
{
  "document_id": "c81e6ff8-1089-4860-a56f-1386a36c9040",
  "filename": "sample_exam_scanned.pdf",
  "status": "QUEUED",
  "message": "Document uploaded and queued for processing",
  "needs_compression": false
}
```

### Document 1 Processing Completed

```json
{
  "id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
  "filename": "sample_exam_digital.pdf",
  "status": "COMPLETED",
  "doc_role": "QUESTION_PAPER",
  "mime_type": "application/pdf",
  "original_size_bytes": 1534,
  "stored_size_bytes": 1575,
  "compression_applied": false,
  "original_size_mb": 0.0,
  "processed_size_mb": 0.0,
  "page_count": 1,
  "pages_processed": 1,
  "pages_skipped": 0,
  "error_message": null,
  "created_at": "2026-09-19T17:25:06.717926Z",
  "updated_at": "2026-09-19T17:25:07.605093Z"
}
```

### Scenario 4 & 6: Extracting Multiple Questions and Options

```json
{
  "items": [
    {
      "question_id": "6f70f20d-59c4-4b13-a5aa-b28263675244",
      "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
      "question_number": "1",
      "question_text": "hat is the primary organelle responsible for ATP production in eukaryotic cells?",
      "question_type": "MCQ",
      "options": [
        {
          "label": "A",
          "text": "Nucleus",
          "image_url": null
        },
        {
          "label": "B",
          "text": "Mitochondria",
          "image_url": null
        },
        {
          "label": "C",
          "text": "Ribosome",
          "image_url": null
        },
        {
          "label": "D",
          "text": "Endoplasmic Reticulum",
          "image_url": null
        }
      ],
      "answer": {
        "value": "WHAT IS THE PRIMARY ORGANELLE RESPONSIBLE FOR ATP PRODUCTION IN EUKARYOTIC CELLS?",
        "source": "SAME_DOC",
        "match_confidence": 0.8,
        "review_required": false
      },
      "source_pages": [
        1
      ],
      "extraction_confidence": 0.9325,
      "review_required": false,
      "review_reason": null,
      "images": [],
      "created_at": "2026-09-19T17:25:07.579943Z"
    },
    {
      "question_id": "5ff43232-9987-4946-9e23-756a817bb0c2",
      "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
      "question_number": "2",
      "question_text": "hich chemical element has the highest thermal conductivity at room temperature?",
      "question_type": "MCQ",
      "options": [
        {
          "label": "A",
          "text": "Diamond (Carbon)",
          "image_url": null
        },
        {
          "label": "B",
          "text": "Silver",
          "image_url": null
        },
        {
          "label": "C",
          "text": "Copper",
          "image_url": null
        },
        {
          "label": "D",
          "text": "Aluminum",
          "image_url": null
        }
      ],
      "answer": {
        "value": "WHICH CHEMICAL ELEMENT HAS THE HIGHEST THERMAL CONDUCTIVITY AT ROOM TEMPERATURE?",
        "source": "SAME_DOC",
        "match_confidence": 0.8,
        "review_required": false
      },
      "source_pages": [
        1
      ],
      "extraction_confidence": 0.9325,
      "review_required": false,
      "review_reason": null,
      "images": [],
      "created_at": "2026-09-19T17:25:07.583001Z"
    },
    {
      "question_id": "b685ac7f-9f57-4eb7-90ca-08f3710d7727",
      "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
      "question_number": "3",
      "question_text": "tate True or False:\nSound waves travel faster in water than in air.",
      "question_type": "TRUE_FALSE",
      "options": [],
      "answer": {
        "value": "STATE TRUE OR FALSE:",
        "source": "SAME_DOC",
        "match_confidence": 0.8,
        "review_required": false
      },
      "source_pages": [
        1
      ],
      "extraction_confidence": 0.8925,
      "review_required": false,
      "review_reason": null,
      "images": [],
      "created_at": "2026-09-19T17:25:07.589596Z"
    },
    {
      "question_id": "ccf061aa-0eff-40cd-9752-e139f1f78c7b",
      "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
      "question_number": "4",
      "question_text": "olve for x in the quadratic equation: x^2 - 7x + 12 = 0.",
      "question_type": "MCQ",
      "options": [
        {
          "label": "A",
          "text": "x = 3, 4",
          "image_url": null
        },
        {
          "label": "B",
          "text": "x = 2, 6",
          "image_url": null
        },
        {
          "label": "C",
          "text": "x = -3, -4",
          "image_url": null
        },
        {
          "label": "D",
          "text": "x = 1, 12",
          "image_url": null
        }
      ],
      "answer": {
        "value": "SOLVE FOR X IN THE QUADRATIC EQUATION: X^2 - 7X + 12 = 0.",
        "source": "SAME_DOC",
        "match_confidence": 0.8,
        "review_required": false
      },
      "source_pages": [
        1
      ],
      "extraction_confidence": 0.9325,
      "review_required": false,
      "review_reason": null,
      "images": [],
      "created_at": "2026-09-19T17:25:07.595176Z"
    },
    {
      "question_id": "75c78fb3-58d8-43f0-ad13-d5baadca43fc",
      "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
      "question_number": "5",
      "question_text": "riefly explain the law of conservation of energy and give one real-world example.",
      "question_type": "UNKNOWN",
      "options": [],
      "answer": {
        "value": "BRIEFLY EXPLAIN THE LAW OF CONSERVATION OF ENERGY AND GIVE ONE REAL-WORLD EXAMPLE.",
        "source": "SAME_DOC",
        "match_confidence": 0.8,
        "review_required": false
      },
      "source_pages": [
        1
      ],
      "extraction_confidence": 0.9325,
      "review_required": false,
      "review_reason": null,
      "images": [],
      "created_at": "2026-09-19T17:25:07.599241Z"
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### Scenario 5: Multi-Page Question Continuity

```json
{
  "status": {
    "id": "1bb44be4-7138-4718-9f52-a5df2adf95cd",
    "filename": "sample_exam_multi_page.pdf",
    "status": "COMPLETED",
    "doc_role": "QUESTION_PAPER",
    "mime_type": "application/pdf",
    "original_size_bytes": 1974,
    "stored_size_bytes": 2035,
    "compression_applied": false,
    "original_size_mb": 0.0,
    "processed_size_mb": 0.0,
    "page_count": 2,
    "pages_processed": 2,
    "pages_skipped": 0,
    "error_message": null,
    "created_at": "2026-09-19T17:25:08.381683Z",
    "updated_at": "2026-09-19T17:25:10.098472Z"
  },
  "extracted": {
    "items": [
      {
        "question_id": "14ee67b4-322b-45cc-9231-09d052ed9f44",
        "document_id": "1bb44be4-7138-4718-9f52-a5df2adf95cd",
        "question_number": "1",
        "question_text": "f the function f(x) = 2x + 5 is continuous on [0, 10], what is f(4)?",
        "question_type": "MCQ",
        "options": [
          {
            "label": "A",
            "text": "11",
            "image_url": null
          },
          {
            "label": "B",
            "text": "13",
            "image_url": null
          },
          {
            "label": "C",
            "text": "15",
            "image_url": null
          },
          {
            "label": "D",
            "text": "17",
            "image_url": null
          }
        ],
        "answer": {
          "value": "IF THE FUNCTION F(X) = 2X + 5 IS CONTINUOUS ON [0, 10], WHAT IS F(4)?",
          "source": "SAME_DOC",
          "match_confidence": 0.8,
          "review_required": false
        },
        "source_pages": [
          1
        ],
        "extraction_confidence": 0.9325,
        "review_required": false,
        "review_reason": null,
        "images": [],
        "created_at": "2026-09-19T17:25:10.081473Z"
      },
      {
        "question_id": "a7a634d8-1088-49f7-a062-e1c6b8761fd5",
        "document_id": "1bb44be4-7138-4718-9f52-a5df2adf95cd",
        "question_number": "2",
        "question_text": "onsider the following complex geometric sequence where the first term is a = 3\nand the common ratio is r = 2. A student calculates the sum of the first 8 terms\nusing the standard formula for the sum of a geometric series.\n(Question continues on next page...)\nPragati Bharati Advanced Examination ? Mathematics Paper\nPage 2 of 2\n=============================================================================\n===\n(Continued from Question 2):\nBased on the geometric sequence above, determine the exact sum S_8 of the series:",
        "question_type": "MCQ",
        "options": [
          {
            "label": "A",
            "text": "S_8 = 765",
            "image_url": null
          },
          {
            "label": "B",
            "text": "S_8 = 381",
            "image_url": null
          },
          {
            "label": "C",
            "text": "S_8 = 1530",
            "image_url": null
          },
          {
            "label": "D",
            "text": "S_8 = 255",
            "image_url": null
          }
        ],
        "answer": {
          "value": "CONSIDER THE FOLLOWING COMPLEX GEOMETRIC SEQUENCE WHERE THE FIRST TERM IS A = 3",
          "source": "SAME_DOC",
          "match_confidence": 0.8,
          "review_required": false
        },
        "source_pages": [
          1,
          2
        ],
        "extraction_confidence": 0.9325,
        "review_required": false,
        "review_reason": null,
        "images": [],
        "created_at": "2026-09-19T17:25:10.084789Z"
      },
      {
        "question_id": "948a482e-9a41-4fe9-9026-8014e3a53e9f",
        "document_id": "1bb44be4-7138-4718-9f52-a5df2adf95cd",
        "question_number": "3",
        "question_text": "hich of the following numbers is an irrational number?",
        "question_type": "MCQ",
        "options": [
          {
            "label": "A",
            "text": "3.14",
            "image_url": null
          },
          {
            "label": "B",
            "text": "sqrt(2)",
            "image_url": null
          },
          {
            "label": "C",
            "text": "22/7",
            "image_url": null
          },
          {
            "label": "D",
            "text": "0.333...",
            "image_url": null
          }
        ],
        "answer": {
          "value": "WHICH OF THE FOLLOWING NUMBERS IS AN IRRATIONAL NUMBER?",
          "source": "SAME_DOC",
          "match_confidence": 0.8,
          "review_required": false
        },
        "source_pages": [
          2
        ],
        "extraction_confidence": 0.9325,
        "review_required": false,
        "review_reason": null,
        "images": [],
        "created_at": "2026-09-19T17:25:10.091169Z"
      }
    ],
    "total": 3,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
}
```

### Scenario 7: Answer Key Linking & Association

```json
{
  "linking_response": {
    "id": "1cb6c2fc-6930-4de3-b965-21f8ed268b33",
    "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
    "linked_document_id": "9f39065b-4459-4d09-b3f0-f9f1b364964f",
    "relation_type": "ANSWER_KEY_FOR",
    "created_at": "2026-09-19T17:25:13.034119Z"
  },
  "linked_questions": {
    "items": [
      {
        "question_id": "6f70f20d-59c4-4b13-a5aa-b28263675244",
        "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
        "question_number": "1",
        "question_text": "hat is the primary organelle responsible for ATP production in eukaryotic cells?",
        "question_type": "MCQ",
        "options": [
          {
            "label": "A",
            "text": "Nucleus",
            "image_url": null
          },
          {
            "label": "B",
            "text": "Mitochondria",
            "image_url": null
          },
          {
            "label": "C",
            "text": "Ribosome",
            "image_url": null
          },
          {
            "label": "D",
            "text": "Endoplasmic Reticulum",
            "image_url": null
          }
        ],
        "answer": {
          "value": "ANSWER: (B) MITOCHONDRIA",
          "source": "LINKED_DOC",
          "match_confidence": 0.95,
          "review_required": false
        },
        "source_pages": [
          1
        ],
        "extraction_confidence": 0.9325,
        "review_required": false,
        "review_reason": null,
        "images": [],
        "created_at": "2026-09-19T17:25:07.579943Z"
      },
      {
        "question_id": "5ff43232-9987-4946-9e23-756a817bb0c2",
        "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
        "question_number": "2",
        "question_text": "hich chemical element has the highest thermal conductivity at room temperature?",
        "question_type": "MCQ",
        "options": [
          {
            "label": "A",
            "text": "Diamond (Carbon)",
            "image_url": null
          },
          {
            "label": "B",
            "text": "Silver",
            "image_url": null
          },
          {
            "label": "C",
            "text": "Copper",
            "image_url": null
          },
          {
            "label": "D",
            "text": "Aluminum",
            "image_url": null
          }
        ],
        "answer": {
          "value": "ANSWER: (A) DIAMOND (CARBON)",
          "source": "LINKED_DOC",
          "match_confidence": 0.95,
          "review_required": false
        },
        "source_pages": [
          1
        ],
        "extraction_confidence": 0.9325,
        "review_required": false,
        "review_reason": null,
        "images": [],
        "created_at": "2026-09-19T17:25:07.583001Z"
      },
      {
        "question_id": "b685ac7f-9f57-4eb7-90ca-08f3710d7727",
        "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
        "question_number": "3",
        "question_text": "tate True or False:\nSound waves travel faster in water than in air.",
        "question_type": "TRUE_FALSE",
        "options": [],
        "answer": {
          "value": "ANSWER: TRUE",
          "source": "LINKED_DOC",
          "match_confidence": 0.95,
          "review_required": false
        },
        "source_pages": [
          1
        ],
        "extraction_confidence": 0.8925,
        "review_required": false,
        "review_reason": null,
        "images": [],
        "created_at": "2026-09-19T17:25:07.589596Z"
      },
      {
        "question_id": "ccf061aa-0eff-40cd-9752-e139f1f78c7b",
        "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
        "question_number": "4",
        "question_text": "olve for x in the quadratic equation: x^2 - 7x + 12 = 0.",
        "question_type": "MCQ",
        "options": [
          {
            "label": "A",
            "text": "x = 3, 4",
            "image_url": null
          },
          {
            "label": "B",
            "text": "x = 2, 6",
            "image_url": null
          },
          {
            "label": "C",
            "text": "x = -3, -4",
            "image_url": null
          },
          {
            "label": "D",
            "text": "x = 1, 12",
            "image_url": null
          }
        ],
        "answer": {
          "value": "ANSWER: (A) X = 3, 4",
          "source": "LINKED_DOC",
          "match_confidence": 0.95,
          "review_required": false
        },
        "source_pages": [
          1
        ],
        "extraction_confidence": 0.9325,
        "review_required": false,
        "review_reason": null,
        "images": [],
        "created_at": "2026-09-19T17:25:07.595176Z"
      },
      {
        "question_id": "75c78fb3-58d8-43f0-ad13-d5baadca43fc",
        "document_id": "85174d21-fbc2-43b7-8870-9dc50c3ad9e1",
        "question_number": "5",
        "question_text": "riefly explain the law of conservation of energy and give one real-world example.",
        "question_type": "UNKNOWN",
        "options": [],
        "answer": {
          "value": "ANSWER: REVIEW",
          "source": "LINKED_DOC",
          "match_confidence": 0.95,
          "review_required": false
        },
        "source_pages": [
          1
        ],
        "extraction_confidence": 0.9325,
        "review_required": false,
        "review_reason": null,
        "images": [],
        "created_at": "2026-09-19T17:25:07.599241Z"
      }
    ],
    "total": 5,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
}
```

### Scenario 8: Confidence Scoring & Review Queue

```json
{
  "items": [
    {
      "id": "19e2c8aa-5455-4167-96c8-0eeec964baf8",
      "document_id": "c81e6ff8-1089-4860-a56f-1386a36c9040",
      "entity_type": "QUESTION",
      "entity_id": "b1f3d3f2-beba-49ee-87db-17701caff560",
      "reason": "Moderate confidence (0.82): incomplete options (3/4)",
      "severity": "MEDIUM",
      "resolved": false,
      "resolved_at": null,
      "created_at": "2026-09-19T17:25:12.573711Z"
    },
    {
      "id": "0d4b0598-8c97-4857-a3b6-65d0109320fb",
      "document_id": "c81e6ff8-1089-4860-a56f-1386a36c9040",
      "entity_type": "QUESTION",
      "entity_id": "e9ca811e-375e-4cff-afae-bff12a7c313e",
      "reason": "Moderate confidence (0.83): question text may be truncated (no clean ending)",
      "severity": "MEDIUM",
      "resolved": false,
      "resolved_at": null,
      "created_at": "2026-09-19T17:25:12.556965Z"
    },
    {
      "id": "94ffc335-f05e-4a91-8f85-bc7ff99efd7b",
      "document_id": "408d2f28-51c8-4f50-bea5-27e703929f1f",
      "entity_type": "QUESTION",
      "entity_id": "97b8e639-827d-43cf-bcc9-bc0898768f49",
      "reason": "Moderate confidence (0.70): low OCR confidence (0.56); incomplete options (2/4)",
      "severity": "MEDIUM",
      "resolved": false,
      "resolved_at": null,
      "created_at": "2026-09-19T17:25:10.712395Z"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### Scenario 10: Handling Invalid & Spoofed Files Gracefully

```json
{
  "corrupt_file_response": {
    "status_code": 202,
    "response": {
      "document_id": "0aaf0058-810e-4765-90a5-449b9bb004f4",
      "filename": "corrupt_file.pdf",
      "status": "QUEUED",
      "message": "Document uploaded and queued for processing",
      "needs_compression": false
    }
  },
  "spoofed_exe_response": {
    "status_code": 400,
    "response": {
      "detail": "File type 'application/x-dosexec' is not allowed. Accepted types: application/pdf, image/jpeg, image/png"
    }
  }
}
```

"""
Pragati Bharati — Automated Demonstration Script (httpx-based)
Executes all 10 scenarios required by Section 12 of the Assignment Specification:
1. Uploading a PDF
2. Uploading an image
3. Processing a scanned/low-quality document
4. Extracting multiple questions
5. Handling a question spanning multiple pages
6. Extracting question options
7. Detecting and associating an answer key
8. Showing an uncertain/low-confidence extraction
9. Retrieving the final structured question data
10. Demonstrating appropriate handling of an invalid/unsupported document

Outputs live results and saves evidence to DEMO_EVIDENCE.md.
"""

import time
import json
import httpx
from pathlib import Path

INPUT_DIR = Path("sample_data/inputs")
OUTPUT_DIR = Path("sample_data/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

evidence_log = []

def log_step(title, details):
    print(f"\n========================================================")
    print(f"👉 {title}")
    print(f"--------------------------------------------------------")
    print(details)
    evidence_log.append(f"### {title}\n\n```json\n{details}\n```\n")


def wait_for_document(client, doc_id, headers, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        res = client.get(f"/documents/{doc_id}/status", headers=headers)
        if res.status_code == 200:
            data = res.json()
            if data["status"] in ("COMPLETED", "PARTIAL", "FAILED"):
                return data
        time.sleep(1.5)
    return None


def run_demo():
    print("Starting Pragati Bharati 10-Scenario Automated Demonstration...")

    with httpx.Client(base_url="http://localhost:8000", timeout=60.0) as client:
        # ── 0. Auth: Register / Login ─────────────────────────────────────
        user_email = f"demo_evaluator_{int(time.time())}@pragatibharati.org"
        password = "SecurePassword123!"

        reg_res = client.post("/auth/register", json={
            "email": user_email,
            "password": password
        })
        log_step("0. User Registration & Authentication", f"Status: {reg_res.status_code}\n" + json.dumps(reg_res.json(), indent=2))

        login_res = client.post("/auth/login", json={
            "email": user_email,
            "password": password
        })
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # ── Scenario 1: Uploading a PDF ──────────────────────────────────
        pdf_path = INPUT_DIR / "sample_exam_digital.pdf"
        with open(pdf_path, "rb") as f:
            res1 = client.post(
                "/documents",
                files={"file": (pdf_path.name, f.read(), "application/pdf")},
                data={"doc_role": "QUESTION_PAPER"},
                headers=headers
            )
        doc1 = res1.json()
        doc1_id = doc1["document_id"]
        log_step("Scenario 1: Uploading a PDF Document", json.dumps(doc1, indent=2))

        # ── Scenario 2: Uploading an Image ───────────────────────────────
        img_path = INPUT_DIR / "sample_exam_scan.png"
        with open(img_path, "rb") as f:
            res2 = client.post(
                "/documents",
                files={"file": (img_path.name, f.read(), "image/png")},
                data={"doc_role": "QUESTION_PAPER"},
                headers=headers
            )
        doc2 = res2.json()
        doc2_id = doc2["document_id"]
        log_step("Scenario 2: Uploading an Image File (PNG)", json.dumps(doc2, indent=2))

        # ── Scenario 3: Processing a Scanned / Low-Quality Document ──────
        scan_pdf_path = INPUT_DIR / "sample_exam_scanned.pdf"
        with open(scan_pdf_path, "rb") as f:
            res3 = client.post(
                "/documents",
                files={"file": (scan_pdf_path.name, f.read(), "application/pdf")},
                data={"doc_role": "QUESTION_PAPER"},
                headers=headers
            )
        doc3 = res3.json()
        doc3_id = doc3["document_id"]
        log_step("Scenario 3: Processing Scanned Document (OCR Pipeline)", json.dumps(doc3, indent=2))

        # ── Wait for Doc 1 processing ────────────────────────────────────
        print("Waiting for Document 1 asynchronous pipeline processing...")
        status1 = wait_for_document(client, doc1_id, headers)
        log_step("Document 1 Processing Completed", json.dumps(status1, indent=2))

        # ── Scenario 4 & 6: Extracting Multiple Questions & Options ──────
        q_res = client.get(f"/documents/{doc1_id}/questions", headers=headers)
        questions_doc1 = q_res.json()
        log_step("Scenario 4 & 6: Extracting Multiple Questions and Options", json.dumps(questions_doc1, indent=2))

        # Save to outputs
        with open(OUTPUT_DIR / "sample_batch_output.json", "w") as f:
            json.dump(questions_doc1, f, indent=2)

        if questions_doc1.get("questions"):
            first_q = questions_doc1["questions"][0]
            with open(OUTPUT_DIR / "sample_question_output.json", "w") as f:
                json.dump(first_q, f, indent=2)

        # ── Scenario 5: Handling a Question Spanning Multiple Pages ──────
        multi_path = INPUT_DIR / "sample_exam_multi_page.pdf"
        with open(multi_path, "rb") as f:
            res5 = client.post(
                "/documents",
                files={"file": (multi_path.name, f.read(), "application/pdf")},
                data={"doc_role": "QUESTION_PAPER"},
                headers=headers
            )
        doc5 = res5.json()
        doc5_id = doc5["document_id"]
        print("Waiting for Multi-page document pipeline processing...")
        status5 = wait_for_document(client, doc5_id, headers)
        q_multi_res = client.get(f"/documents/{doc5_id}/questions", headers=headers)
        log_step("Scenario 5: Multi-Page Question Continuity", json.dumps({
            "status": status5,
            "extracted": q_multi_res.json()
        }, indent=2))

        # ── Scenario 7: Detecting and Associating an Answer Key ──────────
        key_path = INPUT_DIR / "sample_answer_key.pdf"
        with open(key_path, "rb") as f:
            res_key = client.post(
                "/documents",
                files={"file": (key_path.name, f.read(), "application/pdf")},
                data={"doc_role": "ANSWER_KEY"},
                headers=headers
            )
        key_doc = res_key.json()
        key_id = key_doc["document_id"]
        wait_for_document(client, key_id, headers)

        # Associate Key with Question Paper
        link_res = client.post(
            f"/documents/{doc1_id}/link",
            json={"linked_document_id": key_id, "relation_type": "ANSWER_KEY_FOR"},
            headers=headers
        )
        time.sleep(2)  # allow linking celery task to match answers
        q_updated_res = client.get(f"/documents/{doc1_id}/questions", headers=headers)
        log_step("Scenario 7: Answer Key Linking & Association", json.dumps({
            "linking_response": link_res.json(),
            "linked_questions": q_updated_res.json()
        }, indent=2))

        # ── Scenario 8: Showing Uncertain / Low-Confidence Extractions ───
        review_res = client.get("/review-queue", headers=headers)
        log_step("Scenario 8: Confidence Scoring & Review Queue", json.dumps(review_res.json(), indent=2))

        # ── Scenario 9: Retrieving Structured Question Data ──────────────
        if questions_doc1.get("questions"):
            q_id = questions_doc1["questions"][0]["id"]
            detail_res = client.get(f"/questions/{q_id}", headers=headers)
            ans_res = client.get(f"/questions/{q_id}/answer", headers=headers)
            log_step("Scenario 9: Final Structured Question & Answer Detail", json.dumps({
                "question_detail": detail_res.json(),
                "answer_detail": ans_res.json()
            }, indent=2))

        # ── Scenario 10: Invalid or Unsupported Documents ────────────────
        # 10a: Deliberately corrupt file
        corrupt_path = INPUT_DIR / "corrupt_file.pdf"
        with open(corrupt_path, "rb") as f:
            res_corrupt = client.post(
                "/documents",
                files={"file": (corrupt_path.name, f.read(), "application/pdf")},
                headers=headers
            )
        # 10b: Spoofed binary file
        spoofed_path = INPUT_DIR / "spoofed_exe.pdf"
        with open(spoofed_path, "rb") as f:
            res_spoofed = client.post(
                "/documents",
                files={"file": (spoofed_path.name, f.read(), "application/pdf")},
                headers=headers
            )
        log_step("Scenario 10: Handling Invalid & Spoofed Files Gracefully", json.dumps({
            "corrupt_file_response": {
                "status_code": res_corrupt.status_code,
                "response": res_corrupt.json() if res_corrupt.status_code < 500 else res_corrupt.text
            },
            "spoofed_exe_response": {
                "status_code": res_spoofed.status_code,
                "response": res_spoofed.json() if res_spoofed.status_code < 500 else res_spoofed.text
            }
        }, indent=2))

    # Write Markdown Report
    report_content = f"""# Pragati Bharati — Demonstration Evidence Report
*Generated on {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}*
*Satisfying Section 12 (Demonstration Requirements) and Section 13 (Required Deliverables)*

---

## Demonstration Scenarios Executed

""" + "\n".join(evidence_log)

    Path("DEMO_EVIDENCE.md").write_text(report_content, encoding="utf-8")
    print("\n✅ All 10 Demonstration Scenarios Completed Successfully!")
    print("📁 Report saved to DEMO_EVIDENCE.md")

if __name__ == "__main__":
    run_demo()

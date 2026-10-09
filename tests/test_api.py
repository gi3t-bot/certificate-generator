"""
Tests for the Certificate Generator API.

Covers:
  1. Creating a generation job
  2. Input validation
  3. Certificate generation
  4. Job status / progress
  5. Handling an individual certificate failure
  6. Retrieving generated certificates
"""

import io, os, zipfile
from unittest.mock import patch
from tests.conftest import make_xlsx


# ---------------------------------------------------------------------------
# helper - keeps upload calls short in every test
# ---------------------------------------------------------------------------
def upload(client, data: bytes, filename: str = "data.xlsx"):
    return client.post(
        "/upload",
        files={"file": (filename, io.BytesIO(data), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


# ===========================================================================
# 1. Creating a generation job
# ===========================================================================

class TestCreateGenerationJob:

    def test_returns_200_with_job_id_and_total(self, client, normal_xlsx):
        r = upload(client, normal_xlsx)
        assert r.status_code == 200
        body = r.json()
        assert "job_id" in body
        assert body["total"] == 2

    def test_job_id_is_a_valid_uuid(self, client, normal_xlsx):
        import uuid
        job_id = upload(client, normal_xlsx).json()["job_id"]
        uuid.UUID(job_id)   # raises if invalid

    def test_each_upload_gets_a_unique_job_id(self, client, normal_xlsx):
        id1 = upload(client, normal_xlsx).json()["job_id"]
        id2 = upload(client, normal_xlsx).json()["job_id"]
        assert id1 != id2

    def test_completion_date_column_is_optional(self, client):
        data = make_xlsx([{"Name": "Alice", "Course": "Python 101"}])
        r = upload(client, data)
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_real_file_1_normal_real_dates(self, client):
        with open(os.path.join("test_files", "test_1_normal_real_dates.xlsx"), "rb") as f:
            r = upload(client, f.read(), "test_1_normal_real_dates.xlsx")
        assert r.status_code == 200
        assert r.json()["total"] > 0

    def test_real_file_2_text_dates(self, client):
        with open(os.path.join("test_files", "test_2_text_dates.xlsx"), "rb") as f:
            r = upload(client, f.read(), "test_2_text_dates.xlsx")
        assert r.status_code == 200
        assert r.json()["total"] > 0


# ===========================================================================
# 2. Input validation
# ===========================================================================

class TestInputValidation:

    def test_rejects_non_xlsx_file(self, client):
        r = client.post(
            "/upload",
            files={"file": ("report.csv", io.BytesIO(b"Name,Course\nAlice,Python"), "text/csv")},
        )
        assert r.status_code == 400
        assert "excel" in r.json()["detail"].lower()

    def test_rejects_corrupt_bytes(self, client):
        r = upload(client, b"this is not a valid xlsx file")
        assert r.status_code == 400

    def test_rejects_missing_name_column(self, client, missing_name_xlsx):
        r = upload(client, missing_name_xlsx)
        assert r.status_code == 400
        assert "name" in r.json()["detail"].lower()

    def test_rejects_missing_course_column(self, client, missing_course_xlsx):
        r = upload(client, missing_course_xlsx)
        assert r.status_code == 400
        assert "course" in r.json()["detail"].lower()

    def test_rejects_empty_workbook(self, client, empty_xlsx):
        r = upload(client, empty_xlsx)
        assert r.status_code == 400

    def test_rejects_all_blank_names(self, client, blank_names_xlsx):
        r = upload(client, blank_names_xlsx)
        assert r.status_code == 400
        assert "no names" in r.json()["detail"].lower()

    def test_real_file_5_missing_course_column(self, client):
        with open(os.path.join("test_files", "test_5_missing_course_column.xlsx"), "rb") as f:
            r = upload(client, f.read(), "test_5_missing_course_column.xlsx")
        assert r.status_code == 400
        assert "course" in r.json()["detail"].lower()


# ===========================================================================
# 3. Certificate generation  (PDFs actually written to disk)
# ===========================================================================

class TestCertificateGeneration:

    def test_correct_number_of_pdfs_on_disk(self, client, normal_xlsx):
        from app.generator import OUTPUT_DIR
        job_id    = upload(client, normal_xlsx).json()["job_id"]
        batch_dir = os.path.join(OUTPUT_DIR, job_id)
        pdfs      = [f for f in os.listdir(batch_dir) if f.endswith(".pdf")]
        assert len(pdfs) == 2

    def test_pdf_files_are_not_empty(self, client, normal_xlsx):
        from app.generator import OUTPUT_DIR
        job_id    = upload(client, normal_xlsx).json()["job_id"]
        batch_dir = os.path.join(OUTPUT_DIR, job_id)
        for f in os.listdir(batch_dir):
            if f.endswith(".pdf"):
                assert os.path.getsize(os.path.join(batch_dir, f)) > 0

    def test_pdf_filenames_are_sequentially_numbered(self, client, normal_xlsx):
        from app.generator import OUTPUT_DIR
        job_id    = upload(client, normal_xlsx).json()["job_id"]
        batch_dir = os.path.join(OUTPUT_DIR, job_id)
        pdfs      = sorted(f for f in os.listdir(batch_dir) if f.endswith(".pdf"))
        assert pdfs[0].startswith("001_")
        assert pdfs[1].startswith("002_")

    def test_long_text_does_not_crash_the_generator(self, client, long_text_xlsx):
        # auto-fit must shrink the font rather than raising an exception
        r = upload(client, long_text_xlsx)
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_real_file_3_long_text(self, client):
        with open(os.path.join("test_files", "test_3_long_text.xlsx"), "rb") as f:
            r = upload(client, f.read(), "test_3_long_text.xlsx")
        assert r.status_code == 200
        assert r.json()["total"] > 0

    def test_blank_name_rows_are_skipped(self, client):
        data = make_xlsx([
            {"Name": "Alice",  "Course": "Python 101"},
            {"Name": "",       "Course": "SQL"},
            {"Name": "Bob",    "Course": "ML"},
            {"Name": None,     "Course": "Data"},
        ])
        r = upload(client, data)
        assert r.status_code == 200
        assert r.json()["total"] == 2


# ===========================================================================
# 4. Job status / progress
# ===========================================================================

class TestJobStatus:

    def test_status_endpoint_returns_200_with_expected_fields(self, client, normal_xlsx):
        job_id = upload(client, normal_xlsx).json()["job_id"]
        r      = client.get(f"/job/{job_id}")
        assert r.status_code == 200
        body = r.json()
        assert "status"      in body
        assert "total"       in body
        assert "success"     in body
        assert "failed"      in body
        assert "successful"  in body
        assert "failed_list" in body

    def test_job_is_done_after_upload_completes(self, client, normal_xlsx):
        # because background tasks run synchronously inside TestClient,
        # the job is already 'done' by the time upload() returns
        job_id = upload(client, normal_xlsx).json()["job_id"]
        status = client.get(f"/job/{job_id}").json()
        assert status["status"] == "done"

    def test_success_count_matches_input_rows(self, client):
        data = make_xlsx([
            {"Name": "Alice",   "Course": "Python 101"},
            {"Name": "Bob",     "Course": "ML Basics"},
            {"Name": "Charlie", "Course": "SQL"},
        ])
        job_id = upload(client, data).json()["job_id"]
        status = client.get(f"/job/{job_id}").json()
        assert status["success"] == 3
        assert status["failed"]  == 0

    def test_successful_list_contains_all_recipients(self, client):
        data = make_xlsx([
            {"Name": "Alice", "Course": "Python 101"},
            {"Name": "Bob",   "Course": "ML Basics"},
        ])
        job_id = upload(client, data).json()["job_id"]
        status = client.get(f"/job/{job_id}").json()
        names = [c["name"] for c in status["successful"]]
        assert "Alice" in names
        assert "Bob"   in names

    def test_unknown_job_id_returns_404(self, client):
        import uuid
        r = client.get(f"/job/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_invalid_job_id_returns_400(self, client):
        r = client.get("/job/not-a-uuid")
        assert r.status_code == 400


# ===========================================================================
# 5. Handling an individual certificate failure
# ===========================================================================

class TestIndividualCertificateFailure:

    def test_one_failure_does_not_stop_the_rest(self, client):
        # Bob's certificate will raise an exception; Alice and Charlie should still succeed
        data = make_xlsx([
            {"Name": "Alice",   "Course": "Python 101"},
            {"Name": "Bob",     "Course": "ML Basics"},
            {"Name": "Charlie", "Course": "SQL"},
        ])

        original = __import__("app.generator", fromlist=["generate_certificate"]).generate_certificate

        def fake_generate(name, course, date_text, out_path):
            if name == "Bob":
                raise RuntimeError("Simulated generation failure")
            return original(name, course, date_text, out_path)

        with patch("app.main.generate_certificate", side_effect=fake_generate):
            job_id = upload(client, data).json()["job_id"]

        status = client.get(f"/job/{job_id}").json()
        assert status["success"] == 2
        assert status["failed"]  == 1

    def test_failed_entry_shows_the_recipient_name(self, client):
        data = make_xlsx([
            {"Name": "Alice", "Course": "Python 101"},
            {"Name": "Bob",   "Course": "ML Basics"},
        ])

        original = __import__("app.generator", fromlist=["generate_certificate"]).generate_certificate

        def fake_generate(name, course, date_text, out_path):
            if name == "Bob":
                raise RuntimeError("Simulated generation failure")
            return original(name, course, date_text, out_path)

        with patch("app.main.generate_certificate", side_effect=fake_generate):
            job_id = upload(client, data).json()["job_id"]

        failed_list = client.get(f"/job/{job_id}").json()["failed_list"]
        assert any(f["name"] == "Bob" for f in failed_list)

    def test_failed_entry_includes_error_reason(self, client):
        data = make_xlsx([{"Name": "Bob", "Course": "ML Basics"}])

        def fake_generate(name, course, date_text, out_path):
            raise RuntimeError("disk full")

        with patch("app.main.generate_certificate", side_effect=fake_generate):
            job_id = upload(client, data).json()["job_id"]

        failed_list = client.get(f"/job/{job_id}").json()["failed_list"]
        assert "disk full" in failed_list[0]["reason"]

    def test_special_chars_stripped_from_filename(self, client, edge_case_xlsx):
        from app.generator import OUTPUT_DIR
        job_id    = upload(client, edge_case_xlsx).json()["job_id"]
        batch_dir = os.path.join(OUTPUT_DIR, job_id)
        for fname in os.listdir(batch_dir):
            for bad in r'/*?:"<>|':
                assert bad not in fname, f"Bad char '{bad}' in: {fname}"

    def test_duplicate_names_both_get_separate_certificates(self, client):
        from app.generator import OUTPUT_DIR
        data = make_xlsx([
            {"Name": "Rahul Sharma", "Course": "Python Workshop",        "Completion Date": "05 October 2026"},
            {"Name": "Rahul Sharma", "Course": "Web Development Course", "Completion Date": "06 October 2026"},
        ])
        job_id    = upload(client, data).json()["job_id"]
        batch_dir = os.path.join(OUTPUT_DIR, job_id)
        pdfs      = [f for f in os.listdir(batch_dir) if f.endswith(".pdf")]
        assert len(pdfs) == 2

    def test_real_file_4_edge_cases(self, client):
        with open(os.path.join("test_files", "test_4_edge_cases.xlsx"), "rb") as f:
            r = upload(client, f.read(), "test_4_edge_cases.xlsx")
        assert r.status_code == 200
        assert r.json()["total"] > 0


# ===========================================================================
# 6. Retrieving generated certificates
# ===========================================================================

class TestRetrieveGeneratedCertificates:

    def test_download_returns_200_and_zip_content_type(self, client, normal_xlsx):
        job_id = upload(client, normal_xlsx).json()["job_id"]
        r      = client.get(f"/download/{job_id}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"

    def test_zip_contains_the_expected_number_of_pdfs(self, client, normal_xlsx):
        job_id = upload(client, normal_xlsx).json()["job_id"]
        r      = client.get(f"/download/{job_id}")
        zf     = zipfile.ZipFile(io.BytesIO(r.content))
        pdfs   = [n for n in zf.namelist() if n.endswith(".pdf")]
        assert len(pdfs) == 2

    def test_zip_pdfs_are_not_empty(self, client, normal_xlsx):
        job_id = upload(client, normal_xlsx).json()["job_id"]
        r      = client.get(f"/download/{job_id}")
        zf     = zipfile.ZipFile(io.BytesIO(r.content))
        for name in zf.namelist():
            assert zf.getinfo(name).file_size > 0, f"{name} is empty inside the ZIP"

    def test_zip_only_contains_successful_certificates(self, client):
        # one cert will fail — the ZIP should only have the two successful ones
        data = make_xlsx([
            {"Name": "Alice",   "Course": "Python 101"},
            {"Name": "Bob",     "Course": "ML Basics"},
            {"Name": "Charlie", "Course": "SQL"},
        ])

        original = __import__("app.generator", fromlist=["generate_certificate"]).generate_certificate

        def fake_generate(name, course, date_text, out_path):
            if name == "Bob":
                raise RuntimeError("Simulated failure")
            return original(name, course, date_text, out_path)

        with patch("app.main.generate_certificate", side_effect=fake_generate):
            job_id = upload(client, data).json()["job_id"]

        r    = client.get(f"/download/{job_id}")
        zf   = zipfile.ZipFile(io.BytesIO(r.content))
        pdfs = [n for n in zf.namelist() if n.endswith(".pdf")]
        assert len(pdfs) == 2

    def test_download_unknown_job_returns_404(self, client):
        import uuid
        r = client.get(f"/download/{uuid.uuid4()}")
        assert r.status_code == 404

    def test_download_invalid_uuid_returns_400(self, client):
        r = client.get("/download/not-a-uuid-at-all")
        assert r.status_code == 400

    def test_content_disposition_contains_job_id(self, client, normal_xlsx):
        job_id = upload(client, normal_xlsx).json()["job_id"]
        r      = client.get(f"/download/{job_id}")
        assert job_id in r.headers.get("content-disposition", "")

    def test_download_is_repeatable(self, client, normal_xlsx):
        # downloading the same job twice must both succeed
        job_id = upload(client, normal_xlsx).json()["job_id"]
        assert client.get(f"/download/{job_id}").status_code == 200
        assert client.get(f"/download/{job_id}").status_code == 200

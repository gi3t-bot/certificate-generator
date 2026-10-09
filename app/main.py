import os, re, uuid, shutil
import openpyxl
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from datetime import date, datetime

from app.generator import generate_certificate, OUTPUT_DIR
from app.database import init_db, get_conn

app = FastAPI(title="Certificate Generator")

# initialising the database when the app starts
init_db()


def get_cell(row, idx):
    if idx is None or idx >= len(row) or row[idx] is None:
        return ""

    return row[idx]


def format_date(value):
    if isinstance(value, date):
        return value.strftime("%d %B %Y")

    return str(value).strip()


# =====================================================================
# BACKGROUND TASK  -  runs after the response is returned to the client
# =====================================================================
def process_job(job_id: str, recipients: list):
    conn      = get_conn()
    batch_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(batch_dir, exist_ok=True)

    count = 0

    for cert_id, name, course, date_text in recipients:
        count    += 1
        safe_name = re.sub(r'[\\/*?:"<>|]', "", name)
        filename  = f"{count:03d}_{safe_name}.pdf"
        out_path  = os.path.join(batch_dir, filename)

        try:
            generate_certificate(name, course, date_text, out_path)

            # marking this certificate as successfully generated
            conn.execute(
                "UPDATE certificates SET status='success', file_path=? WHERE id=?",
                (out_path, cert_id)
            )
            conn.execute(
                "UPDATE jobs SET success = success + 1 WHERE id=?",
                (job_id,)
            )

        except Exception as e:
            # marking this certificate as failed but continuing with the rest
            conn.execute(
                "UPDATE certificates SET status='failed', error_msg=? WHERE id=?",
                (str(e), cert_id)
            )
            conn.execute(
                "UPDATE jobs SET failed = failed + 1 WHERE id=?",
                (job_id,)
            )

        conn.commit()

    # marking the whole job as done once all rows are processed
    conn.execute("UPDATE jobs SET status='done' WHERE id=?", (job_id,))
    conn.commit()
    conn.close()


# =====================================================================
# POST /upload  -  submit a certificate generation job
# =====================================================================
@app.post("/upload")
def upload_excel(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="only Excel files are allowed")

    # reading the excel file to extract its contents
    try:
        wb = openpyxl.load_workbook(file.file, data_only=True)

    except Exception:
        raise HTTPException(status_code=400, detail="Count not read the excel file")

    ws   = wb.active
    rows = ws.iter_rows(values_only=True)

    try:
        header_row = next(rows)

    except StopIteration:
        raise HTTPException(status_code=400, detail="The Excel is empty")

    headers = []

    for c in header_row:
        if c is not None:
            c = str(c).strip().lower()
        else:
            c = ""

        headers.append(c)

    try:
        name_idx = headers.index("name")

        try:
            course_idx = headers.index("course")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Excel must have a 'Course' column"
            )

        date_idx = (
            headers.index("completion date") if "completion date" in headers else None
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Excel dont have a 'Name' column")

    # collecting all valid recipient rows before saving anything to the database
    recipients_raw = []

    for row in rows:
        if name_idx >= len(row) or row[name_idx] is None:
            continue

        name = str(row[name_idx]).strip()
        if not name:
            continue

        course    = str(get_cell(row, course_idx)).strip()
        date_text = format_date(get_cell(row, date_idx)) if date_idx is not None else ""

        recipients_raw.append((name, course, date_text))

    if not recipients_raw:
        raise HTTPException(status_code=400, detail="No names found in the Excel file")

    # creating a job record in the database
    job_id = str(uuid.uuid4())
    conn   = get_conn()

    conn.execute(
        "INSERT INTO jobs (id, status, total, created_at) VALUES (?, 'processing', ?, ?)",
        (job_id, len(recipients_raw), datetime.utcnow().isoformat())
    )

    # inserting one certificate row per recipient so we can track each one individually
    recipients_with_ids = []

    for name, course, date_text in recipients_raw:
        cursor = conn.execute(
            "INSERT INTO certificates (job_id, name, course, date_text) VALUES (?, ?, ?, ?)",
            (job_id, name, course, date_text)
        )
        recipients_with_ids.append((cursor.lastrowid, name, course, date_text))

    conn.commit()
    conn.close()

    # kicking off the background generation task and returning the job id immediately
    background_tasks.add_task(process_job, job_id, recipients_with_ids)

    return {"job_id": job_id, "total": len(recipients_raw)}


# =====================================================================
# GET /job/{job_id}  -  check the status and per-recipient results
# =====================================================================
@app.get("/job/{job_id}")
def get_job_status(job_id: str):

    try:
        uuid.UUID(job_id)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job id")

    conn = get_conn()

    # fetching the overall job record
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # fetching the individual certificate results
    certs = conn.execute(
        "SELECT name, course, status, error_msg FROM certificates WHERE job_id=?",
        (job_id,)
    ).fetchall()

    conn.close()

    successful   = [{"name": c["name"], "course": c["course"]}                              for c in certs if c["status"] == "success"]
    failed_list  = [{"name": c["name"], "course": c["course"], "reason": c["error_msg"]}   for c in certs if c["status"] == "failed"]

    return {
        "job_id":      job_id,
        "status":      job["status"],
        "total":       job["total"],
        "success":     job["success"],
        "failed":      job["failed"],
        "successful":  successful,
        "failed_list": failed_list,
    }


# =====================================================================
# GET /download/{job_id}  -  download all successful certificates as ZIP
# =====================================================================
@app.get("/download/{job_id}")
def download_batch(job_id: str):

    try:
        uuid.UUID(job_id)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid batch id")

    # checking if the job exists in the database
    conn = get_conn()
    job  = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()

    if not job:
        raise HTTPException(status_code=404, detail="Batch not found")

    if job["status"] != "done":
        raise HTTPException(status_code=400, detail=f"Job is still {job['status']}, please wait")

    # checking if the batch folder exists on disk
    batch_dir = os.path.join(OUTPUT_DIR, job_id)
    if not os.path.isdir(batch_dir):
        raise HTTPException(status_code=404, detail="No certificates found for this job")

    zip_base = os.path.join(OUTPUT_DIR, job_id)
    zip_path = shutil.make_archive(zip_base, "zip", root_dir=batch_dir)

    return FileResponse(
        zip_path, media_type="application/zip", filename=f"certificates_{job_id}.zip"
    )

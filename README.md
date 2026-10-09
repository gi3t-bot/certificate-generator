# Certificate Generator

A simple REST API that takes an Excel file of participant names and generates personalised PDF certificates for each person — in bulk.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Folder Structure](#folder-structure)
3. [How to Set Up the Project](#how-to-set-up-the-project)
4. [How to Run the Application](#how-to-run-the-application)
5. [How to Submit a Certificate Generation Request](#how-to-submit-a-certificate-generation-request)
6. [How to Retrieve Generated Certificates](#how-to-retrieve-generated-certificates)
7. [How to Run Tests](#how-to-run-tests)
8. [Important Design Decisions](#important-design-decisions)

---

## Project Overview

You upload an `.xlsx` Excel file containing participant data (name, course, completion date). The API reads each row, overlays the text onto a PDF certificate template, and saves one PDF per person. You then download all the certificates as a single ZIP file using a batch ID returned by the upload step.

---

## Folder Structure

```
certificate-generator/
│
├── app/
│   ├── __init__.py          # Makes `app` a Python package
│   ├── main.py              # FastAPI app — defines the /upload and /download endpoints
│   └── generator.py         # Core logic — reads the PDF template and writes text onto it
│
├── font/
│   ├── CormorantGaramond-BoldItalic.ttf      # Used for the recipient name
│   ├── CormorantGaramond-Medium.ttf          # Used for course name and date
│   └── ...                                   # Other font variants (not used directly)
│
├── templates/
│   └── certificate.pdf      # The blank certificate template all PDFs are built from
│
├── output/                  # Created automatically — stores generated certificate folders
│
├── requirements.txt         # Python dependencies
└── virt/                    # Python virtual environment (local, not committed to git)
```

---

## How to Set Up the Project

### Prerequisites

- Python **3.11** or higher
- `pip` (comes with Python)

### Steps

**1. Clone or download the project**

```bash
git clone <your-repo-url>
cd certificate-generator
```

**2. Create a virtual environment**

```bash
python -m venv virt
```

**3. Activate the virtual environment**

- **Windows:**
  ```bash
  virt\Scripts\activate
  ```
- **macOS / Linux:**
  ```bash
  source virt/bin/activate
  ```

**4. Install dependencies**

```bash
pip install -r requirements.txt
```

That installs:

| Package            | Purpose                        |
| ------------------ | ------------------------------ |
| `fastapi`          | Web framework for the REST API |
| `uvicorn`          | ASGI server to run FastAPI     |
| `python-multipart` | Required for file uploads      |
| `openpyxl`         | Reads `.xlsx` Excel files      |
| `reportlab`        | Draws text onto a PDF canvas   |
| `pypdf`            | Reads and merges PDF pages     |

---

## How to Run the Application

Make sure your virtual environment is active, then run:

```bash
uvicorn app.main:app --reload
```

The API will start at: **http://127.0.0.1:8000**

You can also open the interactive API docs in your browser at:

- **http://127.0.0.1:8000/docs** (Swagger UI — easiest way to test manually)
- **http://127.0.0.1:8000/redoc**

---

## How to Submit a Certificate Generation Request

### Step 1 — Prepare your Excel file

Create an `.xlsx` file with the following columns (header names are **case-insensitive**):

| Column            | Required    | Description                   |
| ----------------- | ----------- | ----------------------------- |
| `Name`            | ✅ Yes      | Recipient's full name         |
| `Course`          | ✅ Yes      | Course or programme name      |
| `Completion Date` | ❌ Optional | Date shown on the certificate |

Example:

| Name          | Course              | Completion Date |
| ------------- | ------------------- | --------------- |
| Alice Johnson | Python Fundamentals | 2024-09-01      |
| Bob Smith     | Data Science 101    | 2024-09-15      |

> Rows with an empty `Name` cell are automatically skipped.

### Step 2 — Upload the file

**Using the Swagger UI:**

1. Open http://127.0.0.1:8000/docs
2. Click on `POST /upload`
3. Click **Try it out**
4. Upload your `.xlsx` file and click **Execute**

### Step 3 — Note the batch ID

A successful response looks like this:

```json
{
  "job_id": "a3f1c2d4-...",
  "total": 2
}
```

- `job_id` — a unique ID for this job (use it to check status and download)
- `total` — how many valid recipients were found in the file

---

## How to Check Job Status

Use the `job_id` returned by `/upload` to check progress and see per-recipient results.

```
GET http://127.0.0.1:8000/job/{job_id}
```

Example response:

```json
{
  "job_id":  "a3f1c2d4-...",
  "status":  "done",
  "total":   3,
  "success": 2,
  "failed":  1,
  "successful":  [{"name": "Alice Johnson", "course": "Python 101"}],
  "failed_list": [{"name": "Bob Smith", "course": "ML Basics", "reason": "..."}]
}
```

Possible `status` values: `processing` → `done`

---

## How to Retrieve Generated Certificates

Use the `job_id` to download all successful certificates as a single ZIP file.

**Using the Swagger UI:**

1. Open http://127.0.0.1:8000/docs
2. Click on `GET /download/{job_id}`
3. Click **Try it out**
4. Paste the `job_id` and click **Execute**
5. Download the returned ZIP file

The ZIP contains one PDF per successful recipient, named like:

```
001_Alice Johnson.pdf
002_Bob Smith.pdf
```

---

## How to Run Tests

The project includes an automated test suite (`tests/test_api.py`) with **39 tests** covering all critical paths.

### Install test dependencies (one-time)

```bash
pip install pytest httpx
```

### Run all tests

```bash
pytest tests/ -v
```

### What is tested

| Test class | What it covers |
| --------------------------------------- | ----------------------------------------------------------------- |
| `TestCreateGenerationJob`               | Happy-path upload, UUID job ID, unique IDs, optional date column  |
| `TestInputValidation`                   | Wrong file type, missing columns, empty workbook, corrupt bytes   |
| `TestCertificateGeneration`             | PDF count on disk, file sizes, sequential naming, long text       |
| `TestJobStatus`                         | Status fields, done state, success count, unknown/invalid job IDs |
| `TestIndividualCertificateFailure`      | One failure doesn't stop others, error reason in response, special chars |
| `TestRetrieveGeneratedCertificates`     | ZIP content, only successful PDFs, 404/400 errors, repeat downloads |

Tests also run against the five real Excel files in `test_files/` to validate end-to-end behaviour.

### Expected output

```
39 passed in ~3s
```

## Important Design Decisions

### 1. PDF overlay approach (no template re-rendering)

Instead of building certificates from scratch, the app uses an existing `certificate.pdf` as a design template. Text (name, course, date) is drawn onto a transparent in-memory canvas using **ReportLab**, then merged on top of the template using **pypdf**. This keeps the visual design completely separate from the code — designers can update the template PDF without touching any Python.

### 2. SQLite database for job and certificate tracking

Every upload creates a `Job` record and one `Certificate` record per recipient in a local SQLite database (`certificates.db`). This gives the API a proper status endpoint (`GET /job/{job_id}`) that can report exactly which recipients succeeded and which failed — and why. SQLite was chosen because it needs zero setup, ships with Python, and is a real relational database.

### 3. Background processing via FastAPI BackgroundTasks

The `/upload` endpoint saves the job to the database and returns the `job_id` immediately. The actual PDF generation runs in a `BackgroundTask` after the response is sent. This means large batches don't time out the HTTP connection. The client polls `GET /job/{job_id}` to check progress.

### 4. Per-certificate failure isolation

Inside `process_job()`, each certificate is generated inside its own `try/except`. If one fails (corrupted name, disk error, etc.) the error is written to that certificate's database row and processing continues for the remaining recipients. The final job status shows exactly who succeeded and who failed.

### 5. Auto-fitting text

Long names or course titles won't overflow the certificate. The `draw_fitted()` function in `generator.py` gradually shrinks the font size until the text fits within the defined maximum width, with a hard floor (`min_size`) so text is never unreadably small.

### 6. Fonts

The **Cormorant Garamond** font family is used throughout for an elegant, formal look suitable for certificates:

- **Bold Italic** for the recipient's name (larger, prominent)
- **Medium** for the course name and completion date (smaller, supporting text)

### 7. Excel column detection

Column detection is done by matching header names (case-insensitive). `Name` and `Course` are required; `Completion Date` is optional. Rows with blank names are silently skipped so a partially-filled sheet doesn't cause errors.

### 8. Zip-on-demand download

The ZIP file is created fresh each time `GET /download/{job_id}` is called using Python's built-in `shutil.make_archive`. No ZIP is stored persistently, keeping disk usage clean.

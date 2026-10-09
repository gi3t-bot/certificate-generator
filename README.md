# Certificate Generator API

Hey! 👋 Welcome to the Certificate Generator — a backend API that takes a list of participants from an Excel file and automatically generates a personalised PDF certificate for each one. No more doing it one by one.

This README will walk you through everything — setting it up, running it, using it, and understanding why things were built the way they were. Just follow along top to bottom and you'll have it running in a few minutes.

---

## What does this actually do?

Here's the basic flow:

1. You prepare an Excel file with your participants' names, course names, and completion dates.
2. You upload it to the API.
3. The API generates a PDF certificate for each participant — in the background, so you don't have to wait.
4. You check the status to see how many succeeded (and if any failed, you'll know exactly who and why).
5. You download all the certificates as a single ZIP file.

That's it. Simple, fast, and handles bulk generation without breaking a sweat.

---

## What's inside the project

Before you run anything, here's a quick map of the codebase so you know where everything lives:

```
certificate-generator/
│
├── app/
│   ├── main.py        → The FastAPI app. All three API endpoints live here.
│   ├── generator.py   → The actual PDF generation logic. Reads the template and writes text onto it.
│   ├── database.py    → SQLite setup. Creates the jobs and certificates tables.
│   └── __init__.py    → Just marks this folder as a Python package.
│
├── font/              → Cormorant Garamond fonts used on the certificate.
├── templates/
│   └── certificate.pdf  → The blank certificate design. All generated PDFs are built on top of this.
│
├── test_files/        → Five ready-made Excel files you can use to test different scenarios.
├── tests/
│   ├── conftest.py    → Shared fixtures and helpers for the test suite.
│   └── test_api.py    → 39 tests covering every important part of the API.
│
├── requirements.txt   → All Python dependencies.
└── .gitignore         → Keeps the virtual env, generated files, and DB out of git.
```

---

## Setting it up on your machine

### What you need first

- **Python 3.11 or higher** — check with `python --version`
- **pip** — comes bundled with Python, so you likely already have it

### Step 1 — Clone the repo

```bash
git clone https://github.com/gi3t-bot/certificate-generator.git
cd certificate-generator
```

### Step 2 — Create a virtual environment

A virtual environment keeps the project's dependencies isolated from your system Python. Always a good idea.

```bash
python -m venv virt
```

### Step 3 — Activate the virtual environment

You need to activate it every time you open a new terminal for this project.

**On Windows:**
```bash
virt\Scripts\activate
```

**On macOS / Linux:**
```bash
source virt/bin/activate
```

You'll know it's active when you see `(virt)` at the start of your terminal prompt.

### Step 4 — Install the dependencies

```bash
pip install -r requirements.txt
```

This installs six packages — here's what each one does:

| Package | What it's for |
| ------------------ | ----------------------------------------------- |
| `fastapi` | The web framework the API is built on |
| `uvicorn` | The server that runs the FastAPI app |
| `python-multipart` | Needed for file uploads to work in FastAPI |
| `openpyxl` | Reads the Excel `.xlsx` files you upload |
| `reportlab` | Draws the text (name, course, date) onto a PDF canvas |
| `pypdf` | Merges that text canvas onto the certificate template |

That's all the setup you need. No database server, no Docker, nothing external.

---

## Running the application

Once the virtual environment is active and dependencies are installed, just run:

```bash
uvicorn app.main:app --reload
```

The `--reload` flag means the server automatically restarts whenever you change a file — very handy during development.

You'll see something like this in your terminal:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Now open your browser and go to:

**👉 http://127.0.0.1:8000/docs**

This is the Swagger UI — an interactive page where you can call every endpoint directly from the browser without needing Postman or curl. I'd recommend using this to try things out.

---

## Using the API — a complete walkthrough

### Step 1 — Prepare your Excel file

Create a `.xlsx` file (not `.csv`, not `.xls` — it must be `.xlsx`). The column headers are **case-insensitive**, so `NAME`, `Name`, and `name` all work.

| Column | Required? | What it does |
| ----------------- | --------- | ----------------------------------------- |
| `Name` | ✅ Yes | The participant's full name on the certificate |
| `Course` | ✅ Yes | The course or programme they completed |
| `Completion Date` | ❌ Optional | The date printed on the certificate |

Your file can look like this:

| Name | Course | Completion Date |
| ------------- | ------------------- | --------------- |
| Alice Johnson | Python Fundamentals | 01 September 2024 |
| Bob Smith | Data Science 101 | 15 September 2024 |

A couple of things worth knowing:
- If a row has an empty `Name` cell, it's **silently skipped** — no error thrown, just ignored.
- If `Completion Date` is missing for a row or the whole column doesn't exist, the date just won't appear on that certificate. Everything else still works fine.

There are also five ready-made test files in the `test_files/` folder if you want to jump straight in without creating your own.

---

### Step 2 — Upload the file and create a job

Hit **`POST /upload`** in Swagger, upload your `.xlsx` file, and click Execute.

The API will immediately respond with:

```json
{
  "job_id": "a3f1c2d4-5678-...",
  "total": 2
}
```

- **`job_id`** — hold onto this, you'll need it for the next two steps
- **`total`** — how many valid recipients were found in your file

The generation starts in the background right after this response. The API doesn't make you wait — it just starts working and you can check on it whenever you want.

---

### Step 3 — Check the job status

Hit **`GET /job/{job_id}`** and paste in the `job_id` from the previous step.

You'll get back something like this:

```json
{
  "job_id": "a3f1c2d4-5678-...",
  "status": "done",
  "total": 3,
  "success": 2,
  "failed": 1,
  "successful": [
    { "name": "Alice Johnson", "course": "Python Fundamentals" }
  ],
  "failed_list": [
    { "name": "Bob Smith", "course": "Data Science 101", "reason": "..." }
  ]
}
```

The `status` field will be either `processing` (still going) or `done` (finished).

What's really useful here is the `failed_list` — if a certificate failed for any reason, you'll see exactly whose it was and why. A single failure **never** stops the rest of the batch from being processed.

---

### Step 4 — Download the certificates

Once the status is `done`, hit **`GET /download/{job_id}`** with the same `job_id`.

You'll get a ZIP file containing one PDF per successful recipient, named like:

```
001_Alice Johnson.pdf
002_Bob Smith.pdf
```

The ZIP only includes the successful ones — failed ones are logged in the status endpoint but won't appear in the download.

You can call the download endpoint as many times as you want — the ZIP is rebuilt fresh each time from the files on disk.

---

## Running the tests

The project has a full test suite — 39 tests covering every important scenario. Before running them, install the test dependencies if you haven't already:

```bash
pip install pytest httpx
```

Then run:

```bash
pytest tests/ -v
```

You should see all 39 tests pass in about 3 seconds:

```
39 passed in ~3s
```

Here's what each test group covers:

| Test class | What it checks |
| --------------------------------------- | ---------------------------------------------------------------- |
| `TestCreateGenerationJob` | Upload works, returns valid UUID job ID, each upload is unique |
| `TestInputValidation` | Wrong file types, missing columns, empty/corrupt files rejected |
| `TestCertificateGeneration` | Correct number of PDFs on disk, file sizes, sequential naming |
| `TestJobStatus` | Status fields present, counts correct, invalid IDs handled |
| `TestIndividualCertificateFailure` | One failure doesn't stop others, error reason is returned |
| `TestRetrieveGeneratedCertificates` | ZIP has right PDFs, only successes included, repeat downloads work |

The tests also use the five real Excel files in `test_files/` to run proper end-to-end checks.

---

## Design decisions — and why I made them

These are the choices that shaped how the project is built. If you're reviewing this or thinking of extending it, this section will save you a lot of "why was this done this way?" time.

### 1. PDF overlay instead of building from scratch

I didn't generate certificates from a blank page. Instead, `certificate.pdf` in the `templates/` folder is a pre-designed PDF that acts as the visual base. The code draws the recipient's name, course, and date onto a transparent in-memory canvas using **ReportLab**, then merges that canvas on top of the template using **pypdf**.

Why? Because it completely separates design from code. If you want a new certificate design, you just swap out the template PDF — you don't touch a single line of Python.

### 2. SQLite as the relational database

Every upload creates a `Job` row in the database, and every recipient gets a `Certificate` row. This is what powers the status endpoint — you can always look up exactly what happened to each certificate.

SQLite was the right call here: it's a real relational database, ships built into Python, needs zero configuration, and works perfectly for this scale. No Postgres, no Docker container, nothing to set up.

### 3. Background processing so the client isn't left waiting

When you upload a file with 200 participants, you don't want to stare at a loading spinner for 30 seconds. So `/upload` saves the job to the database, queues the generation as a background task, and returns the `job_id` **immediately**. The PDFs are created in the background while you get on with things. You poll `/job/{job_id}` when you want to know if it's done.

### 4. Per-certificate failure isolation — one bad row doesn't ruin the batch

Inside the background task, each certificate is generated inside its own `try/except` block. If something goes wrong for one recipient (weird characters in the name, a file system hiccup, anything), the error gets recorded against that specific certificate row in the database, and the loop moves on to the next one. Nothing crashes, nothing stops. The status endpoint will show you exactly who failed and what the reason was.

### 5. Auto-fitting text for long names and course titles

Not everyone has a short name. "Venkatasubramanian Raghunathan Iyer" is a real name and it needs to fit on the certificate without overflowing. The `draw_fitted()` function in `generator.py` starts at the default font size and shrinks it one point at a time until the text fits within the allowed width. There's a minimum size floor too, so text is never unreadably tiny.

### 6. Fonts — Cormorant Garamond

The certificate uses the **Cormorant Garamond** font family — a classic serif that looks elegant on formal documents. The recipient's name is in Bold Italic (larger, prominent), and the course name and date are in Medium (smaller, supporting). The `.ttf` files are bundled in the `font/` folder so the project works out of the box without any system font installation.

### 7. Excel column detection is flexible

Column headers are matched in lowercase after stripping whitespace, so `Name`, `NAME`, `name`, and `  Name  ` all work the same way. `Name` and `Course` are required. `Completion Date` is optional — if it's missing from the file entirely, certificates are still generated, just without a date.

### 8. The ZIP is built on demand, not stored

Every time you call `/download/{job_id}`, the ZIP is created fresh from the files in the `output/{job_id}/` folder using Python's built-in `shutil.make_archive`. Nothing is pre-zipped and stored. This keeps disk usage simple and means you can download the same batch multiple times without any issues.

---

## Questions?

If something isn't working or you want to understand a specific part of the code better, feel free to raise an issue or reach out directly.

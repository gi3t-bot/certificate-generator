"""
Shared fixtures and helpers for all tests.
"""
import io
import pytest
import openpyxl
from fastapi.testclient import TestClient
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_xlsx(rows: list[dict], filename: str = "test.xlsx") -> tuple[str, bytes, str]:
    """
    Build an in-memory .xlsx file from a list of dicts.
    First dict defines column order via its keys.
    Returns (field_name, file_bytes, filename) ready for TestClient upload.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client():
    """Re-use a single TestClient across the whole test session."""
    return TestClient(app)


@pytest.fixture()
def normal_xlsx():
    """A valid .xlsx with Name, Course and Completion Date columns (2 rows)."""
    return make_xlsx([
        {"Name": "Alice Johnson", "Course": "Python Fundamentals", "Completion Date": "01 September 2024"},
        {"Name": "Bob Smith",    "Course": "Data Science 101",    "Completion Date": "15 September 2024"},
    ])


@pytest.fixture()
def long_text_xlsx():
    """Names and courses that are deliberately too long to fit at the default font size."""
    return make_xlsx([
        {
            "Name":            "Venkatasubramanian Raghunathan Iyer",
            "Course":          "Advanced Machine Learning and Deep Neural Networks Masterclass",
            "Completion Date": "05 October 2026",
        },
        {
            "Name":            "Mohammad Abdul Rahman Al-Farsi Khan",
            "Course":          "Full Stack Web Development with React, Node.js and Cloud Deployment",
            "Completion Date": "05 October 2026",
        },
    ])


@pytest.fixture()
def edge_case_xlsx():
    """Names with special characters that must be stripped from filenames."""
    return make_xlsx([
        {"Name": "Sam O'Brien",        "Course": "Python Workshop",       "Completion Date": ""},
        {"Name": "A/B Testing: Anand", "Course": "Web Development Course", "Completion Date": ""},
        {"Name": "Zoya? Khan*",        "Course": "Data Science Bootcamp", "Completion Date": ""},
    ])


@pytest.fixture()
def missing_course_xlsx():
    """A .xlsx that has Name but NO Course column — must be rejected."""
    return make_xlsx([
        {"Name": "Alice Johnson", "Completion Date": "01 September 2024"},
    ])


@pytest.fixture()
def missing_name_xlsx():
    """A .xlsx that has Course but NO Name column — must be rejected."""
    return make_xlsx([
        {"Course": "Python Fundamentals", "Completion Date": "01 September 2024"},
    ])


@pytest.fixture()
def blank_names_xlsx():
    """Only blank/empty Name cells — no certificates should be produced."""
    return make_xlsx([
        {"Name": "",   "Course": "Python Fundamentals"},
        {"Name": None, "Course": "Data Science 101"},
    ])


@pytest.fixture()
def empty_xlsx():
    """A completely empty workbook (header row missing)."""
    wb = openpyxl.Workbook()
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

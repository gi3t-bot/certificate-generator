from io import BytesIO
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
import os

# importing to use different font for the naming and all
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "certificate.pdf")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


# font setting for the name
FONT_PATH = os.path.join(BASE_DIR, "font", "CormorantGaramond-BoldItalic.ttf")
pdfmetrics.registerFont(TTFont("NameFont", FONT_PATH))
FONT_NAME = "NameFont"
FONT_SIZE = 36
NAME_Y = 315


# font setting for the course and date
BODY_FONT_PATH = os.path.join(BASE_DIR, "font", "CormorantGaramond-Medium.ttf")
pdfmetrics.registerFont(TTFont("BodyFont", BODY_FONT_PATH))

COURSE_FONT_SIZE = 24
COURSE_Y = 255
DATE_FONT_SIZE = 18
DATE_Y = 222
MAX_TEXT_WIDTH = 560

MAX_NAME_WIDTH = 480


def draw_fitted(c, text, font, size, x, y, max_width, min_size=12):
    while pdfmetrics.stringWidth(text, font, size) > max_width and size > min_size:
        size -= 1
    c.setFont(font, size)
    c.drawCentredString(x, y, text)


def generate_certificate(name, course, date_text, output_path):
    # Reading the template and getting its size

    reader = PdfReader(TEMPLATE_PATH)
    page = reader.pages[0]

    width = float(page.mediabox.width)
    height = float(page.mediabox.height)

    # drawing the name on a blank in-memory page

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(width, height))

    draw_fitted(
        c, name, FONT_NAME, FONT_SIZE, width / 2, NAME_Y, MAX_NAME_WIDTH, min_size=14
    )

    if course:
        draw_fitted(
            c,
            f"for successfully completing the {course}",
            "BodyFont",
            COURSE_FONT_SIZE,
            width / 2,
            COURSE_Y,
            MAX_TEXT_WIDTH,
        )

    if date_text:
        draw_fitted(
            c,
            f"Completed on {date_text}",
            "BodyFont",
            DATE_FONT_SIZE,
            width / 2,
            DATE_Y,
            MAX_TEXT_WIDTH,
        )

    c.save()

    buffer.seek(0)

    # merging the overlay onto the template
    overlay_page = PdfReader(buffer).pages[0]
    page.merge_page(overlay_page)

    # writing the output the files
    writer = PdfWriter()
    writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

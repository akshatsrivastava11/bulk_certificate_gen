"""
Certificate PDF Generator using ReportLab.
Produces a professional A4-landscape PDF certificate for each recipient.
"""
import os
from datetime import date
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


# ─── Color Palette ─────────────────────────────────────────────────────────────

NAVY_DARK = colors.HexColor("#0D1B2A")
NAVY = colors.HexColor("#1B2E4B")
GOLD = colors.HexColor("#C9972A")
GOLD_LIGHT = colors.HexColor("#E8C56A")
CREAM = colors.HexColor("#FDF8EE")
WHITE = colors.white
GRAY_LIGHT = colors.HexColor("#E8E8E8")
GRAY = colors.HexColor("#888888")


PAGE_W, PAGE_H = landscape(A4)  # 842 x 595 pts


def _draw_background(c: canvas.Canvas):
    """Draw the layered background."""
    # Main dark navy background
    c.setFillColor(NAVY_DARK)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Decorative side panels
    c.setFillColor(NAVY)
    c.rect(0, 0, 60, PAGE_H, fill=1, stroke=0)
    c.rect(PAGE_W - 60, 0, 60, PAGE_H, fill=1, stroke=0)

    # Cream inner parchment area
    margin = 65
    c.setFillColor(CREAM)
    c.roundRect(margin, 30, PAGE_W - 2 * margin, PAGE_H - 60, 8, fill=1, stroke=0)

    # Gold border frame on parchment
    c.setStrokeColor(GOLD)
    c.setLineWidth(2.5)
    c.roundRect(margin + 10, 40, PAGE_W - 2 * (margin + 10), PAGE_H - 80, 5, fill=0, stroke=1)

    # Thin inner border line
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(0.8)
    c.roundRect(margin + 16, 46, PAGE_W - 2 * (margin + 16), PAGE_H - 92, 3, fill=0, stroke=1)


def _draw_decorative_corners(c: canvas.Canvas):
    """Draw ornamental corner flourishes."""
    margin = 65
    x1, y1 = margin + 10, 40         # bottom-left of gold border
    x2 = x1 + PAGE_W - 2 * (margin + 10)  # bottom-right
    y2 = y1 + PAGE_H - 80            # top corners

    corner_size = 18

    def _corner(cx, cy, dx, dy):
        c.setStrokeColor(GOLD)
        c.setLineWidth(2)
        c.line(cx, cy, cx + dx * corner_size, cy)
        c.line(cx, cy, cx, cy + dy * corner_size)
        c.setFillColor(GOLD)
        c.circle(cx, cy, 3, fill=1, stroke=0)

    _corner(x1, y1, +1, +1)  # bottom-left
    _corner(x2, y1, -1, +1)  # bottom-right
    _corner(x1, y2, +1, -1)  # top-left
    _corner(x2, y2, -1, -1)  # top-right


def _draw_header_seal(c: canvas.Canvas):
    """Draw a decorative seal/emblem at the top."""
    cx = PAGE_W / 2
    seal_y = PAGE_H - 88

    # Outer ring
    c.setFillColor(GOLD)
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(1.5)
    c.circle(cx, seal_y, 30, fill=1, stroke=1)

    # Inner ring
    c.setFillColor(NAVY_DARK)
    c.circle(cx, seal_y, 24, fill=1, stroke=0)

    # Star / asterisk symbol
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(cx, seal_y - 8, "★")


def _draw_side_decorations(c: canvas.Canvas):
    """Draw thin vertical decorative lines on side panels."""
    for x in [30, PAGE_W - 30]:
        c.setStrokeColor(GOLD)
        c.setLineWidth(1)
        c.setDash(4, 4)
        c.line(x, 60, x, PAGE_H - 60)
    c.setDash()  # reset dash


def generate_certificate_pdf(
    output_path: str,
    recipient_name: str,
    event_name: str,
    issued_by: str,
    course_name: Optional[str] = None,
    grade: Optional[str] = None,
    event_date: Optional[date] = None,
    certificate_id: Optional[str] = None,
) -> str:
    """
    Generate a single PDF certificate.

    Args:
        output_path: Absolute path where the PDF should be saved.
        recipient_name: Full name of the certificate recipient.
        event_name: Name of the event/program being certified.
        issued_by: Organization or person issuing the certificate.
        course_name: Optional course or subject name.
        grade: Optional grade or score.
        event_date: Optional date of the event.
        certificate_id: Optional unique certificate reference ID.

    Returns:
        The resolved output path string.
    """
    os.makedirs(Path(output_path).parent, exist_ok=True)
    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    c.setTitle(f"Certificate of Achievement – {recipient_name}")

    # ── Background & Decoration ──────────────────────────────────────────────
    _draw_background(c)
    _draw_decorative_corners(c)
    _draw_header_seal(c)
    _draw_side_decorations(c)

    # ── "CERTIFICATE" header text ────────────────────────────────────────────
    c.setFillColor(NAVY_DARK)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 64, "CERTIFICATE")

    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 116, "OF ACHIEVEMENT")

    # Decorative separator line under header
    line_y = PAGE_H - 128
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(PAGE_W / 2 - 120, line_y, PAGE_W / 2 + 120, line_y)

    # ── "This is to certify that" ────────────────────────────────────────────
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 11)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 160, "This is to proudly certify that")

    # ── Recipient Name ───────────────────────────────────────────────────────
    name_y = PAGE_H - 200
    # Name underline
    name_w = min(len(recipient_name) * 14 + 60, 440)
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(0.8)
    c.line(PAGE_W / 2 - name_w / 2, name_y - 6, PAGE_W / 2 + name_w / 2, name_y - 6)

    c.setFillColor(NAVY_DARK)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(PAGE_W / 2, name_y, recipient_name)

    # ── Course / Event info ──────────────────────────────────────────────────
    body_y = name_y - 46

    if course_name:
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 11)
        c.drawCentredString(PAGE_W / 2, body_y, "has successfully completed the course")
        body_y -= 24

        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(PAGE_W / 2, body_y, course_name)
        body_y -= 22

    c.setFillColor(GRAY)
    c.setFont("Helvetica", 11)
    c.drawCentredString(PAGE_W / 2, body_y, f"as part of  \"{event_name}\"")
    body_y -= 22

    if grade:
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 11)
        c.drawCentredString(PAGE_W / 2, body_y, f"with a grade of")
        body_y -= 22
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(PAGE_W / 2, body_y, grade)
        body_y -= 18

    # ── Footer: Date | Issued by | Cert ID ──────────────────────────────────
    footer_y = 76
    left_x = 130
    right_x = PAGE_W - 130

    # Signature line - left
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.8)
    c.line(left_x - 60, footer_y + 22, left_x + 60, footer_y + 22)
    date_str = event_date.strftime("%B %d, %Y") if event_date else "—"
    c.setFillColor(NAVY_DARK)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(left_x, footer_y + 10, date_str)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 8)
    c.drawCentredString(left_x, footer_y, "DATE")

    # Signature line - right
    c.line(right_x - 60, footer_y + 22, right_x + 60, footer_y + 22)
    c.setFillColor(NAVY_DARK)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(right_x, footer_y + 10, issued_by)
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 8)
    c.drawCentredString(right_x, footer_y, "ISSUED BY")

    # Certificate ID at the very bottom center
    if certificate_id:
        c.setFillColor(GRAY)
        c.setFont("Helvetica", 7)
        c.drawCentredString(PAGE_W / 2, 34, f"Certificate ID: {certificate_id}")

    c.save()
    return output_path

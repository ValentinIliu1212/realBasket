"""Render the hackathon architecture documents (Markdown subset) to PDF with reportlab.

  architecture-detailed.md -> architecture-detailed.pdf
  architecture-summary.md  -> architecture-summary.pdf

Usage: poetry run python hackathon/build_pdf.py [detailed|summary]   (no argument: both)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

HERE = Path(__file__).resolve().parent
# name -> (source, output, page header, PDF title)
DOCS = {
    "detailed": ("architecture-detailed.md", "architecture-detailed.pdf",
                 "RealBasket – Detailed Architecture (MCP + Weaviate)", "RealBasket – Detailed Architecture"),
    "summary": ("architecture-summary.md", "architecture-summary.pdf",
                "RealBasket – Architecture Summary (MCP + Weaviate)", "RealBasket – Architecture Summary"),
}

ACCENT = colors.HexColor("#1F4E79")
LIGHT = colors.HexColor("#EAF1F8")


def register_fonts() -> tuple[str, str, str, str]:
    fonts = Path("C:/Windows/Fonts")
    files = {
        "Body": "arial.ttf",
        "Body-Bold": "arialbd.ttf",
        "Body-Italic": "ariali.ttf",
        "Body-BoldItalic": "arialbi.ttf",
        "Mono": "consola.ttf",
    }
    if all((fonts / f).exists() for f in files.values()):
        for name, f in files.items():
            pdfmetrics.registerFont(TTFont(name, str(fonts / f)))
        pdfmetrics.registerFontFamily(
            "Body", normal="Body", bold="Body-Bold",
            italic="Body-Italic", boldItalic="Body-BoldItalic",
        )
        return "Body", "Body-Bold", "Body-Italic", "Mono"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"


BODY, BOLD, ITALIC, MONO = register_fonts()
base = getSampleStyleSheet()
S = {
    "h1": ParagraphStyle("h1", parent=base["Title"], fontName=BOLD, fontSize=22,
                         textColor=ACCENT, alignment=TA_LEFT, spaceAfter=4),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=BOLD, fontSize=14,
                         textColor=ACCENT, spaceBefore=12, spaceAfter=6),
    "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName=BOLD, fontSize=11.5,
                         textColor=colors.HexColor("#2E75B6"), spaceBefore=8, spaceAfter=4),
    "p": ParagraphStyle("p", parent=base["BodyText"], fontName=BODY, fontSize=9.5,
                        leading=13, spaceAfter=5),
    "quote": ParagraphStyle("quote", parent=base["BodyText"], fontName=BODY, fontSize=9.5,
                            leading=13, backColor=LIGHT, borderColor=ACCENT,
                            borderWidth=0, borderPadding=6, leftIndent=6,
                            spaceBefore=4, spaceAfter=8),
    "cell": ParagraphStyle("cell", fontName=BODY, fontSize=8.5, leading=11),
    "hcell": ParagraphStyle("hcell", fontName=BOLD, fontSize=8.5, leading=11,
                            textColor=colors.white),
    "code": ParagraphStyle("code", fontName=MONO, fontSize=7.8, leading=10,
                           backColor=colors.HexColor("#F4F4F4"), borderPadding=6,
                           borderColor=colors.HexColor("#CCCCCC"), borderWidth=0.5,
                           spaceBefore=4, spaceAfter=10, leftIndent=4, rightIndent=4),
}


def inline(text: str) -> str:
    """Convert inline Markdown (code, bold, italic) to reportlab markup."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f'<font face="{MONO}" color="#A31515">{part[1:-1]}</font>')
        else:
            part = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", part)
            part = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", part)
            out.append(part)
    return "".join(out)


def make_table(rows: list[list[str]], width: float):
    header, body = rows[0], rows[1:]
    data = [[Paragraph(inline(c), S["hcell"]) for c in header]]
    data += [[Paragraph(inline(c), S["cell"]) for c in r] for r in body]
    n = len(header)
    if n == 2:
        widths = [width * 0.36, width * 0.64]
    elif n == 3:
        widths = [width * 0.18, width * 0.47, width * 0.35]
    else:
        widths = [width / n] * n
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B4C6E7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def parse(md: str, width: float) -> list:
    story: list = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            story.append(Preformatted("\n".join(buf), S["code"]))
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = lines[i].strip().strip("|").replace("\\|", "\x00")
                cells = [c.strip().replace("\x00", "|") for c in raw.split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            story += [make_table(rows, width), Spacer(1, 8)]
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", s)
        if m:
            level = len(m.group(1))
            story.append(Paragraph(inline(m.group(2)), S[f"h{level}"]))
            i += 1
            continue
        if s.startswith(">"):
            story.append(Paragraph(inline(s.lstrip("> ")), S["quote"]))
            i += 1
            continue
        list_match = re.match(r"^(\s*)(-|\d+\.)\s+", line)
        if list_match:
            ordered = list_match.group(2) != "-"
            items = []
            while i < len(lines):
                lm = re.match(r"^(\s*)(-|\d+\.)\s+(.*)", lines[i])
                if not lm:
                    break
                indent = len(lm.group(1))
                style = ParagraphStyle("li", parent=S["p"], spaceAfter=2,
                                       leftIndent=indent * 4)
                prefix = "– " if indent else ""
                items.append(ListItem(Paragraph(prefix + inline(lm.group(3)), style),
                                      leftIndent=12 + indent * 4))
                i += 1
            story.append(ListFlowable(
                items,
                bulletType="1" if ordered else "bullet",
                start="1" if ordered else "•",
                bulletFontName=BODY, bulletFontSize=9, leftIndent=12,
                bulletColor=ACCENT,
            ))
            story.append(Spacer(1, 4))
            continue
        story.append(Paragraph(inline(s), S["p"]))
        i += 1
    return story


def page_decorator(header: str):
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(0.6)
        canvas.line(18 * mm, 287 * mm, 192 * mm, 287 * mm)
        canvas.setFont(BODY, 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 289 * mm, header)
        canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    return on_page


def build(name: str) -> Path:
    source, output, header, title = DOCS[name]
    out = HERE / output
    doc = SimpleDocTemplate(
        str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=title, author="RealBasket Team",
    )
    story = parse((HERE / source).read_text(encoding="utf-8"), doc.width)
    on_page = page_decorator(header)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return out


def main(argv: list[str]) -> None:
    names = argv or list(DOCS)
    unknown = [n for n in names if n not in DOCS]
    if unknown:
        raise SystemExit(f"unknown document(s): {', '.join(unknown)} - choose from {', '.join(DOCS)}")
    for name in names:
        print(f"written: {build(name)}")


if __name__ == "__main__":
    main(sys.argv[1:])

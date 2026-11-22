"""Plain, text-based resume PDF built only from approved profile data."""

import io
from collections import defaultdict
from html import escape


SECTION_NAMES = {"experience": "Experience", "project": "Projects", "education": "Education", "skill": "Skills"}


def render_resume_pdf(profile: dict[str, str], facts: list[dict], suggestions: list[dict], selected_ids: set[str]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    approved = {item["id"]: item["after"] for item in suggestions if item["id"] in selected_ids}
    grouped: dict[str, list[tuple[int, str]]] = defaultdict(list)
    rank = {item["id"]: index for index, item in enumerate(suggestions)}
    for index, fact in enumerate(facts):
        if fact["kind"] in SECTION_NAMES:
            order = rank.get(fact["id"], len(facts) + index) if fact["kind"] in {"project", "skill"} else index
            grouped[fact["kind"]].append((order, approved.get(fact["id"], fact["value"])))
    if not any(grouped.values()):
        raise ValueError("No approved career facts are available for export")

    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=letter, leftMargin=48, rightMargin=48, topMargin=46, bottomMargin=46,
                                 title=f"{profile['fullName']} - Resume", author=profile["fullName"])
    name_style = ParagraphStyle("Name", fontName="Helvetica-Bold", fontSize=17, leading=21, alignment=TA_LEFT, textColor=colors.HexColor("#182333"), spaceAfter=6)
    contact_style = ParagraphStyle("Contact", fontName="Helvetica", fontSize=9, leading=13, textColor=colors.HexColor("#263747"), spaceAfter=14)
    heading_style = ParagraphStyle("Heading", fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceBefore=11, spaceAfter=5,
                                   textColor=colors.HexColor("#182333"))
    body_style = ParagraphStyle("Body", fontName="Helvetica", fontSize=9.5, leading=13.5, spaceAfter=5, leftIndent=12, firstLineIndent=-9)

    story = [Paragraph(escape(profile["fullName"]), name_style)]
    contact = [profile.get(key, "") for key in ("email", "phone", "city", "country", "linkedin", "github")]
    story.append(Paragraph(" | ".join(escape(item) for item in contact if item), contact_style))
    for kind in ("experience", "project", "education", "skill"):
        values = sorted(grouped.get(kind, []))
        if not values:
            continue
        story.append(Paragraph(SECTION_NAMES[kind], heading_style))
        for _rank, value in values:
            story.append(Paragraph("- " + escape(value).replace("\n", "<br/>"), body_style))
        story.append(Spacer(1, 2))

    def footer(canvas, page):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5a6876"))
        canvas.drawRightString(letter[0] - 48, 27, str(document.page))
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak, KeepTogether
from reportlab.platypus.flowables import Flowable
from datetime import datetime

MINT      = HexColor("#5DE6B3")
TEAL      = HexColor("#4BACA7")
DARK_TEAL = HexColor("#255B53")
BG_DARK   = HexColor("#080C0B")
BG_SURFACE= HexColor("#0E1512")
BG_CARD   = HexColor("#141C19")
WHITE     = HexColor("#F0F7F4")
MUTED     = HexColor("#5A7A71")
DANGER    = HexColor("#FF4D6D")
WARNING   = HexColor("#FFB347")
SUCCESS   = MINT
BORDER    = HexColor("#D0E4DC")
BODY_TEXT = HexColor("#1A2420")

SEVERITY_COLOR = {"critical": DANGER, "warning": WARNING, "pass": SUCCESS}
SEVERITY_LABEL = {"critical": "CRITICAL", "warning": "WARNING", "pass": "PASS"}
STATUS_COLOR   = {"critical": DANGER, "warning": WARNING, "good": SUCCESS}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def _draw_wrapped(c, text, x, y, max_width, font_size, line_h=12, font="Helvetica"):
    words = text.split()
    line = ""
    lines = []
    c.setFont(font, font_size)
    for word in words:
        test = (line + " " + word).strip()
        if c.stringWidth(test, font, font_size) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    for i, l in enumerate(lines[:3]):
        c.drawString(x, y - i * line_h, l)


class IssueCard(Flowable):
    def __init__(self, issue, width, idx):
        Flowable.__init__(self)
        self.issue = issue
        self.width = width
        self.idx = idx

    def wrap(self, availW, availH):
        return self.width, 95

    def draw(self):
        c = self.canv
        issue = self.issue
        severity = issue.get("severity", "pass")
        sev_color = SEVERITY_COLOR.get(severity, MUTED)
        sev_label = SEVERITY_LABEL.get(severity, severity.upper())
        w = self.width
        h = 88
        c.setFillColor(HexColor("#F8FDFB"))
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 5, fill=1, stroke=1)
        c.setFillColor(sev_color)
        c.roundRect(0, 0, 5, h, 3, fill=1, stroke=0)
        badge_x, badge_y = 14, h - 22
        c.setFillColor(sev_color)
        c.roundRect(badge_x, badge_y, 60, 16, 3, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(badge_x + 6, badge_y + 4, sev_label)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7)
        c.drawRightString(w - 10, h - 14, f"#{self.idx}")
        c.setFillColor(BODY_TEXT)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(badge_x, badge_y - 14, issue.get("title", "")[:70])
        c.setFillColor(HexColor("#3A5A50"))
        c.setFont("Helvetica", 8)
        _draw_wrapped(c, issue.get("detail", "")[:120], badge_x, badge_y - 28, w - badge_x - 10, 8, line_h=11)
        fix = issue.get("fix", "")[:120]
        if fix:
            c.setFillColor(DARK_TEAL)
            c.setFont("Helvetica-BoldOblique", 7.5)
            c.drawString(badge_x, 13, "FIX: ")
            c.setFont("Helvetica-Oblique", 7.5)
            c.setFillColor(HexColor("#255B53"))
            _draw_wrapped(c, fix, badge_x + 28, 13, w - badge_x - 38, 7.5, line_h=10)
        impact = issue.get("impact", "")
        effort = issue.get("effort", "")
        if impact:
            chip_color = DANGER if impact == "high" else (WARNING if impact == "medium" else MUTED)
            c.setFillColor(chip_color)
            c.roundRect(w - 120, 2, 52, 12, 3, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawString(w - 117, 5, f"IMPACT: {impact.upper()}")
        if effort:
            chip_color = SUCCESS if effort == "easy" else (WARNING if effort == "medium" else DANGER)
            c.setFillColor(chip_color)
            c.roundRect(w - 62, 2, 52, 12, 3, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont("Helvetica-Bold", 6.5)
            c.drawString(w - 59, 5, f"EFFORT: {effort.upper()}")


def make_page_template(canvas_obj, doc, domain):
    canvas_obj.saveState()
    canvas_obj.setFillColor(BG_DARK)
    canvas_obj.rect(0, PAGE_H - 18*mm, PAGE_W, 18*mm, fill=1, stroke=0)
    canvas_obj.setFillColor(MINT)
    canvas_obj.setFont("Helvetica-Bold", 10)
    canvas_obj.drawString(MARGIN, PAGE_H - 11*mm, "SNAPSHOT")
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica", 10)
    canvas_obj.drawString(MARGIN + 58, PAGE_H - 11*mm, "AI")
    canvas_obj.setFillColor(MUTED)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawRightString(PAGE_W - MARGIN, PAGE_H - 11*mm, f"Website Intelligence Report · {domain}")
    canvas_obj.setFillColor(BORDER)
    canvas_obj.rect(0, 0, PAGE_W, 12*mm, fill=1, stroke=0)
    canvas_obj.setFillColor(MUTED)
    canvas_obj.setFont("Helvetica", 7.5)
    canvas_obj.drawString(MARGIN, 4*mm, f"Generated {datetime.now().strftime('%B %d, %Y')} · Confidential · SnapshotAI")
    canvas_obj.drawRightString(PAGE_W - MARGIN, 4*mm, f"Page {doc.page}")
    canvas_obj.restoreState()


def get_styles():
    return {
        "section_label": ParagraphStyle("sl", fontName="Helvetica-Bold", fontSize=7.5, textColor=TEAL, leading=10, spaceAfter=4, spaceBefore=16, letterSpacing=1.5),
        "section_title": ParagraphStyle("st", fontName="Helvetica-Bold", fontSize=18, textColor=BODY_TEXT, leading=22, spaceAfter=6),
        "body": ParagraphStyle("b", fontName="Helvetica", fontSize=9.5, textColor=BODY_TEXT, leading=15, spaceAfter=6, alignment=TA_JUSTIFY),
        "cat_title": ParagraphStyle("ct", fontName="Helvetica-Bold", fontSize=13, textColor=BODY_TEXT, leading=16, spaceAfter=3),
        "cat_summary": ParagraphStyle("cs", fontName="Helvetica-Oblique", fontSize=9, textColor=MUTED, leading=13, spaceAfter=8),
        "win_title": ParagraphStyle("wt", fontName="Helvetica-Bold", fontSize=10, textColor=DARK_TEAL, leading=14, spaceAfter=2),
        "win_detail": ParagraphStyle("wd", fontName="Helvetica", fontSize=8.5, textColor=BODY_TEXT, leading=13, spaceAfter=2),
        "win_meta": ParagraphStyle("wm", fontName="Helvetica-Bold", fontSize=7.5, textColor=TEAL, leading=11, spaceAfter=0),
        "roadmap_week": ParagraphStyle("rw", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE, leading=12),
        "roadmap_focus": ParagraphStyle("rf", fontName="Helvetica-Bold", fontSize=10, textColor=BODY_TEXT, leading=14, spaceAfter=3),
        "roadmap_item": ParagraphStyle("ri", fontName="Helvetica", fontSize=8.5, textColor=HexColor("#3A5A50"), leading=13, spaceAfter=1),
        "disclaimer": ParagraphStyle("d", fontName="Helvetica-Oblique", fontSize=7.5, textColor=MUTED, leading=11, alignment=TA_CENTER),
    }


def build_cover(story, scraped, analysis, styles):
    domain = scraped["domain"]
    score  = analysis["overall_score"]
    grade  = analysis["grade"]
    story.append(Spacer(1, 8*mm))
    badge_t = Table([["  WEBSITE INTELLIGENCE REPORT  "]], colWidths=[80*mm])
    badge_t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),DARK_TEAL),("TEXTCOLOR",(0,0),(-1,-1),MINT),("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),("ALIGN",(0,0),(-1,-1),"CENTER"),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
    story.append(badge_t)
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(domain, ParagraphStyle("cd", fontName="Helvetica-Bold", fontSize=28, textColor=WHITE, leading=32, spaceAfter=4)))
    story.append(Paragraph(f"Prepared {datetime.now().strftime('%B %d, %Y')}", ParagraphStyle("cg", fontName="Helvetica", fontSize=13, textColor=MUTED, leading=18, spaceAfter=20)))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8*mm))
    score_color = DANGER if score < 40 else (WARNING if score < 70 else MINT)
    grade_color = DANGER if grade in ("D","F") else (WARNING if grade == "C" else MINT)
    content_width = PAGE_W - 2*MARGIN
    metrics_t = Table([[
        Table([[Paragraph("OVERALL SCORE", ParagraphStyle("x", fontName="Helvetica-Bold", fontSize=7, textColor=MUTED, letterSpacing=1))],[Paragraph(str(score), ParagraphStyle("x2", fontName="Helvetica-Bold", fontSize=42, textColor=score_color, leading=46))],[Paragraph("out of 100", ParagraphStyle("x3", fontName="Helvetica", fontSize=8, textColor=MUTED))]], colWidths=[40*mm]),
        Table([[Paragraph("GRADE", ParagraphStyle("y", fontName="Helvetica-Bold", fontSize=7, textColor=MUTED, letterSpacing=1))],[Paragraph(grade, ParagraphStyle("y2", fontName="Helvetica-Bold", fontSize=42, textColor=grade_color, leading=46))],[Paragraph("letter grade", ParagraphStyle("y3", fontName="Helvetica", fontSize=8, textColor=MUTED))]], colWidths=[30*mm]),
        Table([[Paragraph("EST. MONTHLY REVENUE LOST", ParagraphStyle("z", fontName="Helvetica-Bold", fontSize=7, textColor=MUTED, letterSpacing=1))],[Paragraph(analysis.get("estimated_monthly_revenue_lost","—"), ParagraphStyle("z2", fontName="Helvetica-Bold", fontSize=16, textColor=DANGER, leading=22))],[Paragraph("based on issues found", ParagraphStyle("z3", fontName="Helvetica", fontSize=8, textColor=MUTED))]], colWidths=[content_width - 80*mm]),
    ]], colWidths=[43*mm, 33*mm, content_width - 80*mm])
    metrics_t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
    story.append(metrics_t)
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6*mm))
    story.append(Paragraph("EXECUTIVE SUMMARY", styles["section_label"]))
    story.append(Paragraph(analysis.get("executive_summary",""), styles["body"]))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("CATEGORY OVERVIEW", styles["section_label"]))
    cats = analysis.get("categories", [])
    half = len(cats) // 2
    rows = []
    for i in range(max(len(cats[:half]), len(cats[half:]))):
        row = []
        for side in [cats[:half], cats[half:]]:
            if i < len(side):
                cat = side[i]
                sc = cat["score"]
                col = DANGER if sc < 40 else (WARNING if sc < 70 else SUCCESS)
                row.append(f"{cat['icon']} {cat['name']}")
                row.append(Paragraph(f'<font color="#{col.hexval()}">{sc}</font>', ParagraphStyle("cs2", fontName="Helvetica-Bold", fontSize=11, textColor=BODY_TEXT)))
            else:
                row.extend(["", ""])
        rows.append(row)
    cat_t = Table(rows, colWidths=[65*mm, 14*mm, 65*mm, 14*mm])
    cat_t.setStyle(TableStyle([("FONTNAME",(0,0),(0,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),9),("TEXTCOLOR",(0,0),(0,-1),BODY_TEXT),("TEXTCOLOR",(2,0),(2,-1),BODY_TEXT),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("ROWBACKGROUNDS",(0,0),(-1,-1),[HexColor("#F4FAF7"),HexColor("#FFFFFF")])]))
    story.append(cat_t)
    story.append(PageBreak())


def build_category_page(story, cat, styles, content_width):
    status = cat.get("status","good")
    status_color = STATUS_COLOR.get(status, MUTED)
    ht = Table([[Paragraph(f"{cat['icon']} {cat['name']}", styles["cat_title"]), Paragraph(f'<font color="#{status_color.hexval()}">{cat["score"]}/100</font>', ParagraphStyle("cscore", fontName="Helvetica-Bold", fontSize=20, textColor=BODY_TEXT, alignment=TA_RIGHT))]], colWidths=[content_width*0.7, content_width*0.3])
    ht.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"BOTTOM"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story.append(ht)
    pill_t = Table([[f"  {status.upper()}  "]], colWidths=[24*mm])
    pill_t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),status_color),("TEXTCOLOR",(0,0),(-1,-1),white),("FONTNAME",(0,0),(-1,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(pill_t)
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(cat.get("summary",""), styles["cat_summary"]))
    story.append(HRFlowable(width="100%", thickness=0.4, color=BORDER, spaceAfter=4*mm))
    for idx, issue in enumerate(cat.get("issues", []), 1):
        story.append(IssueCard(issue, content_width, idx))
        story.append(Spacer(1, 3*mm))
    story.append(Spacer(1, 5*mm))


def build_quick_wins(story, analysis, styles, content_width):
    story.append(Paragraph("QUICK WINS", styles["section_label"]))
    story.append(Paragraph("Fix These First", styles["section_title"]))
    story.append(Paragraph("Highest-impact, lowest-effort improvements. Implement them this week.", styles["body"]))
    story.append(Spacer(1, 4*mm))
    for i, win in enumerate(analysis.get("quick_wins", [])):
        bg = HexColor("#F0FBF6") if i % 2 == 0 else HexColor("#FAFFFE")
        inner = Table([[Paragraph(f"#{i+1}  {win['title']}", styles["win_title"])],[Paragraph(win.get("detail",""), styles["win_detail"])],[Paragraph(f"Time: {win.get('time_to_fix','—')}   Impact: {win.get('expected_impact','')}", styles["win_meta"])]], colWidths=[content_width - 6*mm])
        inner.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),4*mm),("RIGHTPADDING",(0,0),(-1,-1),2*mm),("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2),("BACKGROUND",(0,0),(-1,-1),bg)]))
        story.append(inner)
        story.append(Spacer(1, 2.5*mm))
    story.append(PageBreak())


def build_roadmap(story, analysis, styles, content_width):
    story.append(Paragraph("PRIORITY ROADMAP", styles["section_label"]))
    story.append(Paragraph("Your 30-Day Action Plan", styles["section_title"]))
    story.append(Spacer(1, 4*mm))
    week_colors = [MINT, TEAL, DARK_TEAL]
    for i, week in enumerate(analysis.get("priority_roadmap", [])):
        color = week_colors[i % len(week_colors)]
        col_w = 28*mm
        week_label = Table([[Paragraph(f"WEEK {week['week']}", styles["roadmap_week"])]], colWidths=[col_w])
        week_label.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),color),("TOPPADDING",(0,0),(-1,-1),3*mm),("BOTTOMPADDING",(0,0),(-1,-1),3*mm),("LEFTPADDING",(0,0),(-1,-1),4*mm)]))
        items_content = [[Paragraph(week.get("focus",""), styles["roadmap_focus"])]]
        for item in week.get("items", []):
            items_content.append([Paragraph(f"• {item}", styles["roadmap_item"])])
        items_table = Table(items_content, colWidths=[content_width - col_w - 5*mm])
        items_table.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),4*mm),("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
        row_t = Table([[week_label, items_table]], colWidths=[col_w+3*mm, content_width-col_w-3*mm])
        row_t.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),("BACKGROUND",(1,0),(1,0),HexColor("#F4FAF7")),("BOX",(0,0),(-1,-1),0.4,BORDER)]))
        story.append(row_t)
        story.append(Spacer(1, 3*mm))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("COMPETITIVE RISK ASSESSMENT", styles["section_label"]))
    story.append(Paragraph(analysis.get("competitive_risks",""), styles["body"]))
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=0.3, color=BORDER, spaceAfter=4*mm))
    story.append(Paragraph("This report was generated by SnapshotAI using automated website analysis and AI interpretation. Findings are based on publicly accessible data at the time of scan. Revenue impact estimates are approximations based on industry benchmarks.", styles["disclaimer"]))


def generate_pdf_report(scraped: dict, analysis: dict, output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=22*mm, bottomMargin=16*mm, title=f"SnapshotAI Report — {scraped['domain']}", author="SnapshotAI")
    content_width = PAGE_W - 2*MARGIN
    domain = scraped["domain"]
    def on_page(canvas_obj, doc):
        make_page_template(canvas_obj, doc, domain)
    styles = get_styles()
    story  = []
    build_cover(story, scraped, analysis, styles)
    story.append(Paragraph("DETAILED FINDINGS", styles["section_label"]))
    story.append(Paragraph("Category-by-Category Breakdown", styles["section_title"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=5*mm))
    for cat in analysis.get("categories", []):
        story.append(KeepTogether([Spacer(1, 2*mm)]))
        build_category_page(story, cat, styles, content_width)
    story.append(PageBreak())
    build_quick_wins(story, analysis, styles, content_width)
    build_roadmap(story, analysis, styles, content_width)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return output_path

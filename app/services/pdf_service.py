import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class PDFGenerator:
    @staticmethod
    def generate_report(session_id: int, title: str, summary: str, defects_summary: dict) -> str:
        reports_dir = os.path.abspath("generated_reports")
        os.makedirs(reports_dir, exist_ok=True)
        filename = f"Inspection_Report_{session_id}.pdf"
        filepath = os.path.join(reports_dir, filename)

        doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('ReportTitle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#0f172a'))
        story.append(Paragraph(f"InspeXion AI - Asset Audit Report", title_style))
        story.append(Spacer(1, 10))

        story.append(Paragraph(f"<b>Session ID:</b> #{session_id} | <b>Title:</b> {title}", styles['Normal']))
        story.append(Spacer(1, 15))

        data = [
            ["Metric", "Value"],
            ["Total Images Examined", str(defects_summary.get("total_images", 0))],
            ["Critical Defects", str(defects_summary.get("critical", 0))],
            ["Minor Defects", str(defects_summary.get("minor", 0))],
            ["Overall Status", "PASSED" if defects_summary.get("critical", 0) == 0 else "ATTENTION REQUIRED"]
        ]
        t = Table(data, colWidths=[200, 250])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 20))

        story.append(Paragraph("<b>Analysis & Risk Summary:</b>", styles['Heading2']))
        story.append(Spacer(1, 8))

        for line in summary.split("\n"):
            if line.strip():
                story.append(Paragraph(line.replace("<", "&lt;").replace(">", "&gt;"), styles['Normal']))
                story.append(Spacer(1, 4))

        doc.build(story)
        return filepath

pdf_generator = PDFGenerator()
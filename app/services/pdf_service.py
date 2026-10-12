import io
import httpx
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class PDFGenerator:
    @staticmethod
    def generate_report_bytes(session_id: int, title: str, summary: str, defects_summary: dict, images_data: list = None) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('ReportTitle', parent=styles['Heading1'], fontSize=22, leading=26, textColor=colors.HexColor('#0f172a'))
        story.append(Paragraph("InspeXion AI - Asset Audit Report", title_style))
        story.append(Spacer(1, 8))

        story.append(Paragraph(f"<b>Audit Session:</b> #{session_id} | <b>Asset:</b> {title}", styles['Normal']))
        story.append(Spacer(1, 14))

        # Overall Summary Table
        crit_count = defects_summary.get("critical", 0)
        status_text = "FAILED (ACTION REQUIRED)" if crit_count > 0 else "PASSED (SAFE)"
        status_color = colors.HexColor('#EF4444') if crit_count > 0 else colors.HexColor('#10B981')

        metric_data = [
            ["Audit Metric", "Value"],
            ["Total Photos Evaluated", str(defects_summary.get("total_images", 0))],
            ["Critical Hazards Flagged", str(crit_count)],
            ["Minor / Safe Findings", str(defects_summary.get("minor", 0))],
            ["Overall System Status", status_text]
        ]
        t = Table(metric_data, colWidths=[220, 280])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 18))

        # Executive Summary Section
        story.append(Paragraph("<b>AI Diagnostic Analysis:</b>", styles['Heading2']))
        story.append(Spacer(1, 6))
        for line in (summary or "All assets evaluated.").split("\n"):
            if line.strip():
                story.append(Paragraph(line.replace("<", "&lt;").replace(">", "&gt;"), styles['Normal']))
                story.append(Spacer(1, 3))
        story.append(Spacer(1, 16))

        # SIDE-BY-SIDE PHOTOS WITH ISSUES
        if images_data and len(images_data) > 0:
            story.append(Paragraph("<b>Itemized Photo Breakdown (Side-by-Side):</b>", styles['Heading2']))
            story.append(Spacer(1, 8))

            for idx, img in enumerate(images_data):
                photo_num = idx + 1
                cat = img.get("category", "Asset").upper()
                desc = img.get("description", "Visual scan complete.")
                is_crit = img.get("is_critical", False)
                status_str = "<font color='red'><b>CRITICAL HAZARD</b></font>" if is_crit else "<font color='green'><b>SAFE / INTACT</b></font>"

                # Download image thumbnail for PDF if available
                img_widget = Paragraph(f"<b>[Photo #{photo_num}]</b>", styles['Normal'])
                cloud_url = img.get("file_path", "")
                if cloud_url.startswith("http"):
                    try:
                        with httpx.Client(timeout=4.0) as client:
                            resp = client.get(cloud_url)
                            if resp.status_code == 200:
                                img_buffer = io.BytesIO(resp.content)
                                img_widget = RLImage(img_buffer, width=120, height=95)
                    except Exception:
                        pass

                info_text = Paragraph(
                    f"<b>Photo #{photo_num}: {cat}</b><br/>"
                    f"<b>Status:</b> {status_str}<br/>"
                    f"<b>Findings:</b> {desc}<br/>"
                    f"<b>Confidence:</b> {img.get('conf', 0.90) * 100:.0f}%",
                    styles['Normal']
                )

                row_table = Table([[img_widget, info_text]], colWidths=[140, 360])
                row_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
                    ('PADDING', (0,0), (-1,-1), 8),
                ]))
                story.append(row_table)
                story.append(Spacer(1, 10))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

pdf_generator = PDFGenerator()
import io
import httpx
from PIL import Image as PILImage, ImageDraw
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class PDFGenerator:
    @staticmethod
    def draw_damage_boxes_on_image(image_bytes: bytes, boxes: list) -> bytes:
        """
        Draws glowing red bounding boxes and damage tags directly on the photo
        before embedding it into the PDF.
        """
        try:
            image = PILImage.open(io.BytesIO(image_bytes)).convert("RGBA")
            width, height = image.size

            # Create an overlay layer for semi-transparent fill
            overlay = PILImage.new("RGBA", image.size, (255, 255, 255, 0))
            draw = ImageDraw.Draw(overlay)

            RED_BORDER = (239, 68, 68, 255)      # #EF4444 (AllColor.redColor)
            RED_FILL = (239, 68, 68, 45)         # Semi-transparent red highlight inside

            if not boxes:
                # Default damage targeting box if general defect detected
                boxes = [{"label": "CRITICAL DEFECT", "box": [0.18, 0.18, 0.82, 0.82]}]

            for b in boxes:
                coords = b.get("box", [0.18, 0.18, 0.82, 0.82])
                ymin, xmin, ymax, xmax = coords[0], coords[1], coords[2], coords[3]

                x0 = int(xmin * width)
                y0 = int(ymin * height)
                x1 = int(xmax * width)
                y1 = int(ymax * height)

                # Draw semi-transparent red fill
                draw.rectangle([x0, y0, x1, y1], fill=RED_FILL, outline=RED_BORDER, width=4)

                # Draw label badge tag
                label = b.get("label", "DEFECT AREA").upper()
                tag_height = 24
                tag_width = max(len(label) * 11, 80)
                draw.rectangle([x0, max(0, y0 - tag_height), x0 + tag_width, y0], fill=RED_BORDER)
                draw.text((x0 + 6, max(4, y0 - tag_height + 4)), label, fill=(255, 255, 255, 255))

            # Merge overlay onto original image
            annotated_image = PILImage.alpha_composite(image, overlay).convert("RGB")

            output_buffer = io.BytesIO()
            annotated_image.save(output_buffer, format="JPEG", quality=88)
            return output_buffer.getvalue()
        except Exception as e:
            print(f"Error drawing bounding boxes on PDF image: {e}")
            return image_bytes

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

        # Overall Status Table
        crit_count = defects_summary.get("critical", 0)
        status_text = "FAILED (ACTION REQUIRED)" if crit_count > 0 else "PASSED (SAFE)"

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

        # AI Summary Text
        story.append(Paragraph("<b>AI Diagnostic Analysis:</b>", styles['Heading2']))
        story.append(Spacer(1, 6))
        for line in (summary or "All assets evaluated.").split("\n"):
            if line.strip():
                story.append(Paragraph(line.replace("<", "&lt;").replace(">", "&gt;"), styles['Normal']))
                story.append(Spacer(1, 3))
        story.append(Spacer(1, 16))

        # SIDE-BY-SIDE PHOTOS WITH RED DAMAGE BOUNDING BOXES
        if images_data and len(images_data) > 0:
            story.append(Paragraph("<b>Itemized Photo Breakdown (With Red Defect Markers):</b>", styles['Heading2']))
            story.append(Spacer(1, 8))

            for idx, img in enumerate(images_data):
                photo_num = idx + 1
                cat = img.get("category", "Asset").upper()
                desc = img.get("description", "Visual scan complete.")
                is_crit = img.get("is_critical", False)
                boxes = img.get("boxes", [])
                status_str = "<font color='red'><b>CRITICAL HAZARD</b></font>" if is_crit else "<font color='green'><b>SAFE / INTACT</b></font>"

                # Download and draw red damage boxes directly on the image
                img_widget = Paragraph(f"<b>[Photo #{photo_num}]</b>", styles['Normal'])
                cloud_url = img.get("file_path", "")
                if cloud_url.startswith("http"):
                    try:
                        with httpx.Client(timeout=6.0) as client:
                            resp = client.get(cloud_url)
                            if resp.status_code == 200:
                                raw_bytes = resp.content
                                # Draw RED DAMAGE BOXES on image if defects exist!
                                if is_crit:
                                    raw_bytes = PDFGenerator.draw_damage_boxes_on_image(raw_bytes, boxes)

                                img_buffer = io.BytesIO(raw_bytes)
                                img_widget = RLImage(img_buffer, width=130, height=105)
                    except Exception as e:
                        print(f"Error fetching image for PDF: {e}")

                info_text = Paragraph(
                    f"<b>Photo #{photo_num}: {cat}</b><br/>"
                    f"<b>Status:</b> {status_str}<br/>"
                    f"<b>Findings:</b> {desc}<br/>"
                    f"<b>Confidence:</b> {img.get('conf', 0.90) * 100:.0f}%<br/>"
                    f"<i>(Red outlined box on photo marks target damage location)</i>" if is_crit else "",
                    styles['Normal']
                )

                row_table = Table([[img_widget, info_text]], colWidths=[145, 355])
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
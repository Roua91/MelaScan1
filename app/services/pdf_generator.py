import os
from fpdf import FPDF
from PIL import Image as PILImage
from datetime import datetime
import json
from flask import current_app

class PDFGenerator:
    @staticmethod
    def generate_report_pdf(report, images):
        """Generate a professional PDF report with improved layout"""
        try:
            # Create PDF with better defaults
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            
            # Verify reports directory exists and is writable
            pdf_dir = os.path.join(
                current_app.config['UPLOAD_FOLDERS']['reports'], 
                str(report.patient_id))
            
            os.makedirs(pdf_dir, exist_ok=True)
            
            # Test directory writability
            test_file = os.path.join(pdf_dir, 'test.tmp')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
            except IOError as e:
                raise IOError(f"Cannot write to reports directory: {str(e)}")
            
            # Set document properties
            pdf.set_title(f"Medical Report #{report.id}")
            pdf.set_author("MelaScan System")
            pdf.set_creator("MelaScan Medical")
            
            # Add header
            PDFGenerator._add_header(pdf, report)
            
            # Add patient information section
            PDFGenerator._add_patient_info(pdf, report)
            
            # Add findings section
            PDFGenerator._add_findings(pdf, report)
            
            # Add image analysis section
            if images:
                PDFGenerator._add_image_analysis(pdf, images, report.model_used)
            
            # Add footer
            PDFGenerator._add_footer(pdf)
            
            # Save PDF with absolute path
            pdf_path = os.path.abspath(os.path.join(pdf_dir, f'report_{report.id}.pdf'))
            pdf.output(pdf_path)
            
            return pdf_path
            
        except Exception as e:
            current_app.logger.error(f"PDF Generation Error: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to generate PDF: {str(e)}")

    @staticmethod
    def _add_header(pdf, report):
        """Add header section to the PDF"""
        # Add logo
        logo_path = os.path.join(current_app.root_path, 'static/images/logo.png')
        if os.path.exists(logo_path):
            pdf.image(logo_path, x=10, y=8, w=30)
        
        # Set font for title
        pdf.set_font('Helvetica', 'B', 16)
        
        # Title
        pdf.set_xy(0, 10)
        pdf.cell(0, 10, 'MELANOMA DIAGNOSTIC REPORT', 0, 1, 'C')
        
        # Subtitle
        pdf.set_font('Helvetica', '', 12)
        pdf.cell(0, 6, f'Report #: {report.id}', 0, 1, 'C')
        
        # Date
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 6, f'Generated on: {report.generated_on.strftime("%Y-%m-%d %H:%M")}', 0, 1, 'C')
        
        # Line separator
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, 30, 200, 30)
        pdf.ln(10)

    @staticmethod
    def _add_patient_info(pdf, report):
        """Add patient information section"""
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 8, 'PATIENT INFORMATION', 0, 1, 'L', 1)
        pdf.ln(2)
        
        pdf.set_font('Helvetica', '', 10)
        
        # Patient info in two columns
        col_width = 90
        line_height = 6
        
        # Column 1
        pdf.cell(col_width, line_height, f'Name: {report.patient.name}', 0, 0)
        pdf.cell(col_width, line_height, f'Date of Birth: {report.patient.date_of_birth.strftime("%Y-%m-%d") if report.patient.date_of_birth else "N/A"}', 0, 1)
        
        # Column 2
        pdf.cell(col_width, line_height, f'Contact: {report.patient.contact_number}', 0, 0)
        pdf.cell(col_width, line_height, f'Gender: {report.patient.gender or "N/A"}', 0, 1)
        
        pdf.ln(8)

    @staticmethod
    def _add_findings(pdf, report):
        """Add clinical findings section"""
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 8, 'CLINICAL FINDINGS', 0, 1, 'L', 1)
        pdf.ln(2)
        
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 6, report.findings or "No findings reported")
        pdf.ln(8)
        
        # Model information
        pdf.set_font('Helvetica', 'I', 9)
        pdf.cell(0, 5, f'Analysis model used: {report.model_used.upper()}', 0, 1)
        pdf.ln(5)

    @staticmethod
    def _add_image_analysis(pdf, images, model_used):
        """Add image analysis section"""
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 8, 'IMAGE ANALYSIS', 0, 1, 'L', 1)
        pdf.ln(2)
        
        pdf.set_font('Helvetica', '', 9)
        
        for i, img in enumerate(images):
            # Start new page if needed (but try to fit 2 images per page)
            if i > 0 and i % 2 == 0:
                pdf.add_page()
                pdf.set_font('Helvetica', 'B', 12)
                pdf.cell(0, 8, 'IMAGE ANALYSIS (continued)', 0, 1)
                pdf.set_font('Helvetica', '', 9)
                pdf.ln(2)
            
            try:
                if not os.path.exists(img.file_path):
                    pdf.cell(0, 6, f"Image not found: {img.filename}", 0, 1)
                    continue
                    
                # Add image to PDF (smaller size to fit 2 per page)
                pil_img = PILImage.open(img.file_path)
                width, height = pil_img.size
                aspect = width / height
                new_width = 80  # Smaller width to fit 2 images
                new_height = new_width / aspect
                
                # Position image (alternate left/right)
                x_pos = 10 if i % 2 == 0 else 110
                y_pos = pdf.get_y()
                
                # Add image
                pdf.image(img.file_path, x=x_pos, y=y_pos, w=new_width, h=new_height)
                
                # Add image info to the right (or below if second column)
                info_x = x_pos + new_width + 5 if i % 2 == 0 else x_pos
                info_y = y_pos if i % 2 == 0 else y_pos + new_height + 2
                
                pdf.set_xy(info_x, info_y)
                pdf.cell(0, 5, f'Image {i+1}: {img.filename}', 0, 1)
                
                # Add analysis if available
                if img.analysis:
                    try:
                        analysis = json.loads(img.analysis)
                        confidence = analysis.get('confidence', 0) * 100
                        classification = analysis.get('classification', 'unknown').upper()
                        
                        # Set classification color
                        if classification == 'MALIGNANT':
                            pdf.set_text_color(255, 0, 0)  # Red
                        elif classification == 'BENIGN':
                            pdf.set_text_color(0, 128, 0)  # Green
                        
                        pdf.cell(0, 5, f'Result: {classification}', 0, 1)
                        pdf.set_text_color(0, 0, 0)  # Reset to black
                        pdf.cell(0, 5, f'Confidence: {confidence:.1f}%', 0, 1)
                        pdf.cell(0, 5, f'Model: {model_used.upper()}', 0, 1)
                    except (json.JSONDecodeError, KeyError) as e:
                        pdf.cell(0, 5, f"Error parsing analysis data", 0, 1)
                
                # Move to next position
                if i % 2 == 0:
                    pdf.set_xy(110, y_pos)  # Prepare right column
                else:
                    pdf.ln(10)  # Move down after second image
                
            except Exception as e:
                pdf.cell(0, 6, f"Error processing image: {str(e)}", 0, 1)
                current_app.logger.error(f"Error processing image {img.filename}: {str(e)}")

    @staticmethod
    def _add_footer(pdf):
        """Add footer to each page"""
        pdf.set_y(-15)
        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 10, f'Generated by MelaScan Medical Systems - Page {pdf.page_no()}', 0, 0, 'C')
import os
from fpdf import FPDF
from PIL import Image as PILImage
from datetime import datetime
import json
from flask import current_app

class PDFGenerator:
    @staticmethod
    def generate_report_pdf(report, images):
        """Generate a PDF report for the given report and images"""
        try:
            # Ensure reports directory exists
            pdf_dir = os.path.join(current_app.root_path, 'static/reports', str(report.patient_id))
            os.makedirs(pdf_dir, exist_ok=True)
            
            pdf = FPDF()
            pdf.add_page()
            
            # Report header
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, f'Medical Report - #{report.id}', 0, 1, 'C')
            pdf.ln(5)
            
            # Patient information (using safe attribute access)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, 'Patient Information', 0, 1)
            pdf.set_font('Arial', '', 10)
            pdf.cell(0, 6, f'Name: {getattr(report.patient, "name", "N/A")}', 0, 1)
            pdf.cell(0, 6, f'Date of Birth: {report.patient.date_of_birth.strftime("%Y-%m-%d") if hasattr(report.patient, "date_of_birth") else "N/A"}', 0, 1)
            pdf.cell(0, 6, f'Gender: {getattr(report.patient, "gender", "N/A")}', 0, 1)
            pdf.ln(5)
            
            # Patient information
            PDFGenerator._add_patient_info(pdf, report)
            
            # Report findings
            PDFGenerator._add_findings(pdf, report)
            
            # Image analysis
            if images:
                PDFGenerator._add_image_analysis(pdf, images, report.model_used)
            
            # Save PDF
            pdf_dir = os.path.join(current_app.root_path, 'static/reports', str(report.patient_id))
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_path = os.path.join(pdf_dir, f'report_{report.id}.pdf')
            pdf.output(pdf_path)
            
            return pdf_path
            
        except Exception as e:
            current_app.logger.error(f"Error generating PDF: {str(e)}")
            raise

    @staticmethod
    def _add_patient_info(pdf, report):
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Patient Information', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f'Name: {report.patient.name}', 0, 1)
        pdf.cell(0, 6, f'Date of Birth: {report.patient.date_of_birth.strftime("%Y-%m-%d") if report.patient.date_of_birth else "N/A"}', 0, 1)
        pdf.cell(0, 6, f'Gender: {report.patient.gender or "N/A"}', 0, 1)
        pdf.ln(5)

    @staticmethod
    def _add_findings(pdf, report):
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Findings', 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.multi_cell(0, 6, report.findings)
        pdf.ln(10)

    @staticmethod
    def _add_image_analysis(pdf, images, model_used):
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, 'Image Analysis', 0, 1)
        pdf.set_font('Arial', '', 8)
        
        for img in images:
            try:
                if not os.path.exists(img.file_path):
                    pdf.cell(0, 6, f"Image not found: {img.filename}", 0, 1)
                    continue
                    
                # Add image to PDF
                PDFGenerator._add_image_to_pdf(pdf, img)
                
                # Add analysis if available
                if img.analysis:
                    try:
                        PDFGenerator._add_analysis_to_pdf(pdf, img, model_used)
                    except (json.JSONDecodeError, KeyError) as e:
                        pdf.cell(0, 6, f"Error parsing analysis data: {str(e)}", 0, 1)
                
                pdf.ln(5)
            except Exception as e:
                pdf.cell(0, 6, f"Error processing image: {str(e)}", 0, 1)
                current_app.logger.error(f"Error processing image {img.filename}: {str(e)}")

    @staticmethod
    def _add_image_to_pdf(pdf, img):
        pil_img = PILImage.open(img.file_path)
        width, height = pil_img.size
        aspect = width / height
        new_width = 180
        new_height = new_width / aspect
        
        pdf.cell(0, 6, f'Image: {img.filename}', 0, 1)
        pdf.image(img.file_path, x=10, y=None, w=new_width, h=new_height)
        pdf.ln(2)

    @staticmethod
    def _add_analysis_to_pdf(pdf, img, model_used):
        analysis = json.loads(img.analysis)
        confidence = analysis.get('confidence', 0) * 100
        classification = analysis.get('classification', 'unknown')
        
        # Set classification color
        if classification.lower() == 'malignant':
            classification_color = '255, 0, 0'  # Red
        elif classification.lower() == 'benign':
            classification_color = '0, 128, 0'  # Green
        else:
            classification_color = '128, 128, 128'  # Gray
        
        pdf.set_text_color(0, 0, 0)  # Black for text
        pdf.cell(0, 6, f"Model: {model_used.upper()}", 0, 1)
        pdf.cell(0, 6, f"Confidence: {confidence:.1f}%", 0, 1)
        
        # Classification with color
        pdf.set_text_color(*[int(c) for c in classification_color.split(',')])
        pdf.cell(0, 6, f"Classification: {classification.upper()}", 0, 1)
        pdf.set_text_color(0, 0, 0)  # Reset to black
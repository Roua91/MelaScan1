from flask import render_template, current_app
from weasyprint import HTML
import os
from datetime import datetime

def generate_report_pdf(report):
    """Generate PDF from report data"""
    # Render HTML template
    html = render_template('reports/pdf_template.html', report=report)
    
    # Create unique filename
    pdf_filename = f"report_{report.id}_{datetime.now().strftime('%Y%m%d')}.pdf"
    pdf_path = os.path.join(current_app.root_path, 'static/reports', pdf_filename)
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    
    # Generate PDF
    HTML(string=html).write_pdf(pdf_path)
    
    return pdf_path, pdf_filename
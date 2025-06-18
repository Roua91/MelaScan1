from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from werkzeug.utils import secure_filename
from datetime import datetime
from PIL import Image as PILImage
from io import BytesIO
import uuid
import os
import json
import traceback

# Import models and services
from app.models import Patient, Report, Image, UserClinicMap, PatientClinicMap
from app.extensions import db
from app.services.ai_service import ai_service
from app.services.pdf_generator import PDFGenerator


# Create blueprint
doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_doctor_clinics():
    """Get list of clinic IDs assigned to the current doctor"""
    return [ua.clinic_id for ua in current_user.clinic_assignments]

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# =============================================================================
# DASHBOARD AND PATIENT VIEWS
# =============================================================================

@doctor_bp.route('/dashboard')
@login_required
def dashboard():
    """Doctor dashboard with patient search and recent reports"""
    search_query = request.args.get('q', '')
    clinic_ids = get_doctor_clinics()
    
    # Build patients query with clinic filter
    patients_query = Patient.query.join(
        PatientClinicMap
    ).filter(
        PatientClinicMap.clinic_id.in_(clinic_ids)
    )
    
    # Add search filter if provided
    if search_query:
        patients_query = patients_query.filter(
            Patient.name.ilike(f'%{search_query}%') |
            Patient.contact_number.ilike(f'%{search_query}%')
        )
    
    patients = patients_query.order_by(Patient.name).all()
    
    # Get recent reports for this doctor
    recent_reports = Report.query.filter_by(
        doctor_id=current_user.id
    ).order_by(
        Report.generated_on.desc()
    ).limit(5).all()
    
    return render_template('doctor/dashboard.html',
                        patients=patients,
                        recent_reports=recent_reports,
                        search_query=search_query)

@doctor_bp.route('/patients/<int:patient_id>')
@login_required
def view_patient(patient_id):
    """View patient details with reports and images"""
    clinic_ids = get_doctor_clinics()
    
    # Verify patient access through clinic membership
    patient = Patient.query.join(
        PatientClinicMap
    ).filter(
        PatientClinicMap.clinic_id.in_(clinic_ids),
        Patient.id == patient_id
    ).first_or_404()
    
    # Get patient's reports by this doctor
    reports = Report.query.filter_by(
        patient_id=patient_id,
        doctor_id=current_user.id
    ).order_by(
        Report.generated_on.desc()
    ).all()
    
    # Get patient's images
    images = Image.query.filter_by(
        patient_id=patient_id
    ).all()
    
    return render_template('doctor/view_patient.html',
                        patient=patient,
                        reports=reports,
                        images=images)

# =============================================================================
# AI IMAGE ANALYSIS ENDPOINTS
# =============================================================================


@doctor_bp.route('/api/analyze', methods=['POST'])
@login_required
def analyze_image_api():
    """API endpoint for image analysis"""
    if 'image' not in request.files:
        return jsonify({'status': 'error', 'message': 'No image provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
    
    try:
        # Create temp directory
        temp_dir = os.path.join(current_app.instance_path, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Save temporarily with unique filename
        temp_filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        temp_path = os.path.join(temp_dir, temp_filename)
        file.save(temp_path)
        
        # Analyze with ResNet model
        result = ai_service.analyze_image(temp_path)
        
        # Clean up
        try:
            os.remove(temp_path)
        except:
            pass
        
        return jsonify(result)
        
    except Exception as e:
        current_app.logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@doctor_bp.route('/patient/<int:patient_id>/analyze', methods=['POST'])
@login_required
def analyze_patient_image(patient_id):
    """Analyze existing patient image"""
    image_id = request.form.get('image_id')
    if not image_id:
        return jsonify({'error': 'Image ID required'}), 400
        
    try:
        # Get and verify image (assuming you have Image model)
        image = Image.query.get_or_404(image_id)
        
        if image.patient_id != patient_id:
            return jsonify({'error': 'Unauthorized'}), 403
            
        # Analyze image
        result = ai_service.analyze_image(image.file_path)
        
        if result.get('status') == 'error':
            return jsonify({'error': result.get('message', 'Analysis failed')}), 500
            
        analysis = result.get('analysis', {})
        return jsonify({
            'diagnosis': analysis.get('classification'),
            'confidence': analysis.get('confidence'),
            'probabilities': analysis.get('probabilities', {}),
            'model': analysis.get('model_used'),
            'version': analysis.get('model_version')
        })
        
    except Exception as e:
        current_app.logger.error(f"Patient image analysis error: {str(e)}")
        return jsonify({'error': 'Analysis failed'}), 500

@doctor_bp.route('/api/model_info')
@login_required
def model_info():
    """Get AI model information"""
    try:
        model_info_data = ai_service.get_model_info()
        return jsonify({
            'status': 'success',
            'model': {
                'name': 'ResNet50 Melanoma Detection',
                'architecture': 'ResNet50 with custom classification head',
                'parameters': model_info_data.get('total_parameters', 'Unknown'),
                'input_size': '224x224 RGB',
                'classes': ['benign', 'malignant'],
                'device': model_info_data.get('device', 'Unknown')
            }
        })
    except Exception as e:
        current_app.logger.error(f"Model info error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# =============================================================================
# REPORT MANAGEMENT
# =============================================================================

@doctor_bp.route('/reports/create/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def create_report(patient_id):
    """Create a new report for a patient"""
    clinic_ids = get_doctor_clinics()
    
    # Verify patient access
    patient = Patient.query.join(
        PatientClinicMap
    ).filter(
        PatientClinicMap.clinic_id.in_(clinic_ids),
        Patient.id == patient_id
    ).first_or_404()

    if request.method == 'POST':
        try:
            # Validate required fields
            if not request.form.get('findings'):
                flash('Findings field is required', 'danger')
                return redirect(url_for('doctor.create_report', patient_id=patient_id))

            # Create report
            report = Report(
                patient_id=patient_id,
                doctor_id=current_user.id,
                findings=request.form['findings'],
                model_used=request.form.get('model', 'resnet_cbam'),
                generated_on=datetime.utcnow()
            )
            db.session.add(report)
            db.session.flush()  # Get report ID

            # Handle image uploads
            upload_dir = os.path.join(
                current_app.config.get('UPLOAD_FOLDERS', {}).get('patient_images', 
                    os.path.join(current_app.instance_path, 'uploads', 'patient_images')),
                str(patient_id)
            )
            os.makedirs(upload_dir, exist_ok=True)

            saved_images = []
            for file in request.files.getlist('images'):
                if file and allowed_file(file.filename):
                    # Generate unique filename
                    filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                    filepath = os.path.join(upload_dir, filename)
                    
                    # Save file
                    file.save(filepath)
                    
                    # Create image record
                    image = Image(
                        patient_id=patient_id,
                        report_id=report.id,
                        filename=filename,
                        file_path=filepath,
                        uploaded_by=current_user.id,
                        uploaded_on=datetime.utcnow()
                    )
                    db.session.add(image)
                    saved_images.append(filename)

            if not saved_images:
                raise ValueError("At least one valid image is required")

            # Generate PDF report
            try:
                images = Image.query.filter_by(report_id=report.id).all()
                pdf_path = PDFGenerator.generate_report_pdf(report, images)
                report.pdf_path = pdf_path
                current_app.logger.info(f"PDF report generated: {pdf_path}")
            except Exception as pdf_error:
                current_app.logger.error(f"PDF generation failed: {str(pdf_error)}")
                flash('Report saved but PDF generation failed', 'warning')

            db.session.commit()
            flash('Report created successfully!', 'success')
            return redirect(url_for('doctor.view_patient', patient_id=patient_id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Report creation error: {str(e)}", exc_info=True)
            flash(f'Error creating report: {str(e)}', 'danger')

    return render_template('doctor/create_report.html', 
                        patient=patient,
                        models=getattr(ai_service, 'models', {}).keys())

@doctor_bp.route('/reports/save/<int:patient_id>', methods=['POST'])
@login_required
def save_report(patient_id):
    """Save report via AJAX"""
    form = FlaskForm()  # For CSRF validation
    
    # Validate CSRF
    if not form.validate_on_submit():
        return jsonify({
            'success': False, 
            'message': 'CSRF token missing or invalid'
        }), 400
    
    try:
        # Verify patient access
        clinic_ids = get_doctor_clinics()
        patient = Patient.query.join(PatientClinicMap).filter(
            PatientClinicMap.clinic_id.in_(clinic_ids),
            Patient.id == patient_id
        ).first_or_404()

        # Validate required fields
        if 'findings' not in request.form:
            raise ValueError("Findings field is required")

        # Create report
        report = Report(
            patient_id=patient_id,
            doctor_id=current_user.id,
            findings=request.form['findings'],
            model_used=request.form.get('model', 'resnet_cbam'),
            generated_on=datetime.utcnow()
        )
        db.session.add(report)
        db.session.flush()

        # Handle image uploads
        upload_dir = os.path.join(
            current_app.config.get('UPLOAD_FOLDERS', {}).get('patient_images',
                os.path.join(current_app.instance_path, 'uploads', 'patient_images')),
            str(patient_id)
        )
        os.makedirs(upload_dir, exist_ok=True)

        saved_images = []
        for file in request.files.getlist('images'):
            if file and allowed_file(file.filename):
                filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                
                image = Image(
                    patient_id=patient_id,
                    report_id=report.id,
                    filename=filename,
                    file_path=filepath,
                    uploaded_by=current_user.id,
                    uploaded_on=datetime.utcnow()
                )
                db.session.add(image)
                saved_images.append(filename)

        if not saved_images:
            raise ValueError("At least one valid image is required")

        # Generate PDF
        try:
            images = Image.query.filter_by(report_id=report.id).all()
            pdf_path = PDFGenerator.generate_report_pdf(report, images)
            report.pdf_path = pdf_path
        except Exception as pdf_error:
            current_app.logger.error(f"PDF generation failed: {str(pdf_error)}")
            db.session.rollback()
            raise ValueError(f"PDF generation failed: {str(pdf_error)}")

        db.session.commit()

        return jsonify({
            'success': True,
            'report_id': report.id,
            'pdf_path': report.pdf_path,
            'redirect': url_for('doctor.view_patient', patient_id=patient_id)
        })

    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        current_app.logger.error(f"Report save failed: {error_msg}", exc_info=True)
        return jsonify({
            'success': False, 
            'message': error_msg,
            'error_type': 'pdf_generation' if 'PDF' in error_msg else 'general'
        }), 400

@doctor_bp.route('/reports/<int:report_id>')
@login_required
def view_report(report_id):
    """View a specific report"""
    report = Report.query.options(
        db.joinedload(Report.patient),
        db.joinedload(Report.doctor)
    ).filter_by(
        id=report_id,
        doctor_id=current_user.id
    ).first_or_404()
    
    images = Image.query.filter_by(report_id=report_id).all()
    
    return render_template('doctor/view_report.html',
                        report=report,
                        images=images)

@doctor_bp.route('/reports/<int:report_id>/download')
@login_required
def download_report(report_id):
    """Download PDF report"""
    report = Report.query.filter_by(
        id=report_id,
        doctor_id=current_user.id
    ).first_or_404()
    
    # Regenerate PDF if missing
    if not report.pdf_path or not os.path.exists(report.pdf_path):
        try:
            images = Image.query.filter_by(report_id=report_id).all()
            pdf_path = PDFGenerator.generate_report_pdf(report, images)
            report.pdf_path = pdf_path
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"PDF regeneration failed: {str(e)}")
            flash('Could not generate PDF report', 'danger')
            return redirect(url_for('doctor.view_report', report_id=report_id))
    
    return send_from_directory(
        os.path.dirname(report.pdf_path),
        os.path.basename(report.pdf_path),
        as_attachment=True,
        mimetype='application/pdf'
    )

# =============================================================================
# IMAGE MANAGEMENT
# =============================================================================

@doctor_bp.route('/images/<int:patient_id>/<filename>')
@login_required
def serve_image(patient_id, filename):
    """Serve patient images with access control"""
    # Verify patient access
    clinic_ids = get_doctor_clinics()
    patient = Patient.query.join(PatientClinicMap).filter(
        PatientClinicMap.clinic_id.in_(clinic_ids),
        Patient.id == patient_id
    ).first_or_404()

    # Verify image exists
    image = Image.query.filter_by(
        patient_id=patient_id,
        filename=filename
    ).first_or_404()

    upload_dir = os.path.join(
        current_app.config.get('UPLOAD_FOLDERS', {}).get('patient_images',
            os.path.join(current_app.instance_path, 'uploads', 'patient_images')),
        str(patient_id)
    )

    return send_from_directory(upload_dir, filename)

@doctor_bp.route('/images/upload/<int:patient_id>', methods=['POST'])
@login_required
def upload_image(patient_id):
    """Upload images for a patient"""
    clinic_ids = get_doctor_clinics()

    # Verify patient access
    patient = Patient.query.join(
        PatientClinicMap
    ).filter(
        PatientClinicMap.clinic_id.in_(clinic_ids),
        Patient.id == patient_id
    ).first_or_404()

    if 'images' not in request.files:
        flash('No files selected', 'danger')
        return redirect(url_for('doctor.view_patient', patient_id=patient_id))

    files = request.files.getlist('images')
    if not files or files[0].filename == '':
        flash('No files selected', 'danger')
        return redirect(url_for('doctor.view_patient', patient_id=patient_id))

    try:
        upload_dir = os.path.join(
            current_app.config.get('UPLOAD_FOLDERS', {}).get('patient_images',
                os.path.join(current_app.instance_path, 'uploads', 'patient_images')),
            str(patient_id)
        )
        os.makedirs(upload_dir, exist_ok=True)

        for file in files:
            if file and allowed_file(file.filename):
                # Generate unique filename
                filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)

                # Create image record
                image = Image(
                    patient_id=patient_id,
                    filename=filename,
                    file_path=filepath.replace(os.sep, '/'),
                    uploaded_by=current_user.id,
                    uploaded_on=datetime.utcnow()
                )
                db.session.add(image)

        db.session.commit()
        flash('Images uploaded successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Image upload error: {str(e)}")
        flash(f'Error uploading images: {str(e)}', 'danger')

    return redirect(url_for('doctor.view_patient', patient_id=patient_id))
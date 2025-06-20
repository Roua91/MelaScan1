from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app, jsonify
from flask_login import login_required, current_user
from app.models import Patient, Report, Image, UserClinicMap, PatientClinicMap
from app.extensions import db
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid
import os
from flask_wtf import FlaskForm
import json
from app.services.ai_service import ai_service
from app.services.pdf_generator import PDFGenerator
import traceback


doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')


def get_doctor_clinics():
    """Get list of clinic IDs assigned to the current doctor"""
    return [ua.clinic_id for ua in current_user.clinic_assignments]

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@doctor_bp.route('/dashboard')
@login_required
def dashboard():
    search_query = request.args.get('q', '')
    clinic_ids = get_doctor_clinics()
    
    patients_query = Patient.query.join(
        PatientClinicMap
    ).filter(
        PatientClinicMap.clinic_id.in_(clinic_ids)
    )
    
    if search_query:
        patients_query = patients_query.filter(
            Patient.name.ilike(f'%{search_query}%') |
            Patient.contact_number.ilike(f'%{search_query}%')
        )
    
    patients = patients_query.order_by(Patient.name).all()
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
    clinic_ids = get_doctor_clinics()
    
    patient = Patient.query.join(
        PatientClinicMap
    ).filter(
        PatientClinicMap.clinic_id.in_(clinic_ids),
        Patient.id == patient_id
    ).first_or_404()
    
    reports = Report.query.filter_by(
        patient_id=patient_id,
        doctor_id=current_user.id
    ).order_by(
        Report.generated_on.desc()
    ).all()
    
    images = Image.query.filter_by(
        patient_id=patient_id
    ).all()
    
    return render_template('doctor/view_patient.html',
                        patient=patient,
                        reports=reports,
                        images=images)

@doctor_bp.route('/debug/model')
@login_required
def debug_model():
    model = ai_service.models.get('resnet_cbam')
    if not model:
        return jsonify({"error": "Model not loaded"}), 500
    
    # Check first conv layer weights
    conv1_weight = model.resnet.conv1.weight.data.cpu().numpy()
    fc_weight = model.resnet.fc.weight.data.cpu().numpy()
    
    return jsonify({
        "conv1_mean": float(conv1_weight.mean()),
        "conv1_std": float(conv1_weight.std()),
        "fc_mean": float(fc_weight.mean()),
        "fc_std": float(fc_weight.std()),
        "device": str(next(model.parameters()).device)
    })

@doctor_bp.route('/api/analyze_image', methods=['POST'])
@login_required
def analyze_image_api():
    try:
        # Verify CSRF token for AJAX requests
        if request.content_type.startswith('multipart/form-data'):
            form = FlaskForm()
            if not form.validate_on_submit():
                return jsonify({
                    'status': 'error',
                    'message': 'CSRF token missing or invalid'
                }), 400

        if 'image' not in request.files:
            return jsonify({'status': 'error', 'message': 'No image provided'}), 400

        image_file = request.files['image']
        model = request.form.get('model', 'resnet_cbam')

        # Ensure the temp_images directory exists in config
        if 'temp_images' not in current_app.config['UPLOAD_FOLDERS']:
            current_app.config['UPLOAD_FOLDERS']['temp_images'] = os.path.join(
                current_app.instance_path,
                'uploads',
                'temp_images'
            )

        # Create user-specific temp directory
        temp_dir = os.path.join(
            current_app.config['UPLOAD_FOLDERS']['temp_images'],
            str(current_user.id)
        )
        os.makedirs(temp_dir, exist_ok=True)

        # Generate temp file path
        temp_filename = f"temp_{uuid.uuid4().hex}.jpg"
        temp_path = os.path.join(temp_dir, temp_filename)

        # Save the file
        image_file.save(temp_path)

        # Verify file was saved
        if not os.path.exists(temp_path):
            raise IOError("Failed to save temporary image file")

        # Call AI service
        analysis_result = ai_service.analyze_image(temp_path, model)

        # Return response
        return jsonify({
            'status': 'success',
            'analysis': {
                'classification': analysis_result['classification'],
                'confidence': round(analysis_result['confidence'], 4),
                'probabilities': {
                    'benign': round(analysis_result['probabilities']['benign'], 4),
                    'malignant': round(analysis_result['probabilities']['malignant'], 4)
                },
                'model_used': 'ResNet50-CBAM (Selective)',  # Updated model name
                'model_version': '1.1'
            }
        })

    except Exception as e:
        current_app.logger.error(f"Unexpected error in image analysis: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': 'An unexpected error occurred'
        }), 500

    
@doctor_bp.route('/api/model_info')
@login_required
def model_info():
    try:
        model_info = ai_service.get_model_info('resnet_cbam')
        return jsonify({
            'status': 'success',
            'model': {
                'name': 'ResNet50-CBAM (Selective)',
                'architecture': 'Custom ResNet50 with CBAM in first block of each layer',
                'parameters': model_info['total_parameters'],
                'input_size': '224x224 RGB',
                'classes': ['benign', 'malignant']
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    


@doctor_bp.route('/reports/create/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def create_report(patient_id):
    """Create a new report for a patient"""
    clinic_ids = get_doctor_clinics()
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
            db.session.flush()  # Get report ID before committing

            # Handle image uploads
            upload_dir = os.path.join(
                current_app.config['UPLOAD_FOLDERS']['patient_images'],
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
                current_app.logger.info(f"PDF report generated successfully at: {pdf_path}")
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
                        models=ai_service.models.keys())

@doctor_bp.route('/reports/save/<int:patient_id>', methods=['POST'])
@login_required
def save_report(patient_id):
    """Save report (API endpoint for AJAX submissions)"""
    form = FlaskForm()  # For CSRF validation
    
    # Validate CSRF first
    if not form.validate_on_submit():
        error_msg = 'CSRF token missing or invalid'
        current_app.logger.warning(error_msg)
        return jsonify({'success': False, 'message': error_msg}), 400
    
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
        db.session.flush()  # Get report ID before committing

        # Handle image uploads
        upload_dir = os.path.join(
            current_app.config['UPLOAD_FOLDERS']['patient_images'],
            str(patient_id)
        )

        # Create the directory if it doesn't exist
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
            current_app.logger.info(f"PDF report generated successfully at: {pdf_path}")
        except Exception as pdf_error:
            current_app.logger.error(f"PDF generation failed: {str(pdf_error)}")
            db.session.rollback()
            raise ValueError(f"Report saved but PDF generation failed: {str(pdf_error)}")

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
    """Download PDF version of a report"""
    report = Report.query.filter_by(
        id=report_id,
        doctor_id=current_user.id
    ).first_or_404()
    
    # Regenerate PDF if missing or corrupted
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


    
@doctor_bp.route('/images/<int:patient_id>/<filename>')
@login_required
def serve_image(patient_id, filename):
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
        current_app.config['UPLOAD_FOLDERS']['patient_images'],
        str(patient_id)
    ) 

    return send_from_directory(upload_dir, filename)


@doctor_bp.route('/images/upload/<int:patient_id>', methods=['POST'])
@login_required
def upload_image(patient_id):
    clinic_ids = get_doctor_clinics()

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
        for file in files:
            if file and allowed_file(file.filename):
                # Generate unique filename
                filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
                upload_dir = os.path.join(
                    current_app.config['UPLOAD_FOLDERS']['patient_images'],
                    str(patient_id)
                )
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)

                image = Image(
                    patient_id=patient_id,
                    filename=filename,
                    file_path=filepath.replace(os.sep, '/'),  # Ensure consistent path format
                    uploaded_by=current_user.id
                )
                db.session.add(image)

        db.session.commit()
        flash('Images uploaded successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Image upload error: {str(e)}")
        flash(f'Error uploading images: {str(e)}', 'danger')

    return redirect(url_for('doctor.view_patient', patient_id=patient_id))

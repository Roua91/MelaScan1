from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required, current_user
from app.models import Patient, Report, Image, UserClinicMap, PatientClinicMap
from app.extensions import db
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import json

doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')

def get_doctor_clinics():
    return [ua.clinic_id for ua in current_user.clinic_assignments]

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

@doctor_bp.route('/reports/create/<int:patient_id>', methods=['GET', 'POST'])
@login_required
def create_report(patient_id):
    clinic_ids = get_doctor_clinics()
    
    patient = Patient.query.join(
        PatientClinicMap
    ).filter(
        PatientClinicMap.clinic_id.in_(clinic_ids),
        Patient.id == patient_id
    ).first_or_404()

    if request.method == 'POST':
        try:
            report = Report(
                patient_id=patient_id,
                doctor_id=current_user.id,
                findings=request.form['findings'],
                diagnosis=request.form['diagnosis'],
                recommendations=request.form['recommendations']
            )
            db.session.add(report)
            db.session.flush()
            
            if 'images' in request.files:
                for file in request.files.getlist('images'):
                    if file.filename:
                        filename = secure_filename(file.filename)
                        upload_dir = os.path.join(
                            current_app.root_path,
                            'static/uploads',
                            str(patient_id)
                        )
                        os.makedirs(upload_dir, exist_ok=True)
                        filepath = os.path.join(upload_dir, filename)
                        file.save(filepath)
                        
                        image = Image(
                            patient_id=patient_id,
                            report_id=report.id,
                            filename=filename,
                            file_path=filepath,
                            uploaded_by=current_user.id
                        )
                        db.session.add(image)
            
            report.generate_pdf()
            db.session.commit()
            flash('Report created successfully!', 'success')
            return redirect(url_for('doctor.view_patient', patient_id=patient_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('doctor/create_report.html', patient=patient)

@doctor_bp.route('/reports/<int:report_id>')
@login_required
def view_report(report_id):
    report = Report.query.filter_by(
        id=report_id,
        doctor_id=current_user.id
    ).first_or_404()
    
    return render_template('doctor/view_report.html', 
                        report=report,
                        json=json)

@doctor_bp.route('/reports/<int:report_id>/download')
@login_required
def download_report(report_id):
    report = Report.query.filter_by(
        id=report_id,
        doctor_id=current_user.id
    ).first_or_404()
    
    if not report.pdf_path or not os.path.exists(report.pdf_path):
        report.generate_pdf()
        db.session.commit()
    
    return send_from_directory(
        os.path.dirname(report.pdf_path),
        os.path.basename(report.pdf_path),
        as_attachment=True,
        mimetype='application/pdf'
    )

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
                filename = secure_filename(file.filename)
                upload_dir = os.path.join(
                    current_app.root_path,
                    'static/uploads',
                    str(patient_id)
                )
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                file.save(filepath)
                
                image = Image(
                    patient_id=patient_id,
                    filename=filename,
                    file_path=filepath,
                    uploaded_by=current_user.id
                )
                db.session.add(image)
        
        db.session.commit()
        flash('Images uploaded successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error uploading images: {str(e)}', 'danger')
    
    return redirect(url_for('doctor.view_patient', patient_id=patient_id))

@doctor_bp.route('/images/<int:image_id>/analyze')
@login_required
def analyze_image(image_id):
    image = Image.query.join(
        Patient
    ).join(
        PatientClinicMap
    ).join(
        UserClinicMap
    ).filter(
        UserClinicMap.user_id == current_user.id,
        Image.id == image_id
    ).first_or_404()
    
    # This would call your actual AI service
    analysis_result = {
        'diagnosis': 'Sample Diagnosis',
        'confidence': 0.95,
        'findings': 'Sample findings from AI analysis',
        'recommendations': 'Sample recommendations'
    }
    
    image.analysis = json.dumps(analysis_result)
    db.session.commit()
    
    flash('Image analysis completed!', 'success')
    return redirect(url_for('doctor.view_patient', patient_id=image.patient_id))

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}
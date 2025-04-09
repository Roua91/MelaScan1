# app/routes/admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, abort, send_from_directory
from flask_login import login_required, current_user
from datetime import datetime
import json
import os
from app.models import ClinicRegistration, Clinic, User, UserClinicMap
from app.extensions import db
from app.services.email_service import send_credentials_email, send_rejection_email
from app.services.password_service import PasswordService

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        abort(403)
    
    # Get statistics
    total_clinics = Clinic.query.count()
    pending_applications = ClinicRegistration.query.filter_by(status='pending').count()
    approved_clinics = Clinic.query.filter_by(status='active').count()
    rejected_applications = ClinicRegistration.query.filter_by(status='rejected').count()
    
    # Get recent registrations
    registrations = ClinicRegistration.query.order_by(
        ClinicRegistration.submitted_at.desc()
    ).limit(10).all()
    
    return render_template('admin/dashboard.html',
        total_clinics=total_clinics,
        pending_applications=pending_applications,
        approved_clinics=approved_clinics,
        rejected_applications=rejected_applications,
        registrations=registrations)

@admin_bp.route('/registrations')
@login_required
def view_registrations():
    if not current_user.is_admin:
        abort(403)
    
    applications = ClinicRegistration.query.filter_by(status='pending').all()
    return render_template('admin/registrations.html', applications=applications)

@admin_bp.route('/process_registration/<int:application_id>', methods=['GET', 'POST'])
@login_required
def process_registration(application_id):
    if not current_user.is_admin:
        abort(403)
    
    application = ClinicRegistration.query.get_or_404(application_id)
    doctors = json.loads(application.doctor_names) if application.doctor_names else []
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'approve':
            try:
                # Create clinic
                clinic = Clinic(
                    name=application.clinic_name,
                    address=application.clinic_address,
                    contact_number=application.contact_number,
                    license_number=application.license_number,
                    status='active'
                )
                db.session.add(clinic)
                db.session.flush()
                
                # Create admin user
                admin_password = PasswordService.generate_permanent_password()
                admin = User(
                    username=application.admin_email.split('@')[0],
                    email=application.admin_email,
                    role='local_admin'
                )
                admin.set_password(admin_password)
                db.session.add(admin)
                db.session.flush()
                
                # Create doctors
                for doctor_info in doctors:
                    doctor_password = PasswordService.generate_permanent_password()
                    doctor = User(
                        username=doctor_info['email'].split('@')[0],
                        email=doctor_info['email'],
                        role='doctor'
                    )
                    doctor.set_password(doctor_password)
                    db.session.add(doctor)
                    db.session.flush()
                    
                    # Map doctors to clinic
                    db.session.add(UserClinicMap(
                        user_id=doctor.id,
                        clinic_id=clinic.id,
                        role_at_clinic='doctor'
                    ))
                    
                    # Send credentials email
                    send_credentials_email(
                        doctor_info['email'], 
                        clinic.name, 
                        doctor_password
                    )
                
                # Map admin to clinic
                db.session.add(UserClinicMap(
                    user_id=admin.id,
                    clinic_id=clinic.id,
                    role_at_clinic='admin'
                ))
                
                # Update application status
                application.status = 'approved'
                application.processed_at = datetime.utcnow()
                application.processed_by = current_user.id
                
                db.session.commit()
                
                # Send admin credentials
                send_credentials_email(
                    application.admin_email, 
                    clinic.name, 
                    admin_password
                )
                
                flash('Clinic approved successfully!', 'success')
                return redirect(url_for('admin.dashboard'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'Approval failed: {str(e)}', 'danger')
        
        elif action == 'reject':
            rejection_reason = request.form.get('rejection_reason')
            if not rejection_reason:
                flash('Please provide a rejection reason', 'danger')
                return redirect(url_for('admin.process_registration', application_id=application_id))
            
            application.status = 'rejected'
            application.rejection_reason = rejection_reason
            application.processed_at = datetime.utcnow()
            application.processed_by = current_user.id
            db.session.commit()
            
            send_rejection_email(
                email=application.admin_email,
                clinic_name=application.clinic_name,
                reason=rejection_reason
            )
            
            flash('Application rejected', 'success')
            return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/process_registration.html',
        application=application,
        doctors=doctors)

@admin_bp.route('/download/<path:filename>')
@login_required
def download_file(filename):
    if not current_user.is_admin:
        abort(403)
    
    upload_folder = os.path.join(
        current_app.root_path,
        'uploads',
        'registration'
    )
    return send_from_directory(upload_folder, filename, as_attachment=True)
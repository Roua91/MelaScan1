# app/routes/auth.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
import os
import json
from datetime import datetime
from app.forms import ClinicRegistrationForm, LoginForm
from app.models import ClinicRegistration, User
from app.extensions import db
from flask_login import login_user, logout_user, login_required, current_user

registration_bp = Blueprint('registration', __name__)
auth_bp = Blueprint('auth', __name__)

# Registration routes
@registration_bp.route('/register/clinic', methods=['GET', 'POST'])
def clinic_registration():
    form = ClinicRegistrationForm()
    
    if len(form.doctors) == 0:
        form.doctors.append_entry()
    
    if request.method == 'POST':
        try:
            doctor_data = []
            i = 0
            while f'doctors-{i}-name' in request.form:
                doctor_data.append({
                    'name': request.form[f'doctors-{i}-name'],
                    'email': request.form[f'doctors-{i}-email']
                })
                i += 1
            
            if 'license_document' in request.files:
                license_file = request.files['license_document']
                if license_file.filename != '':
                    filename = secure_filename(license_file.filename)
                    upload_folder = current_app.config['UPLOAD_FOLDERS']['registration']
                    os.makedirs(upload_folder, exist_ok=True)
                    file_path = os.path.join(upload_folder, filename)
                    license_file.save(file_path)
            
            registration = ClinicRegistration(
                clinic_name=request.form.get('clinic_name'),
                clinic_address=request.form.get('clinic_address'),
                contact_number=request.form.get('contact_number'),
                admin_name=request.form.get('admin_name'),
                admin_email=request.form.get('admin_email'),
                admin_phone=request.form.get('admin_phone'),
                license_number=request.form.get('license_number'),
                license_document=file_path,
                doctor_count=len(doctor_data),
                doctor_names=json.dumps(doctor_data),
                status='pending'
            )
            
            db.session.add(registration)
            db.session.commit()
            
            flash('Application submitted successfully!', 'success')
            return redirect(url_for('registration.track_application', application_id=registration.id))
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration failed: {str(e)}")
            flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('registration/clinic_register.html', form=form)

@registration_bp.route('/add-doctor', methods=['POST'])
def add_doctor():
    form = ClinicRegistrationForm()
    form.doctors.append_entry()
    return render_template('registration/_doctor_form.html', doctor=form.doctors[-1], index=len(form.doctors))

@registration_bp.route('/track/<int:application_id>')
def track_application(application_id):
    application = ClinicRegistration.query.get_or_404(application_id)
    return render_template('registration/track_application.html', 
        application=application,
        status_message=get_status_message(application.status))

# Auth routes
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'local_admin':
            return redirect(url_for('clinic.dashboard'))
        else:
            return redirect(url_for('doctor.dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'local_admin':
                return redirect(url_for('clinic.dashboard'))
            else:
                return redirect(url_for('doctor.dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

def get_status_message(status):
    messages = {
        'pending': 'Your application is under review',
        'approved': 'Your application has been approved!',
        'rejected': 'Your application was rejected'
    }
    return messages.get(status, 'Unknown application status')
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
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

registration_bp = Blueprint('registration', __name__)
auth_bp = Blueprint('auth', __name__)

@registration_bp.route('/register/clinic', methods=['GET', 'POST'])
def clinic_registration():
    form = ClinicRegistrationForm()
    logger.debug(f"Initial form data: {form.data}")
    logger.debug(f"Initial form errors: {form.errors}")

    # Ensure at least one doctor entry exists
    if not form.doctors.entries:
        form.doctors.append_entry()
        logger.debug("Added initial doctor entry")

    if form.validate_on_submit():
        logger.debug("Form validation passed")
        try:
            # Debug: Print all form data
            logger.debug(f"Form submitted data: {form.data}")
            
            # Process doctors through form data
            doctor_data = []
            for i, doctor in enumerate(form.doctors):
                logger.debug(f"Processing doctor {i+1}: {doctor.form.data}")
                if not doctor.form.name.data or not doctor.form.email.data:
                    logger.error(f"Missing data for doctor {i+1}")
                    flash(f'Please complete all fields for Doctor {i+1}', 'danger')
                    return render_template('registration/clinic_register.html', form=form)
                
                doctor_data.append({
                    'name': doctor.form.name.data,
                    'email': doctor.form.email.data
                })

            # Handle file upload 
            if form.license_document.data:
                license_file = form.license_document.data
                logger.debug(f"Processing file upload: {license_file.filename}")
                
                filename = secure_filename(license_file.filename)
                upload_folder = os.path.join(
                    current_app.root_path,
                    'uploads',
                    'registration'
                )
                logger.debug(f"Upload folder: {upload_folder}")
                
                try:
                    os.makedirs(upload_folder, exist_ok=True)
                    file_path = os.path.join(upload_folder, filename)
                    license_file.save(file_path)
                    stored_path = os.path.join('registration', filename).replace('\\', '/')
                    logger.debug(f"File saved to: {file_path}")
                except Exception as e:
                    logger.error(f"File save failed: {str(e)}")
                    flash('File upload failed. Please try again.', 'danger')
                    return render_template('registration/clinic_register.html', form=form)
            else:
                logger.error("No license document provided")
                flash('License document is required', 'danger')
                return render_template('registration/clinic_register.html', form=form)
            
            # Create and save registration
            try:
                registration = ClinicRegistration(
                    clinic_name=form.clinic_name.data,
                    clinic_address=form.clinic_address.data,
                    contact_number=form.contact_number.data,
                    admin_name=form.admin_name.data,
                    admin_email=form.admin_email.data,
                    admin_phone=form.admin_phone.data,
                    license_number=form.license_number.data,
                    license_document=stored_path,
                    doctor_count=len(doctor_data),
                    doctor_names=json.dumps(doctor_data),
                    status='pending',
                    submitted_at=datetime.utcnow()
                )
                logger.debug(f"Registration object created: {registration}")
                
                db.session.add(registration)
                db.session.flush()
                logger.debug("Database flush successful")
                
                db.session.commit()
                logger.info("Registration committed successfully")
                
                flash('Application submitted successfully!', 'success')
                return redirect(url_for('registration.track_application', application_id=registration.id))
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Database error: {str(e)}", exc_info=True)
                if "UNIQUE constraint failed" in str(e):
                    flash('Email address already registered', 'danger')
                else:
                    flash('Database error occurred. Please try again.', 'danger')
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration failed: {str(e)}", exc_info=True)
            flash(f'Registration failed: {str(e)}', 'danger')
    
    if form.errors:
        logger.error(f"Form validation errors: {form.errors}")
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", 'danger')
    
    return render_template('registration/clinic_register.html', form=form)


        
@registration_bp.route('/add-doctor', methods=['POST'])
def add_doctor():
    try:
        form = ClinicRegistrationForm()
        form.doctors.append_entry()
        logger.debug(f"Added doctor entry. Total doctors: {len(form.doctors)}")
        return render_template('registration/_doctor_entry.html', 
                    doctor=form.doctors[-1], 
                    index=len(form.doctors)-1)
    except Exception as e:
        logger.error(f"Error adding doctor: {str(e)}")
        return "Error adding doctor field", 500
    
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
    
    return render_template('login.html', form=form)

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
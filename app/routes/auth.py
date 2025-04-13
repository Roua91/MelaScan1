# app/routes/auth.py

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
import os
import json
from datetime import datetime
import logging

from app.forms import ClinicRegistrationForm, LoginForm
from app.models import ClinicRegistration, User, Clinic, UserClinicMap, ClinicCredential
from app.extensions import db

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Blueprints
registration_bp = Blueprint('registration', __name__)
auth_bp = Blueprint('auth', __name__)


# -------------------- Registration Routes --------------------

@registration_bp.route('/register/clinic', methods=['GET', 'POST'])
def clinic_registration():
    form = ClinicRegistrationForm()
    logger.debug(f"Initial form data: {form.data}")
    logger.debug(f"Initial form errors: {form.errors}")

    if not form.doctors.entries:
        form.doctors.append_entry()
        logger.debug("Added initial doctor entry")

    if form.validate_on_submit():
        logger.debug("Form validation passed")
        try:
            logger.debug(f"Form submitted data: {form.data}")
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

            if form.license_document.data:
                license_file = form.license_document.data
                logger.debug(f"Processing file upload: {license_file.filename}")

                filename = secure_filename(license_file.filename)
                upload_folder = os.path.join(current_app.root_path, 'uploads', 'registration')
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
                            index=len(form.doctors) - 1)
    except Exception as e:
        logger.error(f"Error adding doctor: {str(e)}")
        return "Error adding doctor field", 500


@registration_bp.route('/track/<int:application_id>')
def track_application(application_id):
    application = ClinicRegistration.query.get_or_404(application_id)
    return render_template('registration/track_application.html',
                        application=application,
                        status_message=get_status_message(application.status))


# -------------------- Auth Routes --------------------

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect_to_dashboard()

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)

            if ClinicCredential.query.filter_by(user_id=user.id, is_valid=True).first():
                flash('Please change your temporary password', 'warning')
                return redirect(url_for('auth.change_password'))

            return redirect_to_dashboard()

        flash('Invalid email or password', 'danger')

    return render_template('login.html', form=form)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('auth.change_password'))

        try:
            current_user.set_password(new_password)
            ClinicCredential.query.filter_by(user_id=current_user.id).update({'is_valid': False})
            db.session.commit()

            flash('Password changed successfully!', 'success')
            return redirect(url_for('auth.redirect_to_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating password', 'danger')

    return render_template('registration/change_password.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/redirect-dashboard')
@login_required
def redirect_to_dashboard():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == 'local_admin':
        return redirect(url_for('local_admin.dashboard'))
    elif current_user.role == 'doctor':
        return redirect(url_for('doctor.dashboard'))

    flash('Unknown user role', 'danger')
    return redirect(url_for('auth.login'))


@auth_bp.route('/track-application', methods=['GET', 'POST'])
def track_application():
    if request.method == 'POST':
        license_number = request.form.get('license_number')
        admin_email = request.form.get('admin_email')

        if not all([license_number, admin_email]):
            flash('All fields are required', 'danger')
            return redirect(url_for('auth.track_application'))

        registration = ClinicRegistration.query.filter_by(
            license_number=license_number,
            admin_email=admin_email
        ).first()

        if not registration:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('auth.track_application'))

        if registration.status != 'approved':
            return render_template('registration/track_status.html',
                                application=registration,
                                status=registration.status,
                                rejection_reason=registration.rejection_reason)

        clinic = Clinic.query.filter_by(license_number=license_number).first()
        if not clinic:
            flash('Clinic not found', 'danger')
            return redirect(url_for('auth.track_application'))

        admin = User.query.filter_by(email=admin_email).first()
        admin_credential = ClinicCredential.query.filter_by(
            user_id=admin.id,
            clinic_id=clinic.id
        ).first()

        doctors = []
        doctor_mappings = UserClinicMap.query.filter_by(
            clinic_id=clinic.id,
            role_at_clinic='doctor'
        ).all()

        for mapping in doctor_mappings:
            doctor = User.query.get(mapping.user_id)
            cred = ClinicCredential.query.filter_by(
                user_id=doctor.id,
                clinic_id=clinic.id
            ).first()

            doctors.append({
                'name': doctor.username,
                'email': doctor.email,
                'password': cred.temp_password if cred else '[not set]'
            })

        print(f"Found {len(doctor_mappings)} doctor mappings:")
        for mapping in doctor_mappings:
            print(f" - User {mapping.user_id} | Role: {mapping.role_at_clinic}")

        print(f"ClinicCredentials for clinic {clinic.id}:")
        creds = ClinicCredential.query.filter_by(clinic_id=clinic.id).all()
        for c in creds:
            print(f" - User {c.user_id} | Temp: {c.temp_password} | Valid: {c.is_valid}")

        return render_template('registration/track_status.html',
                            application=registration,
                            status='approved',
                            admin_credential=admin_credential,
                            doctors=doctors,
                            clinic=clinic)

    return render_template('registration/track_application.html')


# -------------------- Helper Functions --------------------

def get_status_message(status):
    messages = {
        'pending': 'Your application is under review',
        'approved': 'Your application has been approved!',
        'rejected': 'Your application was rejected'
    }
    return messages.get(status, 'Unknown application status')

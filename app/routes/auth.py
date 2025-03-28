from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
import os
import json
from datetime import datetime
from app.forms import ClinicRegistrationForm, LoginForm
from app.models import ClinicRegistration, User, Clinic, UserClinicMap
from app.extensions import db
from app.services.email_service import send_credentials_email
from app.services.password_service import PasswordService

registration_bp = Blueprint('registration', __name__)
auth_bp = Blueprint('auth', __name__)


def is_admin():
    return session.get('is_admin', False)

@registration_bp.route('/register/clinic', methods=['GET', 'POST'])
def clinic_registration():
    form = ClinicRegistrationForm()
    
    # Ensure at least one doctor field exists
    if len(form.doctors) == 0:
        form.doctors.append_entry()
    
    if request.method == 'POST':
        try:
            # Process doctor data
            doctor_data = []
            i = 0
            while f'doctors-{i}-name' in request.form:
                doctor_data.append({
                    'name': request.form[f'doctors-{i}-name'],
                    'email': request.form[f'doctors-{i}-email']
                })
                i += 1
            
            # Handle file upload
            if 'license_document' in request.files:
                license_file = request.files['license_document']
                if license_file.filename != '':
                    filename = secure_filename(license_file.filename)
                    upload_folder = current_app.config['UPLOAD_FOLDERS']['registration']
                    os.makedirs(upload_folder, exist_ok=True)
                    file_path = os.path.join(upload_folder, filename)
                    license_file.save(file_path)
            
            # Create registration record
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

@registration_bp.route('/admin/process_registration/<int:application_id>', methods=['POST'])
def process_registration(application_id):
    if not is_admin():
        return "Unauthorized", 403
    
    application = ClinicRegistration.query.get_or_404(application_id)
    
    if request.form.get('action') == 'approve':
        try:
            clinic = Clinic(
                name=application.clinic_name,
                address=application.clinic_address,
                contact_number=application.contact_number,
                license_number=application.license_number,
                status='active'
            )
            db.session.add(clinic)
            db.session.flush()
            
            admin_password = PasswordService.generate_permanent_password()
            admin = User(
                username=application.admin_email.split('@')[0],
                email=application.admin_email,
                role='local_admin'
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.flush()
            
            doctors = json.loads(application.doctor_names)
            for name, email in doctors.items():
                doctor_password = PasswordService.generate_permanent_password()
                doctor = User(
                    username=email.split('@')[0],
                    email=email,
                    role='doctor'
                )
                doctor.set_password(doctor_password)
                db.session.add(doctor)
                db.session.flush()
                
                db.session.add(UserClinicMap(
                    user_id=doctor.id,
                    clinic_id=clinic.id,
                    role_at_clinic='doctor'
                ))
                
                send_credentials_email(email, clinic.name, doctor_password)
            
            db.session.add(UserClinicMap(
                user_id=admin.id,
                clinic_id=clinic.id,
                role_at_clinic='admin'
            ))
            
            application.status = 'approved'
            application.processed_at = datetime.utcnow()
            application.processed_by = session.get('user_id')  # Simple session ID
            
            db.session.commit()
            
            send_credentials_email(application.admin_email, clinic.name, admin_password)
            flash('Clinic approved successfully', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'Approval failed: {str(e)}', 'danger')
    
    elif request.form.get('action') == 'reject':
        rejection_reason = request.form.get('rejection_reason')
        if not rejection_reason:
            flash('Please provide a rejection reason', 'danger')
            return redirect(url_for('registration.process_registration', application_id=application_id))
        
        application.status = 'rejected'
        application.rejection_reason = rejection_reason
        application.processed_at = datetime.utcnow()
        application.processed_by = session.get('user_id')
        db.session.commit()
        
        flash('Application rejected', 'success')
    
    return redirect(url_for('registration.admin_view_registrations'))

@registration_bp.route('/admin/registrations')
def admin_view_registrations():
    if not is_admin():
        return "Unauthorized", 403
    
    applications = ClinicRegistration.query.filter_by(status='pending').all()
    return render_template('registration/registrations.html', applications=applications)

def get_status_message(status):
    messages = {
        'pending': 'Your application is under review',
        'approved': 'Your application has been approved!',
        'rejected': 'Your application was rejected'
    }
    return messages.get(status, 'Unknown application status')

@registration_bp.route('/track/<int:application_id>')
def track_application(application_id):
    application = ClinicRegistration.query.get_or_404(application_id)
    return render_template('registration/track_application.html', application=application,
        status_message=get_status_message(application.status))


## LOG IN ##
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and check_password_hash(user.password_hash, form.password.data):
            session['user_id'] = user.id
            session['user_role'] = user.role
            session['username'] = user.username
            
            flash('Login successful!', 'success')
            
            # Redirect based on user role
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
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home.home'))
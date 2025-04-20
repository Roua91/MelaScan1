from flask import Blueprint, render_template, abort, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.models import Report
from app.models import User, Clinic, UserClinicMap, Patient, PatientClinicMap , Report
from app.extensions import db
from datetime import datetime
from werkzeug.security import generate_password_hash
from app.services.password_service import PasswordService
from app.models import ClinicCredential
from app.forms import DoctorForm, PatientForm



local_admin_bp = Blueprint('local_admin', __name__, url_prefix='/local_admin')

def get_admin_clinic():
    """Helper function to get current admin's clinic"""
    clinic_mapping = UserClinicMap.query.filter_by(
        user_id=current_user.id,
        role_at_clinic='admin'
    ).first()
    
    if not clinic_mapping:
        abort(403, description="No clinic assigned to this admin")
    return clinic_mapping.clinic



@local_admin_bp.route('/dashboard')
@login_required
def dashboard():
    clinic = get_admin_clinic()
    
    doctors = User.query.join(UserClinicMap).filter(
        UserClinicMap.clinic_id == clinic.id,
        UserClinicMap.role_at_clinic == 'doctor'
    ).all()
    
    patients = Patient.query.join(PatientClinicMap).filter(
        PatientClinicMap.clinic_id == clinic.id
    ).order_by(Patient.date_created.desc()).limit(5).all()
    
    return render_template('local_admin/dashboard.html',
                        clinic=clinic,
                        doctors=doctors,
                        recent_patients=patients,
                        patient_count=Patient.query.join(PatientClinicMap)
                            .filter(PatientClinicMap.clinic_id == clinic.id)
                            .count())
    
    # routes.py
@local_admin_bp.route('/patients/add', methods=['GET', 'POST'])
@login_required
def add_patient():
    clinic = get_admin_clinic()
    form = PatientForm()
    
    if form.validate_on_submit():
        try:
            # Convert date string to date object
            dob = datetime.strptime(form.dob.data, '%Y-%m-%d').date()
            
            # Create and add patient
            patient = Patient(
                name=form.name.data,
                contact_number=form.phone.data,
                date_of_birth=dob
            )
            db.session.add(patient)
            db.session.flush()  # This generates the ID but doesn't commit
            
            # Now create the mapping with the patient's ID
            db.session.add(PatientClinicMap(
                patient_id=patient.id,  # Now patient.id exists
                clinic_id=clinic.id
            ))
            
            db.session.commit()  # Now commit both records
            flash('Patient added successfully!', 'success')
            return redirect(url_for('local_admin.view_patient', id=patient.id))
            
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding patient: {str(e)}', 'danger')
    
    return render_template('local_admin/add_patient.html', form=form)

@local_admin_bp.route('/patients')
@login_required
def manage_patients():
    clinic = get_admin_clinic()
    search_query = request.args.get('q', '')
    
    patients_query = Patient.query.join(PatientClinicMap).filter(
        PatientClinicMap.clinic_id == clinic.id
    )
    
    if search_query:
        patients_query = patients_query.filter(
            Patient.name.ilike(f'%{search_query}%') |
            Patient.contact_number.ilike(f'%{search_query}%')
        )
    
    patients = patients_query.order_by(Patient.name).all()
    return render_template('local_admin/manage_patients.html',
                        patients=patients,
                        search_query=search_query)

@local_admin_bp.route('/patients/<int:id>')
@login_required
def view_patient(id):
    # Verify patient belongs to admin's clinic
    patient = Patient.query.join(PatientClinicMap).filter(
        Patient.id == id,
        PatientClinicMap.clinic_id == get_admin_clinic().id
    ).first_or_404()
    
    reports = Report.query.filter_by(patient_id=id).all()
    return render_template('local_admin/view_patient.html',
                        patient=patient,
                        reports=reports)

@local_admin_bp.route('/patients/<int:id>/delete', methods=['POST'])
@login_required
def delete_patient(id):
    # Verify patient belongs to admin's clinic
    mapping = PatientClinicMap.query.filter_by(
        patient_id=id,
        clinic_id=get_admin_clinic().id
    ).first_or_404()
    
    # Also delete the patient record if you want to completely remove the patient
    patient = Patient.query.get(id)
    if patient:
        db.session.delete(patient)
    
    db.session.delete(mapping)
    db.session.commit()
    flash('Patient deleted successfully', 'success')
    return redirect(url_for('local_admin.manage_patients'))

@local_admin_bp.route('/reports/<int:report_id>/download')
@login_required
def download_report(report_id):
    report = Report.query.join(Patient, PatientClinicMap).filter(
        Report.id == report_id,
        PatientClinicMap.clinic_id == get_admin_clinic().id
    ).first_or_404()
    
    # In a real implementation, generate PDF here
    from flask import send_from_directory
    return send_from_directory('path/to/reports', f'report_{report_id}.pdf')

# routes.py
@local_admin_bp.route('/doctors')
@login_required
def manage_doctors():
    clinic = get_admin_clinic()
    doctors = User.query.join(UserClinicMap).filter(
        UserClinicMap.clinic_id == clinic.id,
        UserClinicMap.role_at_clinic == 'doctor'
    ).all()
    
    return render_template('local_admin/manage_doctors.html', doctors=doctors)


@local_admin_bp.route('/doctors/add', methods=['GET', 'POST'])
@login_required
def add_doctor():
    clinic = get_admin_clinic()
    form = DoctorForm()
    
    if form.validate_on_submit():
        try:
            # Generate credentials
            temp_password = PasswordService.generate_permanent_password()
            
            # Create doctor user
            doctor = User(
                username=form.email.data.split('@')[0],
                email=form.email.data,
                name=form.name.data,  # Now this will work
                role='doctor'
            )
            doctor.set_password(temp_password)
            db.session.add(doctor)
            db.session.flush()  # Get the doctor.id
            
            # Link to clinic
            db.session.add(UserClinicMap(
                user_id=doctor.id,
                clinic_id=clinic.id,
                role_at_clinic='doctor'
            ))
            
            # Store temporary credentials
            db.session.add(ClinicCredential(
                user_id=doctor.id,
                clinic_id=clinic.id,
                temp_password=temp_password,
                is_valid=True
            ))
            
            db.session.commit()
            flash('Doctor added successfully!', 'success')
            return redirect(url_for('local_admin.manage_doctors'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating doctor: {str(e)}', 'danger')
    
    return render_template('local_admin/add_doctor.html', form=form)


@local_admin_bp.route('/doctors/<int:doctor_id>/delete', methods=['POST'])
@login_required
def delete_doctor(doctor_id):
    clinic = get_admin_clinic()
    
    # Remove clinic association
    mapping = UserClinicMap.query.filter_by(
        clinic_id=clinic.id,
        user_id=doctor_id
    ).first_or_404()

    # Invalidate credentials
    ClinicCredential.query.filter_by(
        user_id=doctor_id,
        clinic_id=clinic.id
    ).delete()

    db.session.delete(mapping)
    db.session.commit()
    
    flash('Doctor removed from clinic', 'success')
    return redirect(url_for('local_admin.manage_doctors'))
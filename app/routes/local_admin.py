from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import Clinic, User, Patient, UserClinicMap, PatientClinicMap
from app.extensions import db
from app.forms import AddDoctorForm, AddPatientForm

local_admin_bp = Blueprint('local_admin', __name__, url_prefix='/local-admin')

@local_admin_bp.route('/dashboard')
@login_required
def dashboard():
    # Ensure user is a local admin
    if not current_user.role == 'local_admin':
        abort(403)
    
    # Get the admin's clinic
    clinic_mapping = UserClinicMap.query.filter_by(user_id=current_user.id).first()
    clinic = Clinic.query.get(clinic_mapping.clinic_id)
    
    # Get clinic doctors and patients
    doctors = User.query.join(UserClinicMap).filter(
        UserClinicMap.clinic_id == clinic.id,
        User.role == 'doctor'
    ).all()
    
    patients = Patient.query.join(PatientClinicMap).filter(
        PatientClinicMap.clinic_id == clinic.id
    ).all()
    
    return render_template('local_admin/dashboard.html',
        clinic=clinic,
        doctors=doctors,
        patients=patients)

@local_admin_bp.route('/add-doctor', methods=['GET', 'POST'])
@login_required
def add_doctor():
    form = AddDoctorForm()
    if form.validate_on_submit():
        # Create doctor user and map to clinic
        clinic_mapping = UserClinicMap.query.filter_by(user_id=current_user.id).first()
        doctor = User(
            username=form.email.data.split('@')[0],
            email=form.email.data,
            role='doctor'
        )
        doctor.set_password(form.password.data)
        db.session.add(doctor)
        db.session.flush()
        
        db.session.add(UserClinicMap(
            user_id=doctor.id,
            clinic_id=clinic_mapping.clinic_id,
            role_at_clinic='doctor'
        ))
        db.session.commit()
        flash('Doctor added successfully!', 'success')
        return redirect(url_for('local_admin.dashboard'))
    
    return render_template('local_admin/add_doctor.html', form=form)

@local_admin_bp.route('/add-patient', methods=['GET', 'POST'])
@login_required
def add_patient():
    form = AddPatientForm()
    clinic_mapping = UserClinicMap.query.filter_by(user_id=current_user.id).first()
    
    if form.validate_on_submit():
        patient = Patient(
            name=form.name.data,
            contact_number=form.contact_number.data,
            date_of_birth=form.date_of_birth.data
        )
        db.session.add(patient)
        db.session.flush()
        
        db.session.add(PatientClinicMap(
            patient_id=patient.id,
            clinic_id=clinic_mapping.clinic_id
        ))
        db.session.commit()
        flash('Patient added successfully!', 'success')
        return redirect(url_for('local_admin.dashboard'))
    
    return render_template('local_admin/add_patient.html', form=form)
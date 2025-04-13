from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from app.models import Clinic, UserClinicMap, PatientClinicMap, Patient
from app.extensions import db

doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')

@doctor_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'doctor':
        abort(403)
    
    # Get all clinics where this doctor is assigned
    clinic_assignments = db.session.query(UserClinicMap).join(
        Clinic
    ).filter(
        UserClinicMap.user_id == current_user.id,
        UserClinicMap.role_at_clinic == 'doctor'
    ).all()
    
    # Prepare data structures for template
    clinics_data = []
    
    for assignment in clinic_assignments:
        clinic = assignment.clinic
        
        # Get patients for this clinic
        patients = db.session.query(Patient).join(
            PatientClinicMap
        ).filter(
            PatientClinicMap.clinic_id == clinic.id
        ).all()
        
        clinics_data.append({
            'clinic': clinic,
            'patient_count': len(patients),
            'patients': patients
        })
    
    return render_template('doctor/dashboard.html',
                        clinics_data=clinics_data)
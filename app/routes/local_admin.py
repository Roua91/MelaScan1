from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from app.models import User, Clinic, UserClinicMap, PatientClinicMap  # Added PatientClinicMap
from app.extensions import db

local_admin_bp = Blueprint('local_admin', __name__, url_prefix='/local_admin')

@local_admin_bp.route('/dashboard')
@login_required
def dashboard():
    # Verify user is a local_admin
    if current_user.role != 'local_admin':
        abort(403)
    
    # Get the clinic this admin manages
    clinic_mapping = UserClinicMap.query.filter_by(
        user_id=current_user.id,
        role_at_clinic='admin'
    ).first()
    
    if not clinic_mapping:
        abort(403, description="No clinic assigned to this admin")
    
    clinic = clinic_mapping.clinic
    
    # Get doctors at this clinic
    doctors = User.query.join(UserClinicMap).filter(
        UserClinicMap.clinic_id == clinic.id,
        UserClinicMap.role_at_clinic == 'doctor'
    ).all()
    
    # Get patient count (only if PatientClinicMap exists)
    patient_count = 0
    if 'PatientClinicMap' in globals():
        patient_count = db.session.query(PatientClinicMap).filter_by(
            clinic_id=clinic.id
        ).count()
    
    return render_template('local_admin/dashboard.html', 
                        clinic=clinic,
                        doctors=doctors,
                        patient_count=patient_count)
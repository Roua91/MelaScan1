from flask import Blueprint, render_template
from flask_login import login_required, current_user

doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')

@doctor_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'doctor':
        abort(403)
    
    # Get assigned clinics and patient count
    clinics = current_user.clinic_mappings.join(Clinic).all()
    patient_counts = {}
    
    for clinic in clinics:
        patient_counts[clinic.id] = PatientClinicMap.query.filter_by(
            clinic_id=clinic.id
        ).count()
    
    return render_template('doctor/dashboard.html', clinics=clinics,patient_counts=patient_counts)
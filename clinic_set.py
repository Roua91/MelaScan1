from app.models import User, Clinic, UserClinicMap
from app import db

def setup_clinic_with_staff():
    """
    Creates a test clinic with admin and doctors for testing purposes
    """
    print("Starting clinic setup...")
    
    # Create a clinic
    test_clinic = Clinic(
        name="Test Medical Center",
        address="123 Healthcare Ave, Medical District, CA 90210",
        contact_number="555-123-4567",
        license_number="MED12345",
        status="approved"
    )
    
    # Add and commit the clinic to get its ID
    db.session.add(test_clinic)
    db.session.commit()
    
    # Create local admin user
    admin_user = User(
        username="local_admin",
        email="admin@testclinic.com",
        role="clinic_admin"
    )
    admin_user.set_password("Admin123!")
    
    # Add and commit admin to get the ID
    db.session.add(admin_user)
    db.session.commit()
    
    # Map admin to the clinic
    admin_mapping = UserClinicMap(
        user_id=admin_user.id,
        clinic_id=test_clinic.id,
        role_at_clinic="admin"
    )
    db.session.add(admin_mapping)
    db.session.commit()
    
    # Create doctor users
    doctors = [
        {"username": "doctor_smith", "email": "smith@testclinic.com", "password": "Doctor123!"},
        {"username": "doctor_jones", "email": "jones@testclinic.com", "password": "Doctor123!"}
    ]
    
    for doctor_data in doctors:
        doctor = User(
            username=doctor_data["username"],
            email=doctor_data["email"],
            role="doctor"
        )
        doctor.set_password(doctor_data["password"])
        
        # Add and commit doctor to get the ID
        db.session.add(doctor)
        db.session.commit()
        
        # Map doctor to the clinic
        doctor_mapping = UserClinicMap(
            user_id=doctor.id,
            clinic_id=test_clinic.id,
            role_at_clinic="doctor"
        )
        db.session.add(doctor_mapping)
        db.session.commit()
    
    print("\nSetup complete! You can now login with these credentials:")
    print("Local Admin: local_admin / Admin123!")
    print("Doctors: doctor_smith / Doctor123!, doctor_jones / Doctor123!")

# Run this function in Flask shell
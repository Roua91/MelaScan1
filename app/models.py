from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json
from flask_login import UserMixin

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(150))  
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    
    # Relationships
    clinic_assignments = db.relationship('UserClinicMap', back_populates='user')
    processed_registrations = db.relationship(
        'ClinicRegistration', 
        back_populates='processor', 
        foreign_keys='ClinicRegistration.processed_by'
    )
    credentials = db.relationship('ClinicCredential', back_populates='user')
    reports = db.relationship('Report', back_populates='doctor')
    uploaded_images = db.relationship('Image', back_populates='uploader')

    @property
    def is_admin(self):
        return self.role == 'admin'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Clinic(db.Model):
    __tablename__ = 'clinics'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(250), nullable=False)
    contact_number = db.Column(db.String(20), nullable=False)
    license_number = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')
    
    # Relationships
    staff_assignments = db.relationship('UserClinicMap', back_populates='clinic')
    patient_assignments = db.relationship('PatientClinicMap', back_populates='clinic')
    credentials = db.relationship('ClinicCredential', back_populates='clinic')
    registrations = db.relationship('ClinicRegistration', back_populates='clinic')
    
    registrations = db.relationship(
        'ClinicRegistration', 
        back_populates='clinic',
        foreign_keys='ClinicRegistration.clinic_id'  # Make this explicit
    )

class UserClinicMap(db.Model):
    __tablename__ = 'user_clinic_map'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinics.id'), nullable=False)
    role_at_clinic = db.Column(db.String(20), nullable=False)

    # Relationships
    user = db.relationship('User', back_populates='clinic_assignments')
    clinic = db.relationship('Clinic', back_populates='staff_assignments')

class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    contact_number = db.Column(db.String(20), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)  
    
    # Relationships
    clinic_relationships = db.relationship('PatientClinicMap', back_populates='patient')
    images = db.relationship('Image', back_populates='patient')
    reports = db.relationship('Report', back_populates='patient')

class PatientClinicMap(db.Model):
    __tablename__ = 'patient_clinic_map'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinics.id'), nullable=False)
    
    # Relationships
    clinic = db.relationship('Clinic', back_populates='patient_assignments')
    patient = db.relationship('Patient', back_populates='clinic_relationships')

class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Report content
    findings = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    
    # PDF storage
    pdf_path = db.Column(db.String(500))  
    pdf_filename = db.Column(db.String(255)) 
    
    # Timestamps
    generated_on = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='reports')
    doctor = db.relationship('User', back_populates='reports')
    
    def generate_pdf(self):
        """Generate PDF version of the report"""
        from app.services.pdf_generator import generate_report_pdf
        self.pdf_path, self.pdf_filename = generate_report_pdf(self)
        return self.pdf_path

class Image(db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    analysis = db.Column(db.Text)
    analysis_date = db.Column(db.DateTime)
    
    # Relationships
    patient = db.relationship('Patient', back_populates='images')
    uploader = db.relationship('User', back_populates='uploaded_images')

class ClinicRegistration(db.Model):
    __tablename__ = 'clinic_registrations'

    id = db.Column(db.Integer, primary_key=True)
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinics.id'))
    clinic_name = db.Column(db.String(150), nullable=False)
    clinic_address = db.Column(db.String(250), nullable=False)
    contact_number = db.Column(db.String(20), nullable=False)
    admin_name = db.Column(db.String(100), nullable=False)
    admin_email = db.Column(db.String(120), nullable=False, unique=True)
    admin_phone = db.Column(db.String(20))
    license_number = db.Column(db.String(50), nullable=False)
    license_document = db.Column(db.String(255), nullable=False)
    doctor_count = db.Column(db.Integer, default=1)
    doctor_names = db.Column(db.Text)  # JSON string
    status = db.Column(db.String(20), default='pending')
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    processed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    rejection_reason = db.Column(db.Text)
    admin_password = db.Column(db.String(128))
    doctor_passwords = db.Column(db.Text)  # JSON string
    
    # Relationships
    processor = db.relationship(
        'User', 
        back_populates='processed_registrations', 
        foreign_keys=[processed_by]
    )

    clinic = db.relationship(
        'Clinic', 
        back_populates='registrations',
        foreign_keys=[clinic_id]  
    )
    
    
    def set_doctor_passwords(self, doctor_passwords_dict):
        """Save doctor passwords as a JSON string."""
        self.doctor_passwords = json.dumps({
            k: generate_password_hash(v) for k, v in doctor_passwords_dict.items()
        })

    def get_doctor_passwords(self):
        """Return the stored doctor passwords as a dictionary."""
        try:
            return json.loads(self.doctor_passwords) if self.doctor_passwords else {}
        except json.JSONDecodeError:
            return {}

    def get_doctor_list(self):
        """Return list of doctor names from the JSON string."""
        try:
            return json.loads(self.doctor_names) if self.doctor_names else []
        except json.JSONDecodeError:
            return []

class ClinicCredential(db.Model):
    __tablename__ = 'clinic_credentials'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    clinic_id = db.Column(db.Integer, db.ForeignKey('clinics.id'))
    temp_password = db.Column(db.String(100))
    is_valid = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='credentials')
    clinic = db.relationship('Clinic', back_populates='credentials')
    
    def invalidate(self):
        """Invalidate the temporary password."""
        self.is_valid = False
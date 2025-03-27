#app/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, FileField, SubmitField, FieldList, FormField
from wtforms.validators import DataRequired, Email, Length, ValidationError
from app.models import Clinic, User

class DoctorForm(FlaskForm):
    name = StringField('Doctor Name', validators=[DataRequired()])
    email = StringField('Doctor Email', validators=[DataRequired(), Email()])

class ClinicRegistrationForm(FlaskForm):
    clinic_name = StringField('Clinic Name', validators=[DataRequired(), Length(max=150)])
    clinic_address = TextAreaField('Clinic Address', validators=[DataRequired(), Length(max=250)])
    contact_number = StringField('Contact Number', validators=[DataRequired(), Length(max=20)])
    license_number = StringField('Medical License Number', validators=[DataRequired(), Length(max=50)])
    license_document = FileField('License Document', validators=[DataRequired()])
    
    # Admin fields
    admin_name = StringField('Admin Name', validators=[DataRequired()])
    admin_email = StringField('Admin Email', validators=[DataRequired(), Email()])
    admin_phone = StringField('Admin Phone', validators=[DataRequired()])
    
    # Doctors
    doctors = FieldList(FormField(DoctorForm), min_entries=1)
    
    submit = SubmitField('Submit Application')

    def validate_admin_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('Email already registered.')
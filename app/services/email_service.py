# app/services/email_service.py
from flask_mail import Message
from flask import current_app, url_for
from app.extensions import mail

def send_credentials_email(email, clinic_name, password):
    """Send login credentials when a clinic is approved"""
    msg = Message(
        subject=f"Your {clinic_name} Clinic Credentials",
        recipients=[email],
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    msg.body = f"""
    Your clinic registration has been approved!
    
    Clinic: {clinic_name}
    Login URL: {url_for('auth.login', _external=True)}
    Username: {email}
    Password: {password}
    
    You must change your password after first login.
    """
    mail.send(msg)

def send_rejection_email(email, clinic_name, reason):
    """Send rejection notification with reason"""
    msg = Message(
        subject=f"Your {clinic_name} Clinic Application Status",
        recipients=[email],
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    msg.body = f"""
    Your clinic registration has been reviewed.
    
    Clinic: {clinic_name}
    Status: Rejected
    Reason: {reason}
    
    You may submit a new application after addressing the issues.
    """
    mail.send(msg)
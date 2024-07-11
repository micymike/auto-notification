from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///appointments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model for storing appointments
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    doctor_id = db.Column(db.Integer, nullable=False)
    doctor_name = db.Column(db.String(50), nullable=False)
    doctor_specialty = db.Column(db.String(50), nullable=False)
    appointment_datetime = db.Column(db.DateTime, nullable=False)

def send_email(to_email, subject, body):
    from_email = "youremail@example.com"
    from_password = "yourpassword"

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.example.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        logger.info(f"Email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")

@app.route('/bookAppointment', methods=['POST'])
def book_appointment():
    try:
        data = request.json
        user_name = data.get('appointmentName')
        user_email = data.get('appointmentEmail')
        doctor_id = data.get('doctor')
        appointment_date = data.get('appointmentDate')
        appointment_time = data.get('appointmentTime')

        doctors = [
            {'id': 1, 'name': 'Dr. John Doe', 'specialty': 'Cardiology'},
            {'id': 2, 'name': 'Dr. Jane Smith', 'specialty': 'Neurology'},
            # Add other doctors as needed
        ]

        doctor = next((doc for doc in doctors if doc['id'] == int(doctor_id)), None)
        if not doctor:
            raise ValueError("Doctor not found")

        appointment_datetime_str = f"{appointment_date} {appointment_time}"
        appointment_datetime = datetime.strptime(appointment_datetime_str, '%Y-%m-%d %H:%M')

        new_appointment = Appointment(
            name=user_name,
            email=user_email,
            doctor_id=doctor_id,
            doctor_name=doctor['name'],
            doctor_specialty=doctor['specialty'],
            appointment_datetime=appointment_datetime
        )
        db.session.add(new_appointment)
        db.session.commit()

        subject = "Appointment Confirmation"
        body = f"""
        Dear {user_name},

        Your appointment has been confirmed:

        Doctor: {doctor['name']} ({doctor['specialty']})
        Date and Time: {appointment_datetime.strftime('%A, %B %d, %Y at %I:%M %p')}

        Please arrive 15 minutes before your scheduled appointment time.

        If you need to reschedule or cancel, please contact us at least 24 hours in advance.

        Thank you for choosing our service!

        Best regards,
        Elderly companion
        """
        send_email(user_email, subject, body)

        return jsonify({'status': 'success', 'message': 'Appointment booked successfully'})
    except Exception as e:
        logger.error(f"Error booking appointment: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables
    socketio.run(app, host='0.0.0.0', port=5000)

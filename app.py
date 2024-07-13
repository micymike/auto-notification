import os
import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///appointments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configure the Gemini API key
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Set up the Gemini model
model = genai.GenerativeModel('gemini-pro')

# SMTP configuration (hardcoded for simplicity)
smtp_server = 'smtp.gmail.com'
smtp_port = 587
smtp_username = 'elderlyhealthcompanion@gmail.com'  
smtp_password = 'aeamekctnxnnikbe'  
smtp_from_email = 'elderlyhealthcompanion@gmail.com'  

# Define Appointment model
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100), nullable=False)
    user_email = db.Column(db.String(120), nullable=False)
    doctor_name = db.Column(db.String(100), nullable=False)
    appointment_time = db.Column(db.DateTime, nullable=False)

# List of doctors
doctors = [
    { "id": 1, "name": "Dr. Michael Moses", "specialty": "Cardiology" },
    { "id": 2, "name": "Dr. Purity Ogeke", "specialty": "Neurology" },
    { "id": 3, "name": "Dr. Sarah Williams", "specialty": "Geriatrics" },
    { "id": 4, "name": "Dr. Lorna Karugo", "specialty": "Orthopedics" },
    { "id": 5, "name": "Dr. Solace Ace", "specialty": "Endocrinology" },
    { "id": 6, "name": "Dr. James Wilson", "specialty": "Pulmonology" },
    { "id": 7, "name": "Dr. Mercy Wanjiku", "specialty": "Rheumatology" },
    { "id": 8, "name": "Dr. Elizabeth Lizzie", "specialty": "Gastroenterology" },
    { "id": 9, "name": "Dr. Jennifer Martinez", "specialty": "Nephrology" },
    { "id": 10, "name": "Dr. Kidus Elias", "specialty": "Oncology" }
]

# Generate message using Gemini
def generate_message(prompt, enhance_accuracy=False):
    try:
        if enhance_accuracy:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.95,
                    top_k=50,
                    max_output_tokens=100
                )
            )
        else:
            response = model.generate_content(prompt)

        message = response.text
        if not message.endswith(('.', '!', '?')):
            message += '...'
        logger.debug(f"Generated message: {message}")
        return message
    except genai.exceptions.APIException as e:
        logger.error(f"Gemini API Exception: {e}")
        return "Error generating message. Gemini API Exception."
    except Exception as e:
        logger.error(f"Error generating message: {str(e)}")
        return "Error generating message. Please try again."

# Send email using SMTP
def send_email(recipient_email, subject, body):
    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = smtp_from_email
        msg['To'] = recipient_email

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(smtp_from_email, recipient_email, msg.as_string())

        logger.info(f"Email sent to {recipient_email}")
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise

# Schedule the job for notifications
scheduler = BackgroundScheduler()
scheduler.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/doctors')
def get_doctors():
    return jsonify(doctors)

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.json
        name = data['name']
        condition = data['condition']
        age = data['age']
        email = data['email']
        notification_type = data['notificationType']
        time = data.get('time')
        enhance_accuracy = data.get('enhance_accuracy', False)

        if notification_type == 'motivational':
            prompt = f"Generate a motivational message for {name}, who is {age} years old and has {condition}. The message should be encouraging and uplifting."
        elif notification_type == 'medicational':
            prompt = f"Generate a gentle medication reminder for {name}, who is {age} years old and has {condition}. The reminder should be friendly and supportive."
        elif notification_type == 'advice':
            prompt = f"Provide helpful advice for managing {condition} for {name}, who is {age} years old. The advice should be practical and easy to follow."
        else:
            return jsonify({'status': 'error', 'message': 'Invalid notification type'}), 400

        message = generate_message(prompt, enhance_accuracy)
        
        # Add sign-off to the message
        message += "\n\nBest regards,\nStarlets Team"

        if time:
            # Schedule the notification
            schedule_time = datetime.strptime(time, "%H:%M").time()
            now = datetime.now()
            schedule_datetime = datetime.combine(now.date(), schedule_time)

            if schedule_datetime <= now:
                schedule_datetime += timedelta(days=1)  

            scheduler.add_job(send_email, 'date', run_date=schedule_datetime, args=[email, 'Your Notification', message])
            response_message = f"Notification scheduled for {time}. You will receive it at {email} at the specified time."
        else:
            # Send notification immediately
            send_email(email, 'Your Notification', message)
            response_message = f"Notification sent successfully. Please check your email at {email}."

        logger.info(f"Successfully processed submission for {name}, {notification_type}, email: {email}")
        return jsonify({'status': 'success', 'message': response_message})
    except Exception as e:
        logger.error(f"Error processing submission: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    try:
        data = request.json
        user_name = data['appointmentName']
        user_email = data['appointmentEmail']
        doctor_id = int(data['doctor'])
        appointment_date = data['appointmentDate']
        appointment_time = data['appointmentTime']

        # Validate doctor_id
        doctor = next((d for d in doctors if d['id'] == doctor_id), None)
        if not doctor:
            return jsonify({'status': 'error', 'message': 'Invalid doctor selected'}), 400

        # Combine date and time
        appointment_datetime = datetime.strptime(f"{appointment_date} {appointment_time}", "%Y-%m-%d %H:%M")

        # Create new appointment
        new_appointment = Appointment(
            user_name=user_name,
            user_email=user_email,
            doctor_name=doctor['name'],
            appointment_time=appointment_datetime
        )
        db.session.add(new_appointment)
        db.session.commit()

        # Send confirmation email
        subject = "Appointment Confirmation"
        body = f"""
        Dear {user_name},

        Your appointment has been confirmed:

        Doctor: {doctor['name']} ({doctor['specialty']})
        Date and Time: {appointment_datetime.strftime('%A, %B %d, %Y at %I:%M %p')}

        Please arrive 15 minutes before your scheduled appointment time. You will be guided to your specified doctor.

        If you need to reschedule or cancel, please contact us at least 24 hours in advance. Feel free to reply to this email for such service.

        Thank you for choosing our service!

        Best regards,
        Starlets Team
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
        db.create_all()  
    socketio.run(app, debug=True)
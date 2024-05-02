import pandas as pd
from pymongo import MongoClient
import gspread
import bcrypt
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from oauth2client.service_account import ServiceAccountCredentials
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
import pyotp
import qrcode
import io
import base64
from datetime import datetime
import os
import shutil
from django.http import JsonResponse
from django.conf import settings

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import speech_recognition as sr


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .pdfsummarizer import summarize_pdf


scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name(r'static\teacher-sheets-7ca6f414fc77.json', scopes)
google_sheet_url = 'https://docs.google.com/spreadsheets/d/1AQugi52kUJy_qiu1_KncUmWG2E-wGbC94YDWd6hwG2Y/edit#gid=0'

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USERNAME = 'contact.fithealth23@gmail.com'
SMTP_PASSWORD = 'ebrh bilu ygsn zrkw'

def hash_password(email):
    hashed = bcrypt.hashpw(email.encode(), bcrypt.gensalt())
    return hashed.decode()

def get_google_sheet_data(sheet_url):
    gc = gspread.authorize(credentials)
    worksheet = gc.open_by_url(sheet_url).sheet1
    data = worksheet.get_all_values()
    headers = data.pop(0)
    df = pd.DataFrame(data, columns=headers)
    return df

def upload_image(image_name):
    # Chemin de la source de l'image
    source_path = os.path.join("image", image_name)
    
    if os.path.exists(source_path):
        # Chemin de destination dans le dossier "uploads"
        destination_folder = os.path.join(settings.STATIC_ROOT, "uploads")
        # Assurez-vous que le dossier de destination existe, sinon créez-le
        os.makedirs(destination_folder, exist_ok=True)
        # Chemin de l'image à copier
        source_image = source_path
        # Copier l'image dans le dossier de destination
        shutil.copy(source_image, destination_folder)
        # Renvoyer le chemin de l'image dans le dossier "uploads"
        return os.path.join(destination_folder, image_name)
    else:
        return None

@api_view(['GET'])
def insert_data_to_mongodb_and_send_email(request):
    client = MongoClient('mongodb://127.0.0.1:27017/nest?directConnection=true')
    db = client.nest
    collection = db.users 
    print("Insert Data")
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    data_dict = get_google_sheet_data(google_sheet_url).to_dict(orient='records')
    for user_data in data_dict:
        email = user_data["email"]
        if collection.find_one({"email": email}) is None:
            hashed_password = hash_password(email)
            user_data["password"] = hashed_password
            user_data["isVerify"] = True
            user_data["role"] = []
            user_data["image"] = upload_image("avatar.png")
            # Add createdAt and updatedAt fields
            current_time = datetime.now()
            user_data["createdAt"] = current_time
            user_data["updatedAt"] = current_time

            # Generate and store TOTP secret for 2FA
            totp_secret = pyotp.random_base32()
            user_data["twoFactorSecret"] = totp_secret
            
            # Generate QR code image
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(pyotp.totp.TOTP(totp_secret).provisioning_uri(email, issuer_name="DocSharePeak"))
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert QR code image to base64
            buffered = io.BytesIO()
            qr_img.save(buffered)
            qr_img_base64 = base64.b64encode(buffered.getvalue()).decode()
            qr_img_url = f"data:image/png;base64,{qr_img_base64}"
            user_data["qrCodeDataUrl"] = qr_img_url
            
            # Insert user data into MongoDB
            collection.insert_one(user_data)
            
            # Send email with 2FA setup
            send_email_with_2fa(server, user_data["email"], email, totp_secret, buffered.getvalue())
    server.quit()
    client.close()
    return Response({"message": "Inserted Successfully!"}, status=status.HTTP_200_OK)

def send_email_with_2fa(server, to_email, password, totp_secret, qr_img_buffer):
    # Generate TOTP code
    totp = pyotp.TOTP(totp_secret)
    totp_code = totp.now()

    # Attach QR code image to email
    qr_img_attachment = MIMEImage(qr_img_buffer, _subtype="png")
    qr_img_attachment.add_header("Content-Disposition", "attachment", filename="qr_code.png")

    msg = MIMEMultipart()
    msg['From'] = SMTP_USERNAME
    msg['To'] = to_email
    msg['Subject'] = 'DocSharePeak 2FA setup'

    body = f'Hello,\n\nYour password for DocSharePeak is: {password}\n\n'
    body += 'To enhance security, we have enabled two-factor authentication (2FA) for your account.\n'
    body += f'Please use the following TOTP code to set up 2FA in your preferred authenticator app: {totp_code}\n\n'
    body += 'Scan the QR code below to add your account to the authenticator app.\n\n'
    body += 'Best regards,\nThe DocSharePeak Team'
    msg.attach(MIMEText(body, 'plain'))
    msg.attach(qr_img_attachment)

    server.send_message(msg)





@csrf_exempt
def speech_to_text(request):
    if request.method == 'POST':
        r = sr.Recognizer()
        try:
            with sr.Microphone(device_index=0) as source:
                print("Speak:")
                audio = r.listen(source)
                text = r.recognize_google(audio)
                return JsonResponse({'text': text})
        except Exception as e:
            return JsonResponse({'error': str(e)})
    else:
        return JsonResponse({'error': 'Invalid request method'})





@csrf_exempt
def summarize_pdf_view(request):
    if request.method == 'POST' and request.FILES.get('pdf_file'):
        try:
            pdf_file = request.FILES['pdf_file']
            summary = summarize_pdf(pdf_file)
            return JsonResponse({'summary': summary})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request'}, status=400)
from django.urls import path
from .views import insert_data_to_mongodb_and_send_email
from .views import speech_to_text
from .views import summarize_pdf_view

urlpatterns = [
    path('insertdata/', insert_data_to_mongodb_and_send_email, name='insert_data_to_mongodb_and_send_email'),
    path('speech-to-text/', speech_to_text, name='speech_to_text'),
    path('summarize-pdf/', summarize_pdf_view, name='summarize_pdf'),
]
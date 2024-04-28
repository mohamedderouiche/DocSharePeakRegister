from django.urls import path
from .views import insert_data_to_mongodb_and_send_email

urlpatterns = [
    path('insertdata/', insert_data_to_mongodb_and_send_email, name='insert_data_to_mongodb_and_send_email'),

]
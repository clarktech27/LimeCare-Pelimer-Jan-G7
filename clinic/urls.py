from django.urls import path

from . import views

app_name = 'clinic'

urlpatterns = [
    path('patients/', views.patient_list, name='patient_list'),
    path('patients/new/', views.patient_create, name='patient_create'),
    path('patients/<int:pk>/', views.patient_detail, name='patient_detail'),
    path('patients/<int:pk>/edit/', views.patient_edit, name='patient_edit'),
    path('patients/<int:pk>/toggle/', views.patient_toggle_active, name='patient_toggle_active'),
    path('appointments/', views.appointment_list, name='appointment_list'),
    path('appointments/new/', views.appointment_create, name='appointment_create'),
    path('appointments/<int:pk>/', views.appointment_detail, name='appointment_detail'),
    path('appointments/<int:pk>/reschedule/', views.appointment_edit, name='appointment_edit'),
    path('appointments/<int:pk>/status/', views.appointment_status, name='appointment_status'),
]
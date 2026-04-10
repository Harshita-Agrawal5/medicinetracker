from django.urls import path
from . import views

urlpatterns = [
    # Home / Auth
    path('', views.redirect_user, name='home'),   # ✅ FIXED
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),

    # Doctor
    path('doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/patient/<int:patient_id>/', views.patient_detail, name='patient_detail'),
    path('doctor/patient/<int:patient_id>/add_medicine/', views.add_medicine, name='add_medicine'),

    # Patient
    path('patient/', views.user_dashboard, name='user_dashboard'),
    path('take/<int:med_id>/', views.take_medicine, name='take_medicine'),
    path('missed/<int:med_id>/', views.mark_missed, name='mark_missed'),

    # Caregiver
    path('caregiver/', views.caregiver_dashboard, name='caregiver_dashboard'),

    # Medicine History
    path('history/', views.medicine_history, name='medicine_history'),
    path('history/<int:patient_id>/', views.medicine_history, name='medicine_history_patient'),

    # (duplicate kept as you said don't delete)
    path('doctor/patient/<int:patient_id>/', views.patient_detail, name='patient_detail'),

    path('dispenser/', views.dispenser_status, name='dispenser_status'),
    
     path('api/pill-event/', views.pill_event),
    path('dashboard/', views.dashboard),
]

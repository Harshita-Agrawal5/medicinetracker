from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Profile, Medicine, MedicineHistory, DispenserSlot, PillEvent


# ----------------- SAFE PROFILE GET -----------------
def get_user_role(user):
    profile, created = Profile.objects.get_or_create(user=user)
    return profile


# ----------------- DASHBOARD REDIRECT -----------------
def redirect_dashboard(user):
    profile = get_user_role(user)

    if profile.role == 'doctor':
        return redirect('doctor_dashboard')
    elif profile.role == 'patient':
        return redirect('user_dashboard')
    elif profile.role == 'caregiver':
        return redirect('caregiver_dashboard')
    else:
        return redirect('login')


def redirect_user(request):
    if request.user.is_authenticated:
        return redirect_dashboard(request.user)
    return redirect('login')


# ----------------- AUTH -----------------
def login_view(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect_dashboard(user)
        else:
            return render(request, 'main/login.html', {'error': 'Invalid credentials'})

    return render(request, 'main/login.html')


def signup_view(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        role = request.POST.get('role', '').lower()

        if not role:
            return render(request, 'main/signup.html', {'error': 'Please select a role'})
        if User.objects.filter(username=username).exists():
            return render(request, 'main/signup.html', {'error': 'User already exists'})

        user = User.objects.create_user(username=username, password=password)
        Profile.objects.create(user=user, role=role)
        return redirect('login')

    return render(request, 'main/signup.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def home(request):
    return redirect_dashboard(request.user)


# ----------------- DOCTOR DASHBOARD -----------------
@login_required
def doctor_dashboard(request):
    profile = get_user_role(request.user)
    if profile.role != 'doctor':
        return redirect('home')

    patients = User.objects.filter(profile__role='patient')
    return render(request, 'main/doctor_dashboard.html', {'patients': patients})


@login_required
def patient_detail(request, patient_id):
    profile = get_user_role(request.user)
    if profile.role != 'doctor':
        return redirect('home')

    patient = get_object_or_404(User, id=patient_id, profile__role='patient')
    medicines = Medicine.objects.filter(patient=patient).order_by('time')

    taken_count = medicines.filter(status='taken').count()
    missed_count = medicines.filter(status='missed').count()
    pending_count = medicines.count() - taken_count - missed_count

    return render(request, 'main/patient_detail.html', {
        'patient': patient,
        'medicines': medicines,
        'taken_count': taken_count,
        'missed_count': missed_count,
        'pending_count': pending_count,
    })


@login_required
def add_medicine(request, patient_id):
    profile = get_user_role(request.user)
    if profile.role != 'doctor':
        return redirect('home')

    patient = get_object_or_404(User, id=patient_id, profile__role='patient')

    if request.method == "POST":
        name = request.POST.get('name')
        dosage = request.POST.get('dosage')
        time = request.POST.get('time')
        notes = request.POST.get('notes', '')

        if not name or not dosage or not time:
            messages.error(request, "Please fill all required fields!")
            return redirect('add_medicine', patient_id=patient.id)

        med = Medicine.objects.create(
            patient=patient,
            name=name,
            dosage=dosage,
            time=time,
            notes=notes,
            prescribed_by=request.user,
            status='pending'
        )

        MedicineHistory.objects.create(medicine=med, action='pending')
        messages.success(request, "Medicine added successfully!")
        return redirect('patient_detail', patient_id=patient.id)

    return render(request, 'main/add_medicine.html', {'patient': patient})


# ----------------- PATIENT DASHBOARD -----------------
@login_required
def user_dashboard(request):
    profile = get_user_role(request.user)
    if profile.role != 'patient':
        return redirect('home')

    user = request.user

    # 🔥 FORCE FRESH DATA FROM DATABASE (IMPORTANT ADDITION)
    medicines = Medicine.objects.filter(patient=user).order_by('-id')

    # 🔥 DEBUG (optional but useful while testing)
    print("DASHBOARD MEDICINES:", list(medicines.values('name', 'status')))

    taken_count = medicines.filter(status='taken').count()
    missed_count = medicines.filter(status='missed').count()
    pending_count = medicines.count() - taken_count - missed_count

    caregivers = User.objects.filter(profile__role='caregiver')
    
    print("USER:", request.user.username)
    print("MEDICINES:", list(Medicine.objects.filter(patient=request.user).values('name', 'status')))

    # ----------------- EXISTING CAREGIVER LOGIC (UNCHANGED) -----------------
    if request.method == 'POST' and 'caregiver' in request.POST:
        caregiver_id = request.POST.get('caregiver')
        if caregiver_id:
            caregiver_user = User.objects.get(id=caregiver_id)
            profile.caregiver = caregiver_user
            profile.save()
            return redirect('user_dashboard')

    # 🔥 EXTRA SAFETY: always re-fetch latest profile (ADD ONLY)
    profile.refresh_from_db()

    return render(request, 'main/user_dashboard.html', {
        'medicines': medicines,
        'taken_count': taken_count,
        'missed_count': missed_count,
        'pending_count': pending_count,
        'profile': profile,
        'caregivers': caregivers,
    })


@login_required
def take_medicine(request, med_id):
    med = get_object_or_404(Medicine, id=med_id, patient=request.user)
    med.status = 'taken'
    med.save()
    MedicineHistory.objects.create(medicine=med, action='taken')
    return redirect('user_dashboard')


@login_required
def mark_missed(request, med_id):
    med = get_object_or_404(Medicine, id=med_id, patient=request.user)
    med.status = 'missed'
    med.save()
    MedicineHistory.objects.create(medicine=med, action='missed')
    return redirect('user_dashboard')


# ----------------- CAREGIVER DASHBOARD -----------------
@login_required
def caregiver_dashboard(request):
    profile = get_user_role(request.user)
    if profile.role != 'caregiver':
        return redirect('home')

    patients = User.objects.filter(profile__caregiver=request.user)
    medicines = Medicine.objects.filter(patient__in=patients).order_by('time')

    taken_count = medicines.filter(status='taken').count()
    missed_count = medicines.filter(status='missed').count()
    pending_count = medicines.count() - taken_count - missed_count

    return render(request, 'main/caregiver_dashboard.html', {
        'patients': patients,
        'medicines': medicines,
        'taken_count': taken_count,
        'missed_count': missed_count,
        'pending_count': pending_count,
    })


# ----------------- MEDICINE HISTORY -----------------
@login_required
def medicine_history(request, patient_id=None):
    profile = get_user_role(request.user)
    role = profile.role

    if role == 'doctor':
        medicines = Medicine.objects.filter(prescribed_by=request.user)
        if patient_id:
            medicines = medicines.filter(patient__id=patient_id)

    elif role == 'patient':
        medicines = Medicine.objects.filter(patient=request.user)

    elif role == 'caregiver':
        medicines = Medicine.objects.filter(patient__profile__caregiver=request.user)

    else:
        return redirect('home')

    history = MedicineHistory.objects.filter(medicine__in=medicines).order_by('-timestamp')

    return render(request, 'main/medicine_history.html', {
        'history': history,
        'role': role
    })


# ----------------- DISPENSER -----------------
@login_required
def dispenser_status(request):
    profile = get_user_role(request.user)
    role = profile.role

    if role not in ['patient', 'caregiver']:
        return redirect('home')

    if role == 'patient':
        slots = DispenserSlot.objects.filter(patient=request.user)
    else:
        slots = DispenserSlot.objects.filter(patient__profile__caregiver=request.user)

    return render(request, 'main/dispenser_status.html', {'slots': slots})


# ----------------- API (POSTMAN INTEGRATION) -----------------
@api_view(['POST'])
def pill_event(request):
    event = request.data.get("event")
    patient_name = request.data.get("patient_name")
    medicine_name = request.data.get("medicine_name")

    if not (event and patient_name and medicine_name):
        return Response({"error": "Missing data"})

    patient = User.objects.filter(username__iexact=patient_name.strip()).first()

    if not patient:
        return Response({"error": "Patient not found"})

    from datetime import datetime

    # 🔥 CREATE MEDICINE ENTRY
    med = Medicine.objects.create(
        patient=patient,
        name=medicine_name.strip(),
        time=datetime.now().time(),
        status="taken" if event == "pill_taken" else "missed"
    )

    MedicineHistory.objects.create(
        medicine=med,
        action=event
    )

    # 🔥 UPDATE DISPENSER SLOT (FIXED)
    slot = DispenserSlot.objects.filter(
        patient=patient,
        medicine_name__iexact=medicine_name.strip()
    ).first()

    if slot:
        if slot.quantity > 0:
            slot.quantity -= 1
            slot.save()
            print("✅ Quantity updated:", slot.quantity)
        else:
            print("⚠️ No stock left")
    else:
        print("❌ No slot found for this medicine")

    # 🔥 RETURN AFTER EVERYTHING
    return Response({
        "message": "New entry created",
        "medicine": med.name,
        "status": med.status
    })
  

 
# ----------------- DASHBOARD (EVENT VIEW) -----------------
def dashboard(request):
    events = PillEvent.objects.order_by('-timestamp')[:10]
    return render(request, "dashboard.html", {"events": events})

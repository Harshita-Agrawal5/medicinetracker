from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Profile, Medicine, MedicineHistory

# ----------------- DASHBOARD REDIRECT -----------------
def redirect_dashboard(user):
    role = user.profile.role
    if role == 'doctor':
        return redirect('doctor_dashboard')
    elif role == 'patient':
        return redirect('user_dashboard')
    elif role == 'caregiver':
        return redirect('caregiver_dashboard')
    return redirect('login')


# ----------------- AUTH -----------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect_dashboard(request.user)

    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect_dashboard(user)
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
    if request.user.profile.role != 'doctor':
        return redirect('home')

    patients = User.objects.filter(profile__role='patient')
    return render(request, 'main/doctor_dashboard.html', {'patients': patients})


@login_required
def patient_detail(request, patient_id):
    if request.user.profile.role != 'doctor':
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
    if request.user.profile.role != 'doctor':
        return redirect('home')

    patient = get_object_or_404(User, id=patient_id, profile__role='patient')

    if request.method == "POST":
        name = request.POST.get('name')
        dosage = request.POST.get('dosage')
        time = request.POST.get('time')  # e.g., "08:00"
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
    if request.user.profile.role != 'patient':
        return redirect('home')

    user = request.user
    profile = user.profile
    medicines = Medicine.objects.filter(patient=user).order_by('time')
    taken_count = medicines.filter(status='taken').count()
    missed_count = medicines.filter(status='missed').count()
    pending_count = medicines.count() - taken_count - missed_count

    # ----------------- CAREGIVER LOGIC -----------------
    caregivers = User.objects.filter(profile__role='caregiver')

    if request.method == 'POST' and 'caregiver' in request.POST:
        caregiver_id = request.POST.get('caregiver')
        if caregiver_id:
            caregiver_user = User.objects.get(id=caregiver_id)
            profile.caregiver = caregiver_user
            profile.save()
            return redirect('user_dashboard')  # reload page after update

    context = {
        'medicines': medicines,
        'taken_count': taken_count,
        'missed_count': missed_count,
        'pending_count': pending_count,
        'profile': profile,
        'caregivers': caregivers,
    }
    return render(request, 'main/user_dashboard.html', context)


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
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Profile, Medicine

@login_required
def caregiver_dashboard(request):
    user = request.user
    if user.profile.role != 'caregiver':
        return redirect('home')

    # Fetch all patients assigned to this caregiver
    patients = User.objects.filter(profile__caregiver=user)

    # Get medicines for these patients
    medicines = Medicine.objects.filter(patient__in=patients).order_by('time')

    # ✅ Calculate summary counts
    taken_count = medicines.filter(status='taken').count()
    missed_count = medicines.filter(status='missed').count()
    pending_count = medicines.count() - taken_count - missed_count

    context = {
        'patients': patients,
        'medicines': medicines,
        'taken_count': taken_count,
        'missed_count': missed_count,
        'pending_count': pending_count,
    }
    return render(request, 'main/caregiver_dashboard.html', context)


# ----------------- MEDICINE HISTORY -----------------
@login_required
def medicine_history(request, patient_id=None):
    user = request.user
    role = user.profile.role

    if role == 'doctor':
        if patient_id:
            medicines = Medicine.objects.filter(prescribed_by=user, patient__id=patient_id)
        else:
            medicines = Medicine.objects.filter(prescribed_by=user)
    elif role == 'patient':
        medicines = Medicine.objects.filter(patient=user)
    elif role == 'caregiver':
        medicines = Medicine.objects.filter(patient__profile__caregiver=user)
    else:
        return redirect('home')

    history = MedicineHistory.objects.filter(medicine__in=medicines).order_by('-timestamp')
    return render(request, 'main/medicine_history.html', {'history': history, 'role': role})
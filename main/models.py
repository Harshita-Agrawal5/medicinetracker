from django.db import models
from django.contrib.auth.models import User

# ----------------- PROFILE -----------------
class Profile(models.Model):
    ROLE_CHOICES = (
        ('doctor', 'Doctor'),
        ('patient', 'Patient'),
        ('caregiver', 'Caregiver'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    # Only add caregiver reference for patient profiles
    caregiver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='patients',  # Caregiver can access all assigned patients
        limit_choices_to={'profile__role': 'caregiver'}  # Only users with role caregiver
    )

    def __str__(self):
        return f"{self.user.username} ({self.role})"


# ----------------- MEDICINE -----------------
class Medicine(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('taken', 'Taken'),
        ('missed', 'Missed'),
    )

    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='medicines')
    name = models.CharField(max_length=100)
    dosage = models.CharField(max_length=50, blank=True, null=True)
    time = models.TimeField()
    date = models.DateField(auto_now_add=True)
    prescribed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescriptions'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, null=True)  # Added notes field

    def __str__(self):
        return f"{self.name} for {self.patient.username} ({self.status})"


# ----------------- MEDICINE HISTORY -----------------
class MedicineHistory(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=20, choices=Medicine.STATUS_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medicine.name} {self.action} at {self.timestamp}"
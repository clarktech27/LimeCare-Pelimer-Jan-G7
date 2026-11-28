import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import Profile

from .forms import AppointmentForm, PatientForm
from .models import Appointment, Patient

ALL_ROLES = (Profile.ADMIN, Profile.DOCTOR, Profile.NURSE, Profile.REGISTRATION)
# BR-09: only Registration Staff, Nurses and Admin can register or change patients.
MANAGE_ROLES = (Profile.ADMIN, Profile.NURSE, Profile.REGISTRATION)
# F-06: Registration Staff and Admin book appointments; Doctors view their own schedule.
BOOKING_ROLES = (Profile.ADMIN, Profile.REGISTRATION)
APPOINTMENT_VIEW_ROLES = (Profile.ADMIN, Profile.REGISTRATION, Profile.DOCTOR)


def _can_manage(user):
    return user.profile.role in MANAGE_ROLES


@role_required(*ALL_ROLES)
def patient_list(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', 'active')
    patients = Patient.objects.all()
    if status == 'active':
        patients = patients.filter(is_active=True)
    elif status == 'inactive':
        patients = patients.filter(is_active=False)
    for term in q.split():
        patients = patients.filter(
            Q(first_name__icontains=term) | Q(middle_name__icontains=term)
            | Q(last_name__icontains=term) | Q(patient_number__icontains=term)
        )
    page = Paginator(patients, 10).get_page(request.GET.get('page'))
    return render(request, 'clinic/patient_list.html', {
        'page': page, 'q': q, 'status': status,
        'query': urlencode({'q': q, 'status': status}),
        'can_manage': _can_manage(request.user),
    })


@role_required(*ALL_ROLES)
def patient_detail(request, pk):
    patient = get_object_or_404(Patient.objects.select_related('registered_by'), pk=pk)
    return render(request, 'clinic/patient_detail.html', {
        'patient': patient, 'can_manage': _can_manage(request.user),
        'can_book': patient.is_active and request.user.profile.role in BOOKING_ROLES,
    })


@role_required(*MANAGE_ROLES)
def patient_create(request):
    form = PatientForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            patient = form.save(commit=False)
            patient.registered_by = request.user
            patient.save()
            messages.success(request, f'{patient.full_name} was registered as {patient.patient_number}.')
            return redirect('clinic:patient_detail', pk=patient.pk)
        messages.error(request, 'Please correct the errors below.')
    return render(request, 'clinic/patient_form.html', {'form': form, 'title': 'Register Patient'})


@role_required(*MANAGE_ROLES)
def patient_edit(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    form = PatientForm(request.POST or None, instance=patient)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            messages.success(request, 'Patient record updated successfully.')
            return redirect('clinic:patient_detail', pk=patient.pk)
        messages.error(request, 'Please correct the errors below.')
    return render(request, 'clinic/patient_form.html', {
        'form': form, 'title': f'Edit {patient.patient_number}', 'patient': patient,
    })


@require_POST
@role_required(*MANAGE_ROLES)
def patient_toggle_active(request, pk):
    # BR-13: a patient is deactivated instead of deleted.
    patient = get_object_or_404(Patient, pk=pk)
    patient.is_active = not patient.is_active
    patient.save(update_fields=['is_active', 'updated_at'])
    state = 'reactivated' if patient.is_active else 'deactivated'
    messages.success(request, f'{patient.full_name} was {state}.')
    return redirect('clinic:patient_detail', pk=patient.pk)


# ---------------------------------------------------------------------------
# Appointment scheduling (core feature, F-06)
# ---------------------------------------------------------------------------

STATUS_ACTIONS = {
    'complete': Appointment.COMPLETED,
    'cancel': Appointment.CANCELLED,
    'no_show': Appointment.NO_SHOW,
}


def _visible_appointments(user):
    """A Doctor only sees their own appointments; Admin and Registration Staff see all."""
    appointments = Appointment.objects.select_related(
        'patient', 'doctor__user', 'department', 'created_by',
    )
    if user.profile.role == Profile.DOCTOR:
        appointments = appointments.filter(doctor__user=user)
    return appointments


def _can_modify_appointment(user, appointment):
    """Admin can change any appointment; Registration Staff only the ones they booked."""
    role = user.profile.role
    return role == Profile.ADMIN or (role == Profile.REGISTRATION and appointment.created_by_id == user.pk)


@role_required(*APPOINTMENT_VIEW_ROLES)
def appointment_list(request):
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', Appointment.SCHEDULED)
    date_text = request.GET.get('date', '').strip()
    appointments = _visible_appointments(request.user)

    if status in dict(Appointment.STATUS_CHOICES):
        appointments = appointments.filter(status=status)
    else:
        status = 'all'
    if date_text:
        try:
            appointments = appointments.filter(scheduled_at__date=datetime.date.fromisoformat(date_text))
        except ValueError:
            messages.error(request, 'Enter a valid date.')
            date_text = ''
    for term in q.split():
        appointments = appointments.filter(
            Q(patient__first_name__icontains=term) | Q(patient__last_name__icontains=term)
            | Q(patient__patient_number__icontains=term)
        )
    appointments = appointments.order_by('scheduled_at' if status == Appointment.SCHEDULED else '-scheduled_at')
    page = Paginator(appointments, 10).get_page(request.GET.get('page'))
    return render(request, 'clinic/appointment_list.html', {
        'page': page, 'q': q, 'status': status, 'date': date_text,
        'status_choices': Appointment.STATUS_CHOICES,
        'query': urlencode({'q': q, 'status': status, 'date': date_text}),
        'can_book': request.user.profile.role in BOOKING_ROLES,
    })


@role_required(*APPOINTMENT_VIEW_ROLES)
def appointment_detail(request, pk):
    appointment = get_object_or_404(_visible_appointments(request.user), pk=pk)
    can_modify = _can_modify_appointment(request.user, appointment)
    return render(request, 'clinic/appointment_detail.html', {
        'appointment': appointment,
        'can_modify': can_modify,
        'can_act': can_modify and appointment.status == Appointment.SCHEDULED,
    })


def _save_appointment(request, form, success_message):
    """Save the form; the database unique constraint is the last line of defence for BR-16."""
    appointment = form.save(commit=False)
    if not appointment.pk:
        appointment.created_by = request.user
    try:
        with transaction.atomic():
            appointment.save()
    except IntegrityError:
        form.add_error('scheduled_at', 'This doctor already has a Scheduled appointment at that date and time.')
        return None
    messages.success(request, success_message)
    return appointment


@role_required(*BOOKING_ROLES)
def appointment_create(request):
    form = AppointmentForm(request.POST or None, initial={'patient': request.GET.get('patient')})
    if request.method == 'POST':
        if form.is_valid():
            appointment = _save_appointment(request, form, 'Appointment booked successfully.')
            if appointment:
                return redirect('clinic:appointment_detail', pk=appointment.pk)
        messages.error(request, 'Please correct the errors below.')
    return render(request, 'clinic/appointment_form.html', {'form': form, 'title': 'Book Appointment'})


@role_required(*BOOKING_ROLES)
def appointment_edit(request, pk):
    appointment = get_object_or_404(_visible_appointments(request.user), pk=pk)
    if not _can_modify_appointment(request.user, appointment):
        raise PermissionDenied
    if appointment.status != Appointment.SCHEDULED:  # BR-18
        messages.error(request, f'Only Scheduled appointments can be rescheduled. This one is {appointment.status}.')
        return redirect('clinic:appointment_detail', pk=appointment.pk)
    form = AppointmentForm(request.POST or None, instance=appointment)
    if request.method == 'POST':
        if form.is_valid():
            if _save_appointment(request, form, 'Appointment rescheduled successfully.'):
                return redirect('clinic:appointment_detail', pk=appointment.pk)
        messages.error(request, 'Please correct the errors below.')
    return render(request, 'clinic/appointment_form.html', {
        'form': form, 'title': 'Reschedule Appointment', 'appointment': appointment,
    })


@require_POST
@role_required(*BOOKING_ROLES)
def appointment_status(request, pk):
    appointment = get_object_or_404(_visible_appointments(request.user), pk=pk)
    if not _can_modify_appointment(request.user, appointment):
        raise PermissionDenied
    new_status = STATUS_ACTIONS.get(request.POST.get('action'))
    try:
        appointment.change_status(new_status)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f'Appointment marked as {appointment.status}.')
    return redirect('clinic:appointment_detail', pk=appointment.pk)
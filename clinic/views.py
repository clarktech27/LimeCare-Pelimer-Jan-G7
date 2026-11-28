from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import Profile

from .forms import PatientForm
from .models import Patient

ALL_ROLES = (Profile.ADMIN, Profile.DOCTOR, Profile.NURSE, Profile.REGISTRATION)
# BR-09: only Registration Staff, Nurses and Admin can register or change patients.
MANAGE_ROLES = (Profile.ADMIN, Profile.NURSE, Profile.REGISTRATION)


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
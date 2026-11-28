from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse

from .decorators import role_required
from .forms import ProfileUpdateForm, RegisterForm, UserUpdateForm
from .models import Department, Profile

User = get_user_model()


def _dashboard_for(user):
    return 'accounts:admin_dashboard' if user.profile.role == Profile.ADMIN else 'accounts:staff_dashboard'


class RoleLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse(_dashboard_for(self.request.user))

    def form_valid(self, form):
        messages.success(self.request, f'Welcome back, {form.get_user().get_username()}!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Invalid username or password.')
        return super().form_invalid(form)


def register(request):
    if request.user.is_authenticated:
        return redirect('accounts:home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully. Welcome to LimeCare!')
            return redirect('accounts:home')
        messages.error(request, 'Please correct the errors below.')
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def home(request):
    """Send each user to the dashboard for their role."""
    return redirect(_dashboard_for(request.user))


@role_required(Profile.ADMIN)
def admin_dashboard(request):
    users = User.objects.select_related('profile', 'profile__department').order_by('-date_joined')
    ctx = {
        'total_users': users.count(),
        'admin_count': users.filter(profile__role=Profile.ADMIN).count(),
        'staff_count': users.exclude(profile__role=Profile.ADMIN).count(),
        'department_count': Department.objects.filter(is_active=True).count(),
        'users': users[:10],
    }
    return render(request, 'accounts/admin_dashboard.html', ctx)


@role_required(Profile.DOCTOR, Profile.NURSE, Profile.REGISTRATION)
def staff_dashboard(request):
    return render(request, 'accounts/staff_dashboard.html')


@login_required
def profile(request):
    return render(request, 'accounts/profile.html', {'profile_user': request.user})


@login_required
def profile_edit(request):
    # Always operates on request.user: users can only edit their own profile.
    user_form = UserUpdateForm(request.POST or None, instance=request.user)
    profile_form = ProfileUpdateForm(request.POST or None, instance=request.user.profile)
    if request.method == 'POST':
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
        messages.error(request, 'Please correct the errors below.')
    return render(request, 'accounts/profile_edit.html', {'user_form': user_form, 'profile_form': profile_form})
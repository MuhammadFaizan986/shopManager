from django.shortcuts import redirect
from django.contrib.auth import logout
from django.contrib.auth.views import (
    LoginView as AuthLoginView,
    PasswordChangeView as AuthPasswordChangeView,
    PasswordChangeDoneView as AuthPasswordChangeDoneView,
)
from django.contrib import messages
from django.urls import reverse_lazy


class LoginView(AuthLoginView):
    template_name = 'accounts/login.html'


def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'You have been logged out.')
    return redirect('accounts:login')


class PasswordChangeView(AuthPasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')


class PasswordChangeDoneView(AuthPasswordChangeDoneView):
    template_name = 'accounts/password_change_done.html'

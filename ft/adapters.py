from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import PermissionDenied


class NoNewUsersAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False  # Disable signups

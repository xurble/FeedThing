from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.internal.httpkit import get_client_ip as resolve_client_ip


# Used when the client IP cannot be resolved (missing/invalid REMOTE_ADDR, proxy
# headers misconfigured). Rate limits then share one bucket for those requests;
# set ALLAUTH_TRUSTED_CLIENT_IP_HEADER / ALLAUTH_TRUSTED_PROXY_COUNT for real IPs.
_UNKNOWN_CLIENT_IP = "0.0.0.0"


class NoNewUsersAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False  # Disable signups

    def get_client_ip(self, request):
        try:
            ip = resolve_client_ip(request)
        except KeyError:
            ip = None
        if not ip:
            return _UNKNOWN_CLIENT_IP
        return ip

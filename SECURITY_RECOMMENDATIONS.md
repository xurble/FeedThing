# Security Recommendations for FeedThing

## High Priority Issues

### 1. SSL Certificate Verification Disabled
**Issue**: In `ft/views.py` line 205, SSL verification is disabled with `verify=False`.
```python
ret = requests.get(feed, headers=headers, verify=False, timeout=15)
```

**Risk**: This makes the application vulnerable to man-in-the-middle attacks when fetching feeds.

**Fix**: Enable SSL verification and handle SSL errors gracefully:
```python
try:
    ret = requests.get(feed, headers=headers, verify=True, timeout=15)
except requests.exceptions.SSLError:
    # Log the SSL error and handle appropriately
    logging.warning(f"SSL verification failed for feed: {feed}")
    # Either skip the feed or try with a custom CA bundle
    ret = requests.get(feed, headers=headers, verify=True, timeout=15)
```

### 2. Unprotected Public Endpoint
**Issue**: The `/refresh/` endpoint is publicly accessible without authentication.

**Risk**: Anyone can trigger feed updates, potentially causing DoS or resource exhaustion.

**Fix**: Add IP-based restrictions or basic authentication:
```python
# In settings.py, add allowed IPs for refresh endpoint
REFRESH_ALLOWED_IPS = ['127.0.0.1', '::1']  # Add your server IPs

# In views.py, add IP check to read_request_listener
def read_request_listener(request):
    client_ip = request.META.get('REMOTE_ADDR')
    if client_ip not in settings.REFRESH_ALLOWED_IPS:
        return HttpResponse("Forbidden", status=403)
    # ... rest of the function
```

### 3. Information Disclosure in Error Messages
**Issue**: Detailed error messages with stack traces are returned to users in `addfeed` function.

**Risk**: Sensitive system information could be exposed to attackers.

**Fix**: Log detailed errors server-side but return generic error messages to users:
```python
except Exception as xx:
    logging.error(f"Error in addfeed: {xx}", exc_info=True)
    return HttpResponse("<div>An error occurred while processing the feed</div>")
```

## Medium Priority Issues

### 4. Missing Security Headers
**Issue**: No security headers are configured to protect against common attacks.

**Fix**: Add security middleware and headers in `settings.py`:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    # ... rest of middleware
]

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")  # Adjust as needed
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")   # Adjust as needed
```

### 5. XML Parsing Vulnerability
**Issue**: Using `minidom.parseString()` without proper validation in OPML import.

**Risk**: XML External Entity (XXE) attacks.

**Fix**: Use secure XML parsing:
```python
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ParseError

def importopml(request):
    try:
        # Disable external entity processing
        ET.XMLParser(target=None, encoding=None)
        theFile = request.FILES["opml"].read()
        root = ET.fromstring(theFile)
        # ... rest of parsing logic
    except ParseError:
        return HttpResponse("Invalid OPML file")
```

### 6. Rate Limiting Missing
**Issue**: No rate limiting on public endpoints or user actions.

**Fix**: Add Django rate limiting:
```python
# Install django-ratelimit: pip install django-ratelimit
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='10/m', method='GET')
def read_request_listener(request):
    # ... existing code

@login_required
@ratelimit(key='user', rate='5/m', method='POST')
def addfeed(request):
    # ... existing code
```

## Low Priority Issues

### 7. Session Security
**Fix**: Add session security settings:
```python
# In settings.py
SESSION_COOKIE_SECURE = True  # Only send over HTTPS
SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript access
SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
CSRF_COOKIE_SECURE = True
```

### 8. Admin Security
**Fix**: Change admin URL to something less obvious:
```python
# In urls.py
urlpatterns = [
    path("admin-secret-path/", admin.site.urls),  # Change from "admin/"
    # ... rest of URLs
]
```

### 9. Database Security
**Fix**: Add database connection security in `settings_server.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'feedthing',
        'USER': 'auser',
        'PASSWORD': 'apassword',
        'HOST': '',
        'PORT': '',
        'OPTIONS': {
            'init_command': "SET default_storage_engine=INNODB",
            'sql_mode': 'STRICT_TRANS_TABLES',  # Strict SQL mode
        },
    }
}
```

### 10. Logging Security
**Fix**: Add security-focused logging:
```python
# In settings.py LOGGING configuration
'loggers': {
    'django.security': {
        'handlers': ['file'],
        'level': 'INFO',
        'propagate': True,
    },
    'ft.security': {
        'handlers': ['file'],
        'level': 'WARNING',
        'propagate': True,
    },
}
```

## Additional Recommendations

### 11. Dependency Security
- Run `safety check` regularly to check for vulnerable dependencies
- Consider using `pip-audit` for additional security scanning
- Keep Django and all dependencies updated

### 12. Environment Configuration
- Ensure `DEBUG = False` in production
- Use environment variables for sensitive configuration
- Implement proper secret management

### 13. Regular Security Monitoring
- Set up log monitoring for failed authentication attempts
- Monitor for unusual feed fetching patterns
- Regular security audits of the application

## Implementation Priority

1. **Immediate**: Fix SSL verification and secure the refresh endpoint
2. **This week**: Add security headers and fix error message disclosure
3. **This month**: Implement rate limiting and secure XML parsing
4. **Ongoing**: Regular dependency updates and security monitoring

These recommendations focus on practical, low-effort changes that will significantly improve the security posture of the FeedThing application without requiring major architectural changes.
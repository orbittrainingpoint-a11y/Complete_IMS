# Security Review Document
## Orbit ERP — Institute Management System

**Document Version:** 3.0
**Date:** 2026-07-13
**Status:** Production

---

## 1. Authentication

### 1.1 Primary Login

- Django's built-in `authenticate()` + `login()` — bcrypt-compatible password hashing
- Session-based auth (`sessionid` cookie, `HttpOnly`, `Secure` in production)
- All views decorated with `@login_required` (redirect to `/accounts/login/`)
- Login and logout events written to `AuditLog` table with IP address

### 1.2 CRM SSO

- HMAC-SHA256 token with timestamp component
- Token TTL: **90 seconds** — prevents replay attacks
- Shared secret `CRM_SSO_SECRET` stored in `settings.py` (not in code or DB)
- Token verified on both sides before session is created

### 1.3 Public Token Forms

- Certificate request forms at `/cert-request/<uuid:token>/` are unauthenticated
- Secured by UUID4 token (128-bit entropy) — link is single-use in practice (one submission sets status=submitted and the form displays a success page)
- No sensitive personal data returned to the client — form is submit-only

---

## 2. Authorization

### 2.1 Role Checks

All privileged operations check `request.user.userprofile.role` or `request.user.is_superuser`.

| Protection | Where Applied |
|------------|--------------|
| Admin-only decorator/check | User management, settings, audit log, delete certificates, delete proposals |
| Accounts access | Refund list, refund confirm |
| Own-data filter | Sales executive sees only their own registrations |
| 1-hour edit lock | Sales executives blocked from editing registrations after 60 minutes |

### 2.2 Object-Level Access

Sales executives are filtered at query level:
```python
if role == 'sales_executive':
    registrations = registrations.filter(consultant=request.user.get_full_name())
```

### 2.3 Insecure Direct Object Reference (IDOR)

- All `<pk>` lookups use `get_object_or_404` — returns 404 for unknown IDs
- No tenant isolation needed (single-tenant system)

---

## 3. Input Handling

### 3.1 SQL Injection

- All ORM queries use parameterized queries by default
- Raw SQL (used in `_revenue_for_user`) uses Django `connection.cursor()` with `%s` placeholders — not string formatting

### 3.2 Cross-Site Scripting (XSS)

- Django template engine auto-escapes all `{{ variable }}` output
- `mark_safe()` is not used on user-supplied content
- Rich text content (e.g. `class_feedback`, `client_notes`) rendered as plain text, never as HTML

### 3.3 File Uploads

- File uploads use `FileField` / `ImageField` — Django validates MIME type for images via Pillow
- Files stored under `MEDIA_ROOT` (not in static files directory)
- Media files served by Nginx, not Django, in production — no server-side execution of uploaded files

### 3.4 CSRF

- Django `CsrfViewMiddleware` active on all POST requests
- All forms include `{% csrf_token %}`
- AJAX POST requests in custom JS include `X-CSRFToken` header or `csrfmiddlewaretoken` field

---

## 4. Session & Cookie Security

| Setting | Value |
|---------|-------|
| `SESSION_COOKIE_HTTPONLY` | True (Django default) |
| `SESSION_COOKIE_SECURE` | True on VPS (HTTPS enforced by Nginx) |
| `CSRF_COOKIE_SECURE` | True on VPS |
| `X-Frame-Options` | DENY (Django default via `XFrameOptionsMiddleware`) |
| `Secure` header | Via Nginx HTTPS |

---

## 5. Sensitive Data Handling

### 5.1 Passwords

- User passwords hashed via Django's PBKDF2+SHA256 (default)
- CRM passwords synced using `werkzeug.security.generate_password_hash` (scrypt/PBKDF2 compatible)
- No plaintext passwords stored or logged

### 5.2 Secrets in Settings

The following are stored in `settings.py` only — never in the codebase, DB, or logs:
- `SECRET_KEY`
- `CRM_SSO_SECRET`
- `EMAIL_HOST_PASSWORD`
- `CRM_DB_PASSWORD`

### 5.3 Personally Identifiable Information

Stored in `invoices_registration`: name, DOB, passport number, Emirates ID, UID, phone, email, nationality. This data:
- Is accessible only to authenticated staff
- Is not exposed in any public API response
- Email addresses used only for cert request and refund notification emails

---

## 6. Audit Logging

All login and logout events are logged to `invoices_auditlog`:
```python
@receiver(user_logged_in)
def on_user_logged_in(sender, user, request, **kwargs):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
    AuditLog.objects.create(user=user, action='login', ip_address=ip, ...)
```

Audit log viewable by Admin only at `/audit/`.

---

## 7. Infrastructure Security

| Layer | Security Measure |
|-------|-----------------|
| Transport | HTTPS via Let's Encrypt (auto-renews with Certbot) |
| Web server | Nginx — no directory listing, no server version in headers |
| Application | DEBUG=False on VPS — no stack traces exposed to users |
| Database | MariaDB on localhost only — not exposed to external network |
| SSH | Key-based auth recommended for VPS access |
| Static/media | Nginx serves directly — Django app not in the path |

---

## 8. Known Limitations and Accepted Risks

| Item | Risk Level | Notes |
|------|-----------|-------|
| No rate limiting on login | Low-Medium | Brute force possible; mitigated by strong passwords policy |
| No MFA | Low | Single-tenant internal tool; SSO is HMAC-only |
| Cert request token is not invalidated after use | Low | UUID entropy makes guessing impractical; status check blocks re-submission |
| Email SMTP via Gmail app password | Low | App password can be rotated independently from account password |
| pymysql direct CRM DB write | Low | Internal only; not exposed externally; credentials in settings.py |
| Media files served at predictable paths | Low | Staff-uploaded files; no sensitive docs publicly accessible without knowing exact filename |

---

## 9. Recommendations

1. **Rate limit `/accounts/login/`** — use `django-axes` or similar to block repeated failures
2. **Add MFA** for admin accounts (TOTP via `django-otp`)
3. **Certificate request token expiry** — add a `expires_at` field; reject form submissions after 7 days
4. **Rotate `CRM_SSO_SECRET`** periodically — recommend quarterly rotation
5. **Separate media disk** — avoid storing uploads on the same partition as the OS
6. **Database backups** — automate nightly `mysqldump` to a separate backup location

---

*Document updated: 2026-07-13*
*Version 3.0 — adds public cert-request token security, refund access control, v3 role matrix updates*

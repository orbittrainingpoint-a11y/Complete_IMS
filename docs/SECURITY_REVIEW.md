# Security Review Document
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06
**Review Type:** Internal Code Audit (Updated)

---

## 1. Executive Summary

Since the v1.0 security review (2026-06-25), all three CRITICAL issues have been resolved. The system is now deployed on VPS with environment-variable-driven configuration, Gunicorn + Apache (replacing the old Windows/IIS setup), and HTTPS termination at the proxy.

**Overall Risk Level: LOW–MEDIUM** for a production SaaS deployment.
**Remaining risks** are medium-priority operational hardening items.

---

## 2. Resolved Issues (Since v1.0)

### ~~SEC-01: Debug Mode in Production~~ — FIXED
`DEBUG` is now read from `DJANGO_DEBUG` environment variable, defaulting to `False`.

```python
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'
```

### ~~SEC-02: Hardcoded Secret Key~~ — FIXED
`SECRET_KEY` is now loaded from `DJANGO_SECRET_KEY` environment variable.

```python
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'fallback-dev-only-key')
```

### ~~SEC-03: Hardcoded Database Password~~ — FIXED
All database credentials are now in `/var/www/html/orbit/.env.erp`.

### ~~SEC-04 (HIGH): Root Database User~~ — FIXED
Production uses a dedicated `orbit_app` MySQL user with per-database grants (SELECT, INSERT, UPDATE, DELETE only on `orbit_invoice` and `leads`).

### ~~SEC-B4: Admin Username Hardcode~~ — FIXED
The legacy `if request.user.username == 'admin':` check has been replaced with `is_admin_user(request.user)`, which checks `UserProfile.role`.

---

## 3. Current Security Architecture

### 3.1 Authentication
- Django session-based authentication (`django.contrib.auth`)
- Passwords hashed with PBKDF2-SHA256 (Django default, 870,000 iterations as of Django 5)
- `@login_required` decorator enforced on all non-public views
- Role-based access: `is_admin_user()` checks `UserProfile.role in ('admin',) or user.is_superuser`
- No public API — all endpoints require active session

### 3.2 CSRF Protection
- All HTML forms use `{% csrf_token %}`
- AJAX POSTs must include `X-CSRFToken` header
- `CSRF_TRUSTED_ORIGINS` set to `https://orbittraining.online,https://www.orbittraining.online`

### 3.3 Transport Security
- Apache terminates HTTPS with Let's Encrypt SSL certificate
- HTTP → HTTPS redirect enforced at Apache level (301 permanent)
- `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` — Django trusts Apache's `X-Forwarded-Proto` header

### 3.4 SSO Bridge Security
- Algorithm: HMAC-SHA256
- Token payload: `base64url({"u": username, "t": unix_timestamp})`
- Token TTL: 90 seconds
- Signature comparison: `hmac.compare_digest()` (constant-time, prevents timing attacks)
- Shared secret: `CRM_SSO_SECRET` stored in env files, not in source code
- HTTPS-only: tokens are only transmitted over TLS-encrypted connections in production

### 3.5 Audit Logging
- Login and logout events are automatically logged via Django signals
- `AuditLog` entries include: `user`, `action`, `model_name`, `object_id`, `object_repr`, `ip_address`, `timestamp`
- IP address extracted from `HTTP_X_FORWARDED_FOR` (first address), then `REMOTE_ADDR`
- Audit log view is admin-only

### 3.6 File Upload Security
- Uploaded files stored in `media/` directory with structured paths
- Media files served directly by Apache (not through Django view)
- File type validation is done at the Django form/model level

---

## 4. Remaining Security Items

### SEC-05 (MEDIUM): SSO Secret Rotation Policy
**Current:** `CRM_SSO_SECRET` is a static string that has never been rotated.
**Risk:** If the secret leaks, an attacker could forge SSO tokens. The 90-second TTL limits damage but does not eliminate it.
**Recommendation:**
- Establish a rotation schedule (e.g., every 6 months or immediately if exposed)
- Update both `.env.erp` and `.env.crm` simultaneously, then restart both services

---

### SEC-06 (MEDIUM): No Rate Limiting on Login
**Current:** No brute-force protection on `POST /accounts/login/`
**Risk:** Automated credential stuffing or password guessing is possible.
**Recommendation:**
- Add `django-axes` (failed login lockout) or `django-ratelimit`
- Configure account lockout after 10 failed attempts

---

### SEC-07 (MEDIUM): Media File Access Control
**Current:** All files in `media/` are publicly accessible via direct URL if the path is known.
**Risk:** Uploaded documents (certificates, trade licenses, VAT certificates) could be accessed without authentication.
**Recommendation:**
- For sensitive uploads (portal/trade_license/, portal/vat/), serve via Django view with `@login_required` using `FileResponse`
- Or configure Apache to require authentication for the `media/portal/` path

---

### SEC-08 (MEDIUM): Session Lifetime
**Current:** Default Django session expiry (browser session only — expires on browser close).
**Risk:** Users on shared computers who forget to log out leave sessions accessible.
**Recommendation:**
```python
SESSION_COOKIE_AGE = 43200  # 12 hours in seconds
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True  # Slide the expiry on activity
```

---

### SEC-09 (LOW): X-Frame-Options / Clickjacking
**Current:** `XFrameOptionsMiddleware` is in `INSTALLED_APPS` with default `DENY`.
**Status:** Already mitigated by Django default.
**No action needed.**

---

### SEC-10 (LOW): CRM Internal API Authentication
**Current:** CRM `/api/internal/lead/<id>` endpoint is protected by `Authorization: Bearer <CRM_SSO_SECRET>` header.
**Risk (low):** If the VPS internal network is compromised, this API could be queried. The secret is shared with the SSO token, so rotating SSO secret also rotates API auth.
**Recommendation:** Consider a separate API key for internal API vs SSO token, providing independent revocation.

---

### SEC-11 (LOW): CRM DB Write Access from ERP
**Current:** The `sync_user_to_crm()` function in views.py writes directly to the CRM MySQL database using `pymysql` with the credentials from `CRM_DB_*` env variables.
**Risk:** The ERP process has INSERT/UPDATE access to the CRM database. A bug in ERP could corrupt CRM data.
**Recommendation:** Replace with a CRM API endpoint for user sync, so the two databases are only connected at the application layer, not the DB layer.

---

### SEC-12 (LOW): Django Admin Exposure
**Current:** `/admin/` is enabled and accessible.
**Risk:** Default path is a well-known target for automated attacks.
**Recommendation:**
```python
# settings.py — use a non-guessable admin path
# In urls.py:
path('orbit-control-panel/', admin.site.urls),
```
Or restrict `/admin/` to internal IP in Apache.

---

### SEC-13 (INFO): ALLOWED_HOSTS Configuration
**Status:** Set via `ALLOWED_HOSTS` env variable in `.env.erp`. Properly configured for production.
**No action needed.**

---

### SEC-14 (INFO): Password Hashing (CRM User Sync)
**Current:** `sync_user_to_crm()` creates CRM user records with werkzeug `pbkdf2:sha256` hashes (so Flask-Login can authenticate them).
**Status:** Acceptable — werkzeug pbkdf2 is a secure password hashing scheme.
**No action needed.**

---

## 5. Security Checklist

| Check | Status |
|-------|--------|
| DEBUG=False in production | PASS |
| SECRET_KEY from env var | PASS |
| Database password from env var | PASS |
| Dedicated DB user (not root) | PASS |
| HTTPS / TLS | PASS |
| CSRF protection on forms | PASS |
| CSRF trusted origins configured | PASS |
| Login required on views | PASS |
| Admin hardcode removed | PASS |
| SSO token TTL (90s) | PASS |
| HMAC constant-time comparison | PASS |
| Audit log for login/logout | PASS |
| Role-based access control | PASS |
| X-Frame-Options DENY | PASS |
| Rate limiting on login | MISSING |
| Session timeout configured | MISSING |
| SSO secret rotation policy | MISSING |
| Media file auth for sensitive docs | MISSING |
| Separate CRM API for user sync | LOW PRIORITY |
| Non-guessable admin URL | LOW PRIORITY |

---

## 6. Incident Response Notes

If a security incident occurs:

1. **Suspected SSO token leak:** Update `CRM_SSO_SECRET` in both `.env.erp` and `.env.crm` immediately, then `sudo systemctl restart orbit-erp orbit-crm`
2. **Suspected DB credential leak:** Change DB password in MySQL and update `.env.erp`, restart `orbit-erp`
3. **Audit log review:** Navigate to `/audit/` (admin login required) — filters: user, action, date range, IP address
4. **Django secret key compromise:** Rotate `DJANGO_SECRET_KEY` — note this invalidates all existing sessions and signed cookies, logging out all users

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*

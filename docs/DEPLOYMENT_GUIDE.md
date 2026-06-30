# Deployment Guide
## Orbit ERP — Institute Management System

**Document Version:** 1.0  
**Date:** 2026-06-25

---

## 1. Prerequisites

### 1.1 Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Runtime |
| MySQL / MariaDB | 8.0+ / 10.4+ | Database |
| Git | Any | Version control |
| XAMPP | 8.x | Development stack (Windows) |
| IIS | 10+ | Production web server (Windows) |

### 1.2 System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 2 GB | 4 GB |
| Disk | 5 GB | 20 GB |
| CPU | 2 cores | 4 cores |
| OS | Windows 10 / Server 2016 | Windows Server 2022 |

---

## 2. Local Development Setup

### 2.1 Clone / Extract Project

```powershell
# The project is located at:
D:\Insittute management system\orbit-system\invoice_project\
```

### 2.2 Create Python Virtual Environment

```powershell
cd "D:\Insittute management system\orbit-system"
python -m venv myenv
myenv\Scripts\activate
```

### 2.3 Install Dependencies

```powershell
cd invoice_project
pip install -r server_requirements.txt

# If mysqlclient fails on Windows, install mysqlclient wheel:
pip install mysqlclient

# Additional packages needed at runtime:
pip install Pillow WeasyPrint reportlab PyPDF2
```

### 2.4 Database Setup

**Step 1: Start MySQL/MariaDB**

XAMPP users: Start MySQL from XAMPP Control Panel

**Step 2: Create Database**

```sql
-- Run in MySQL CLI or phpMyAdmin
CREATE DATABASE orbit_invoice
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;
```

**Step 3: Import SQL Dump**

```powershell
# Via XAMPP MySQL CLI
C:\xampp\mysql\bin\mysql.exe -u root orbit_invoice < "D:\Insittute management system\orbiterp.sql"

# If collation error, use the converted file:
# (Replace utf8mb4_0900_ai_ci → utf8mb4_general_ci first)
```

**Step 4: Update settings.py**

```python
# File: invoice_project/invoice_project/settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'orbit_invoice',
        'USER': 'root',
        'PASSWORD': '',          # XAMPP default: no password
        # 'PASSWORD': 'Orbit20232024',  # Original server password
        'HOST': 'localhost',
        'PORT': '3306',
    }
}
```

### 2.5 Run Migrations (if needed)

```powershell
cd "D:\Insittute management system\orbit-system\invoice_project"
myenv\Scripts\python manage.py migrate --run-syncdb
```

### 2.6 Start Development Server

```powershell
myenv\Scripts\python manage.py runserver 0.0.0.0:8000
```

**Access at:** `http://localhost:8000/`

### 2.7 Create Superuser (if new DB)

```powershell
myenv\Scripts\python manage.py createsuperuser
```

---

## 3. Static & Media Files

### 3.1 Collect Static Files

```powershell
myenv\Scripts\python manage.py collectstatic --no-input
```

### 3.2 Media Directory

The `media/` directory contains user-uploaded files (193MB). For development, ensure this directory exists:

```powershell
# These directories are automatically created on first upload:
media\certificates\
media\course_contents\
media\khda_certificates\
media\proposal_logos\
media\proposal_logos_white\
media\registration_forms\
media\trainer_profiles\
media\company_profiles\
```

---

## 4. Production Deployment (IIS + wfastcgi)

### 4.1 Install FastCGI

1. Open IIS Manager
2. Install Application Request Routing (ARR) and URL Rewrite modules
3. Install Python with wfastcgi:
   ```powershell
   pip install wfastcgi
   wfastcgi-enable
   ```

### 4.2 IIS Configuration (web.config)

The project includes `web.config` in `invoice_project/`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="PythonHandler"
           path="*"
           verb="*"
           modules="FastCgiModule"
           scriptProcessor="C:\path\to\python.exe|C:\path\to\wfastcgi.py"
           resourceType="Unspecified"
           requireAccess="Script"/>
    </handlers>
  </system.webServer>
  <appSettings>
    <add key="WSGI_HANDLER" value="invoice_project.wsgi.application"/>
    <add key="PYTHONPATH" value="D:\Insittute management system\orbit-system\invoice_project"/>
    <add key="DJANGO_SETTINGS_MODULE" value="invoice_project.settings"/>
  </appSettings>
</configuration>
```

### 4.3 Production Settings Changes

Before deploying to production, update `settings.py`:

```python
# SECURITY
DEBUG = False
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'your-secure-key-here')
ALLOWED_HOSTS = ['your-domain.com', 'www.your-domain.com', '10.255.254.23']

# Database (use env variables)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'orbit_invoice'),
        'USER': os.environ.get('DB_USER', 'orbit_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': 'localhost',
        'PORT': '3306',
    }
}

# Timezone (UAE)
TIME_ZONE = 'Asia/Dubai'
```

---

## 5. Environment Variables

Create a `.env` file (never commit to git):

```env
DJANGO_SECRET_KEY=your-very-long-random-secret-key-here
DB_NAME=orbit_invoice
DB_USER=orbit_user
DB_PASSWORD=your-database-password
DJANGO_DEBUG=False
```

---

## 6. Database Backup

### 6.1 Export (Backup)

```powershell
# XAMPP
C:\xampp\mysql\bin\mysqldump.exe -u root orbit_invoice > backup_$(Get-Date -Format 'yyyyMMdd').sql

# MySQL 8.0
mysqldump -u root -p orbit_invoice > backup.sql
```

### 6.2 Restore

```powershell
# XAMPP
C:\xampp\mysql\bin\mysql.exe -u root orbit_invoice < backup.sql
```

---

## 7. URL Access Reference

| URL | Page |
|-----|------|
| `/` | Main orbit dashboard |
| `/dashboard/` | Invoice dashboard |
| `/accounts/login/` | Login page |
| `/admin/` | Django admin |
| `/register/` | Student registration |
| `/student-dashboard/` | Student list |
| `/corporate_dashboard/` | Corporate list |
| `/create_invoice/` | New invoice |
| `/quotation/create/` | New quotation |
| `/certificates/` | Certificate list |
| `/proposals/` | Proposal list |
| `/lead/` | CRM dashboard |
| `/courses/` | Course list |
| `/coupons/` | Coupon management |
| `/trainer-profile/list/` | Trainer profiles |
| `/company-profile/list/` | Company profiles |

---

## 8. Troubleshooting

### MySQL Connection Error
```
django.db.utils.OperationalError: (2003, "Can't connect to MySQL server")
```
**Fix:** Ensure MySQL/MariaDB service is running. XAMPP: Start MySQL from Control Panel.

### Collation Error on Import
```
ERROR 1273 (HY000): Unknown collation: 'utf8mb4_0900_ai_ci'
```
**Fix:** Replace `utf8mb4_0900_ai_ci` with `utf8mb4_general_ci` in SQL file before importing.

### Missing mysqlclient
```
ModuleNotFoundError: No module named 'MySQLdb'
```
**Fix:** `pip install mysqlclient` — may need Visual C++ Build Tools on Windows.

### Static Files Not Found
```
Page loads but CSS/JS missing
```
**Fix:** Run `python manage.py collectstatic` and ensure `STATIC_ROOT` is correctly configured.

### Media Files 404
**Fix:** Add media URL handler in development:
```python
# urls.py (development only)
from django.conf import settings
from django.conf.urls.static import static
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

*Document prepared for Orbit Training Point ERP System*  
*Generated: 2026-06-25*

# Orbit ERP — Institute Management System

**Organization:** Orbit Training Point  
**Framework:** Django 5.0.6  
**Database:** MySQL / MariaDB  
**Version:** Production

---

## Quick Start

### 1. Start MySQL (XAMPP)
Open XAMPP Control Panel → Start MySQL

### 2. Activate Virtual Environment
```powershell
cd "D:\Insittute management system\orbit-system"
myenv\Scripts\activate
```

### 3. Start Application
```powershell
cd invoice_project
python manage.py runserver 0.0.0.0:8000
```

### 4. Open in Browser
```
http://localhost:8000/
```

---

## Database Setup (First Time)

```powershell
# Create database
C:\xampp\mysql\bin\mysql.exe -u root -e "CREATE DATABASE orbit_invoice CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"

# Import data
C:\xampp\mysql\bin\mysql.exe -u root orbit_invoice < "D:\Insittute management system\orbiterp.sql"
```

> **Note for XAMPP (MariaDB):** Replace `utf8mb4_0900_ai_ci` with `utf8mb4_general_ci` in the SQL file before importing.

---

## Project Structure

```
D:\Insittute management system\
├── orbit-system/
│   ├── invoice_project/          ← Django project
│   │   ├── invoice_project/      ← Settings, URLs
│   │   ├── invoices/             ← Main app (models, views, forms)
│   │   ├── manage.py
│   │   ├── media/                ← User uploads (193MB)
│   │   └── server_requirements.txt
│   └── myenv/                    ← Python virtual environment
├── orbiterp.sql                  ← Database dump
├── README.md                     ← This file
└── docs/                         ← All documentation
    ├── PRD.md                    ← Product Requirements
    ├── TRD.md                    ← Technical Requirements
    ├── FRD.md                    ← Functional Requirements
    ├── DATABASE_STRUCTURE.md     ← Full schema documentation
    ├── DATA_DICTIONARY.md        ← Field definitions
    ├── SYSTEM_ARCHITECTURE.md    ← Architecture diagrams
    ├── API_REFERENCE.md          ← Endpoint reference
    ├── MODULE_GUIDE.md           ← Per-module technical guide
    ├── DEPLOYMENT_GUIDE.md       ← Setup & deployment instructions
    ├── USER_MANUAL.md            ← Staff user guide
    └── SECURITY_REVIEW.md        ← Security findings & fixes
```

---

## System Modules

| Module | URL | Description |
|--------|-----|-------------|
| Dashboard | `/` | Business KPIs and overview |
| Invoices | `/dashboard/` | Sales & purchase invoices |
| Student Registration | `/student-dashboard/` | Individual registrations |
| Corporate Registration | `/corporate_dashboard/` | Company registrations |
| Courses | `/courses/` | Training course catalog |
| Certificates | `/certificates/` | Issue & track certificates |
| Quotations | `/quotation/` | Client quotations |
| Proposals | `/proposals/` | Training proposals |
| CRM / Leads | `/lead/` | Lead tracking & follow-ups |
| Trainer Profiles | `/trainer-profile/list/` | Trainer CV management |
| Company Profiles | `/company-profile/list/` | Company profile management |
| Coupons | `/coupons/` | Discount coupon codes |
| Admin | `/admin/` | Django admin panel |

---

## Database Summary

| Category | Tables | Records |
|----------|--------|---------|
| Users | 6 auth tables | 54 users |
| Courses | 2 tables | 239 courses |
| Registrations | 3 tables | 853 students |
| Invoices | 4 tables | 1,156 invoices |
| Quotations | 2 tables | 217 quotations |
| Certificates | 3 tables | 254 certificates |
| Proposals | 1 table | 90 proposals |
| CRM | 6 tables | 18 leads |
| Other | 9 tables | — |
| **Total** | **35 tables** | **~11,000+ records** |

---

## Key Configuration

**File:** `orbit-system/invoice_project/invoice_project/settings.py`

```python
DATABASE = {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': 'orbit_invoice',
    'USER': 'root',
    'PASSWORD': 'Orbit20232024',   # Change for XAMPP (no password)
    'HOST': 'localhost',
    'PORT': '',
}
```

---

## Dependencies

```
Django==5.0.6
mysqlclient==2.2.4
asgiref==3.8.1
sqlparse==0.5.0
tzdata==2024.1
wfastcgi==3.0.0 (production IIS only)
```

---

## Documentation Index

| Document | Purpose |
|----------|---------|
| [PRD](docs/PRD.md) | What the product does and why |
| [TRD](docs/TRD.md) | Technical implementation details |
| [FRD](docs/FRD.md) | Detailed functional specifications |
| [Database Structure](docs/DATABASE_STRUCTURE.md) | Complete schema with all tables and FKs |
| [Data Dictionary](docs/DATA_DICTIONARY.md) | Field definitions and allowed values |
| [System Architecture](docs/SYSTEM_ARCHITECTURE.md) | Architecture diagrams and patterns |
| [API Reference](docs/API_REFERENCE.md) | All URL endpoints and AJAX APIs |
| [Module Guide](docs/MODULE_GUIDE.md) | Per-module technical deep-dive |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | Setup and production deployment |
| [User Manual](docs/USER_MANUAL.md) | Staff guide for using the system |
| [Security Review](docs/SECURITY_REVIEW.md) | Security findings and fixes |

---

*Orbit Training Point — Internal ERP System*

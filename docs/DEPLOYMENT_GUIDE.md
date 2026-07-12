# Deployment Guide
## Orbit ERP — Institute Management System

**Document Version:** 3.0
**Date:** 2026-07-13

---

## 1. Environment Overview

| Environment | URL | Port | Service | Path |
|-------------|-----|------|---------|------|
| Local ERP | http://localhost:8000 | 8000 | `python manage.py runserver` | `D:\Insittute management system\orbit-system\invoice_project\` |
| Local CRM | http://localhost:5000 | 5000 | `flask run` | `D:\Insittute management system\leads-management\` |
| VPS ERP | https://orbittraining.online | 8001 | `orbit-erp.service` (systemd) | `/var/www/html/orbit/orbit-system/invoice_project/` |
| VPS CRM | https://crm.orbittraining.online | 5001 | `crm.service` (systemd) | `/var/www/html/orbit/leads-management/` |

---

## 2. Local Development Setup

### 2.1 Prerequisites

- Python 3.14
- XAMPP (MySQL/MariaDB running)
- Git

### 2.2 ERP Setup

```bash
# 1. Clone repo
git clone <repo-url>
cd "Insittute management system"

# 2. Create and activate venv
cd orbit-system
python -m venv venv314
venv314\Scripts\activate    # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create database
mysql -u root -e "CREATE DATABASE orbit_invoice CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 5. Import existing data
mysql -u root orbit_invoice < orbit_invoice_backup.sql

# 6. Configure settings.py
#    Set DB credentials, email app password, CRM_SSO_SECRET

# 7. Run migrations
cd invoice_project
python manage.py migrate

# 8. Start server
python manage.py runserver 8000
```

### 2.3 CRM Setup

```bash
cd "Insittute management system/leads-management"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
# Edit config: set DB, CRM_SSO_SECRET (must match ERP)
flask run --port 5000
```

---

## 3. VPS Deployment — Django ERP

### 3.1 Standard Code Deploy

```bash
# SSH into VPS
ssh user@orbittraining.online

# Pull latest
cd /var/www/html/orbit/orbit-system
git pull origin main

# Activate venv
source /var/www/html/orbit/venv_erp/bin/activate

# Migrate (always run after pull — safe if no new migrations)
cd invoice_project
python manage.py migrate

# Collect static (if CSS/JS/templates changed)
python manage.py collectstatic --noinput

# Restart
sudo systemctl restart orbit-erp.service
sudo systemctl status orbit-erp.service
```

### 3.2 Log Monitoring

```bash
# Service log
sudo journalctl -u orbit-erp.service -n 100 --no-pager

# Django error log
tail -f /var/www/html/orbit/orbit-system/invoice_project/django.log
```

### 3.3 Systemd Service File

`/etc/systemd/system/orbit-erp.service`:

```ini
[Unit]
Description=Orbit ERP Django Application
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/html/orbit/orbit-system/invoice_project
ExecStart=/var/www/html/orbit/venv_erp/bin/gunicorn \
    --workers 3 \
    --bind 0.0.0.0:8001 \
    invoice_project.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 4. VPS Deployment — Flask CRM

```bash
cd /var/www/html/orbit/leads-management
git pull origin main
sudo systemctl restart crm.service
sudo systemctl status crm.service
```

---

## 5. Running Migrations

### 5.1 Standard

```bash
source /var/www/html/orbit/venv_erp/bin/activate
cd /var/www/html/orbit/orbit-system/invoice_project
python manage.py migrate
```

### 5.2 Writing Manual Migrations (Required for New Fields)

Because `InstituteSetting` uses a closure-based upload function that Django cannot serialize, **do not run `makemigrations`**. Write migrations by hand:

1. Create `invoices/migrations/0070_<description>.py`
2. Set correct `dependencies` pointing to the prior migration
3. Include only `migrations.AddField` operations
4. Run `python manage.py migrate invoices`

**Template:**
```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('invoices', '0069_certificationrequest_class_feedback')]
    operations = [
        migrations.AddField(
            model_name='yourmodel',
            name='your_field',
            field=models.TextField(blank=True),
        ),
    ]
```

---

## 6. Nginx Configuration

```nginx
server {
    listen 80;
    server_name orbittraining.online;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name orbittraining.online;

    ssl_certificate /etc/letsencrypt/live/orbittraining.online/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/orbittraining.online/privkey.pem;

    location /static/ {
        alias /var/www/html/orbit/orbit-system/invoice_project/staticfiles/;
    }

    location /media/ {
        alias /var/www/html/orbit/orbit-system/invoice_project/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 7. Database Backup & Restore

```bash
# Backup (VPS)
mysqldump -u root orbit_invoice > /backups/orbit_invoice_$(date +%Y%m%d).sql

# Backup (local Windows)
mysqldump -u root orbit_invoice > orbit_invoice_backup.sql

# Restore
mysql -u root orbit_invoice < orbit_invoice_backup.sql
```

---

## 8. Secrets Checklist

Never commit these to git — set them directly in `settings.py` on each environment:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django cryptographic key |
| `CRM_SSO_SECRET` | HMAC secret shared between ERP and CRM |
| `EMAIL_HOST_PASSWORD` | Gmail app password |
| `CRM_DB_PASSWORD` | CRM database password |
| `DEBUG` | Must be `False` on VPS |
| `ALLOWED_HOSTS` | Must include VPS domain |

---

## 9. Post-v3 Deployment Sequence

To deploy all changes from this release cycle (commits since 2026-07-06):

```bash
# === ERP ===
cd /var/www/html/orbit/orbit-system
git pull origin main
source /var/www/html/orbit/venv_erp/bin/activate
cd invoice_project
python manage.py migrate          # applies migration 0069 (class_feedback)
python manage.py collectstatic --noinput
sudo systemctl restart orbit-erp.service

# === CRM ===
cd /var/www/html/orbit/leads-management
git pull origin main
sudo systemctl restart crm.service

# === Verify ===
sudo systemctl status orbit-erp.service
sudo systemctl status crm.service
```

---

*Document updated: 2026-07-13*
*Version 3.0 — adds v3 migration notes, manual migration warning, post-v3 deploy sequence, CRM safe delete*

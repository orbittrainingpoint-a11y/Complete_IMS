# Deployment Guide
## Orbit ERP — Institute Management System

**Document Version:** 2.0
**Date:** 2026-07-06

---

## 1. System Overview

| Component | Local Dev | VPS Production |
|-----------|-----------|----------------|
| Django ERP | `http://localhost:8000/` | Gunicorn on `:8001` |
| Flask CRM | `http://localhost:5000/` | Gunicorn on `:5001` |
| Web server | Django dev server | Apache (reverse proxy, HTTPS) |
| Domain | — | `https://orbittraining.online` |
| Database | MariaDB via XAMPP | MySQL 8 |
| DB name | orbit_invoice | orbit_invoice |
| CRM DB | leads (Flask SQLite / MySQL) | leads (MySQL) |
| Env files | local `.env` | `/var/www/html/orbit/.env.erp`, `.env.crm` |
| Services | Manual | `orbit-erp.service`, `orbit-crm.service` (systemd) |

---

## 2. Local Development Setup (Windows + XAMPP)

### 2.1 Prerequisites

| Software | Version | Purpose |
|----------|---------|---------|
| Python | 3.10+ | Runtime |
| XAMPP | 8.x | MariaDB + phpMyAdmin |
| Git | Any | Version control |

### 2.2 Django ERP Setup

```powershell
# Navigate to ERP source
cd "D:\Insittute management system\orbit-system"

# Create and activate virtual environment
python -m venv myenv
myenv\Scripts\activate

# Install dependencies
cd invoice_project
pip install -r server_requirements.txt
```

### 2.3 Database Setup (Local)

**Start MariaDB** via XAMPP Control Panel, then:

```sql
-- phpMyAdmin or MySQL CLI
CREATE DATABASE orbit_invoice
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;
```

If you have a SQL dump:
```powershell
"C:\xampp\mysql\bin\mysql.exe" -u root orbit_invoice < orbit_invoice_backup.sql
```

### 2.4 Environment Configuration (Local)

Create `D:\Insittute management system\orbit-system\invoice_project\.env`:

```ini
DJANGO_SECRET_KEY=your-local-dev-secret-key
DJANGO_DEBUG=True
DB_NAME=orbit_invoice
DB_USER=root
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=3306
CRM_SSO_SECRET=orbit-erp-crm-sso-bridge-2024-x9q3mz
CRM_URL=http://localhost:5000
ERP_URL=http://localhost:8000
```

### 2.5 Apply Migrations

```powershell
python manage.py migrate
```

> **Important:** Do not use `makemigrations` on a production-synced DB without reviewing the generated SQL. The constraint is: **never alter existing table columns or remove tables**.

### 2.6 Run Django ERP (Development)

```powershell
python manage.py runserver 8000
```

Access at: `http://localhost:8000/`

---

## 3. Flask CRM Setup (Local)

### 3.1 Navigate to CRM

```powershell
cd "D:\Insittute management system\leads-management"
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3.2 CRM Environment

Create `D:\Insittute management system\leads-management\.env`:

```ini
FLASK_SECRET_KEY=your-crm-secret
CRM_SSO_SECRET=orbit-erp-crm-sso-bridge-2024-x9q3mz
ERP_URL=http://localhost:8000
DATABASE_URL=mysql+pymysql://root:@localhost/leads
```

### 3.3 Run Flask CRM (Development)

```powershell
python app.py
```

Access at: `http://localhost:5000/`

---

## 4. VPS Production Deployment

### 4.1 Server Requirements

| Component | Spec |
|-----------|------|
| OS | Ubuntu 22.04 LTS |
| RAM | 4 GB minimum |
| Disk | 20 GB minimum |
| Python | 3.10+ |
| Web server | Apache 2.4 with `mod_proxy`, `mod_ssl` |
| DB | MySQL 8 |

### 4.2 Django ERP — Gunicorn Service

**File:** `/etc/systemd/system/orbit-erp.service`

```ini
[Unit]
Description=Orbit ERP Django Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/html/orbit/orbit-system/invoice_project
EnvironmentFile=/var/www/html/orbit/.env.erp
ExecStart=/var/www/html/orbit/orbit-system/myenv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8001 \
    invoice_project.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4.3 Flask CRM — Gunicorn Service

**File:** `/etc/systemd/system/orbit-crm.service`

```ini
[Unit]
Description=Orbit CRM Flask Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/html/orbit/leads-management
EnvironmentFile=/var/www/html/orbit/.env.crm
ExecStart=/var/www/html/orbit/leads-management/venv/bin/gunicorn \
    --workers 2 \
    --bind 127.0.0.1:5001 \
    app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4.4 Enable and Start Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable orbit-erp orbit-crm
sudo systemctl start orbit-erp orbit-crm

# Verify
sudo systemctl status orbit-erp
sudo systemctl status orbit-crm
```

---

## 5. Environment Files (VPS)

### 5.1 `/var/www/html/orbit/.env.erp`

```ini
DJANGO_SECRET_KEY=<strong-random-key-50-chars-min>
DJANGO_DEBUG=False
DB_NAME=orbit_invoice
DB_USER=orbit_app
DB_PASSWORD=<db-password>
DB_HOST=localhost
DB_PORT=3306
CRM_SSO_SECRET=orbit-erp-crm-sso-bridge-2024-x9q3mz
CRM_URL=http://127.0.0.1:5001
ERP_URL=https://orbittraining.online
CSRF_TRUSTED_ORIGINS=https://orbittraining.online,https://www.orbittraining.online
ALLOWED_HOSTS=orbittraining.online,www.orbittraining.online,127.0.0.1
CRM_DB_HOST=localhost
CRM_DB_NAME=leads
CRM_DB_USER=orbit_app
CRM_DB_PASSWORD=<db-password>
```

### 5.2 `/var/www/html/orbit/.env.crm`

```ini
FLASK_SECRET_KEY=<strong-random-key>
CRM_SSO_SECRET=orbit-erp-crm-sso-bridge-2024-x9q3mz
ERP_URL=https://orbittraining.online
DATABASE_URL=mysql+pymysql://orbit_app:<password>@localhost/leads
```

> **Note:** `CRM_SSO_SECRET` must be identical in both files. If it is changed in one, it must be updated in the other and both services must be restarted.

---

## 6. Apache Configuration (VPS)

**File:** `/etc/apache2/sites-available/orbittraining.conf`

```apache
<VirtualHost *:443>
    ServerName orbittraining.online
    ServerAlias www.orbittraining.online

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/orbittraining.online/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/orbittraining.online/privkey.pem

    # Forward real IP to Django/Flask
    RequestHeader set X-Forwarded-Proto "https"

    # Serve media files directly
    Alias /media/ /var/www/html/orbit/orbit-system/invoice_project/media/
    <Directory /var/www/html/orbit/orbit-system/invoice_project/media/>
        Options -Indexes
        Require all granted
    </Directory>

    # Serve static files directly
    Alias /static/ /var/www/html/orbit/orbit-system/invoice_project/static/
    <Directory /var/www/html/orbit/orbit-system/invoice_project/static/>
        Options -Indexes
        Require all granted
    </Directory>

    # Flask CRM at /crm/
    ProxyPreserveHost On
    ProxyPass /crm/ http://127.0.0.1:5001/crm/
    ProxyPassReverse /crm/ http://127.0.0.1:5001/crm/

    # Django ERP — everything else
    ProxyPass / http://127.0.0.1:8001/
    ProxyPassReverse / http://127.0.0.1:8001/
</VirtualHost>

<VirtualHost *:80>
    ServerName orbittraining.online
    ServerAlias www.orbittraining.online
    Redirect permanent / https://orbittraining.online/
</VirtualHost>
```

Enable and reload:

```bash
sudo a2enmod proxy proxy_http ssl headers
sudo a2ensite orbittraining
sudo systemctl reload apache2
```

---

## 7. Database Setup (VPS — MySQL 8)

```sql
-- Create DB
CREATE DATABASE orbit_invoice
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

-- Create CRM DB
CREATE DATABASE leads
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

-- Create dedicated app user
CREATE USER 'orbit_app'@'localhost' IDENTIFIED BY 'StrongPassword!';
GRANT SELECT, INSERT, UPDATE, DELETE ON orbit_invoice.* TO 'orbit_app'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE ON leads.* TO 'orbit_app'@'localhost';
FLUSH PRIVILEGES;
```

Import existing data:

```bash
mysql -u orbit_app -p orbit_invoice < orbit_invoice_backup.sql
```

> **Collation note:** Local MariaDB uses `utf8mb4_general_ci`; VPS MySQL 8 uses `utf8mb4_0900_ai_ci`. Both are functional. Do not convert collation in production without a maintenance window.

---

## 8. Static Files (Production)

```bash
cd /var/www/html/orbit/orbit-system/invoice_project
source /var/www/html/orbit/orbit-system/myenv/bin/activate
python manage.py collectstatic --noinput
```

Static files are collected to `STATIC_ROOT` and served directly by Apache (see Section 6).

---

## 9. Deployment: Updating Code on VPS

```bash
# SSH into VPS
cd /var/www/html/orbit

# Pull latest code
git pull origin main

# Activate venv
source orbit-system/myenv/bin/activate
cd orbit-system/invoice_project

# Install any new dependencies
pip install -r server_requirements.txt

# Apply new migrations (review first!)
python manage.py migrate

# Collect static
python manage.py collectstatic --noinput

# Restart services
sudo systemctl restart orbit-erp orbit-crm
```

---

## 10. Service Management Commands

```bash
# Restart
sudo systemctl restart orbit-erp
sudo systemctl restart orbit-crm

# Stop
sudo systemctl stop orbit-erp

# View logs (last 50 lines)
sudo journalctl -u orbit-erp -n 50
sudo journalctl -u orbit-crm -n 50

# Follow live logs
sudo journalctl -u orbit-erp -f
```

---

## 11. Database Backup

```bash
# Daily backup script (run via cron)
mysqldump -u orbit_app -p orbit_invoice > /backups/orbit_invoice_$(date +%Y%m%d).sql
mysqldump -u orbit_app -p leads > /backups/leads_$(date +%Y%m%d).sql

# Compress and remove files older than 30 days
gzip /backups/*.sql
find /backups/ -name "*.sql.gz" -mtime +30 -delete
```

---

## 12. SSL Certificate Renewal

```bash
# Certbot auto-renewal (should already be set up via cron/systemd timer)
sudo certbot renew --dry-run

# Manual renewal
sudo certbot renew
sudo systemctl reload apache2
```

---

## 13. Troubleshooting

| Problem | Check |
|---------|-------|
| 502 Bad Gateway | `systemctl status orbit-erp` — service may be down |
| Static files not loading | `python manage.py collectstatic` + Apache alias configured |
| Media files 403 | Apache media directory has `Require all granted` |
| CRM SSO failing | Both `.env.erp` and `.env.crm` have same `CRM_SSO_SECRET` |
| Database errors | Check `DB_USER`/`DB_PASSWORD` env vars; user has correct GRANTS |
| Session cookie issues | `CSRF_TRUSTED_ORIGINS` includes `https://orbittraining.online` |
| Login IP shows 127.0.0.1 | Apache not sending `X-Forwarded-For` — add `RequestHeader set X-Forwarded-Proto` |

---

*Document updated: 2026-07-06*
*Reflects production system at orbittraining.online*

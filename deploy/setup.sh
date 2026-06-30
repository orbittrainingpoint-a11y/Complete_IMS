#!/bin/bash
# =============================================================================
# Orbit Training - Complete IMS Deployment Script
# Domains: orbittraining.online (ERP) + crm.orbittraining.online (CRM)
# Run as root on Ubuntu VPS
# =============================================================================
set -e

APP_DIR="/var/www/html/orbit"
REPO="https://github.com/orbittrainingpoint-a11y/Complete_IMS.git"
DB_USER="orbituser"
DB_PASS="OrbitDB2024Secure!"   # CHANGE THIS
ERP_SECRET="erp-django-secret-$(openssl rand -hex 24)"
CRM_SECRET="crm-flask-secret-$(openssl rand -hex 24)"
SSO_SECRET="orbit-erp-crm-sso-bridge-2024-x9q3mz"

echo "================================================================"
echo "  Orbit Training IMS - VPS Setup"
echo "================================================================"

# ── 1. System packages ────────────────────────────────────────────
echo "[1/10] Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    libmysqlclient-dev pkg-config \
    apache2 \
    mysql-server \
    certbot python3-certbot-apache \
    git curl

# Enable Apache modules
a2enmod proxy proxy_http ssl headers rewrite
systemctl restart apache2

# ── 2. MySQL setup ────────────────────────────────────────────────
echo "[2/10] Setting up MySQL databases..."
mysql -u root <<MYSQL_SCRIPT
CREATE DATABASE IF NOT EXISTS orbit_invoice CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS leads CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON orbit_invoice.* TO '${DB_USER}'@'localhost';
GRANT ALL PRIVILEGES ON leads.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
MYSQL_SCRIPT
echo "  Databases created: orbit_invoice, leads"
echo "  DB user: ${DB_USER} / ${DB_PASS}"

# ── 3. Clone repo ─────────────────────────────────────────────────
echo "[3/10] Cloning repository..."
mkdir -p ${APP_DIR}
cd ${APP_DIR}
if [ -d ".git" ]; then
    git pull
else
    git clone ${REPO} .
fi

# ── 4. Import databases ───────────────────────────────────────────
echo "[4/10] Importing databases..."
if [ -f "${APP_DIR}/deploy/orbit_invoice.sql" ]; then
    sed 's/utf8mb4_0900_ai_ci/utf8mb4_unicode_ci/g; s/utf8mb3/utf8/g' \
        ${APP_DIR}/deploy/orbit_invoice.sql | \
        mysql -u ${DB_USER} -p${DB_PASS} orbit_invoice
    echo "  orbit_invoice imported OK"
else
    echo "  WARNING: deploy/orbit_invoice.sql not found - skipping import"
fi

if [ -f "${APP_DIR}/deploy/leads.sql" ]; then
    sed 's/utf8mb4_0900_ai_ci/utf8mb4_unicode_ci/g; s/utf8mb3/utf8/g' \
        ${APP_DIR}/deploy/leads.sql | \
        mysql -u ${DB_USER} -p${DB_PASS} leads
    echo "  leads imported OK"
else
    echo "  WARNING: deploy/leads.sql not found - skipping import"
fi

# ── 5. ERP (Django) virtual env ───────────────────────────────────
echo "[5/10] Setting up ERP Python environment..."
python3 -m venv ${APP_DIR}/venv_erp
${APP_DIR}/venv_erp/bin/pip install --upgrade pip -q
${APP_DIR}/venv_erp/bin/pip install -r ${APP_DIR}/orbit-system/invoice_project/requirements.txt -q
echo "  ERP packages installed"

# ── 6. CRM (Flask) virtual env ────────────────────────────────────
echo "[6/10] Setting up CRM Python environment..."
python3 -m venv ${APP_DIR}/venv_crm
${APP_DIR}/venv_crm/bin/pip install --upgrade pip -q
${APP_DIR}/venv_crm/bin/pip install -r ${APP_DIR}/leads-management/requirements.txt -q
echo "  CRM packages installed"

# ── 7. Environment files ──────────────────────────────────────────
echo "[7/10] Creating environment files..."
cat > ${APP_DIR}/.env.erp <<EOF
DJANGO_SECRET_KEY=${ERP_SECRET}
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=orbittraining.online,www.orbittraining.online
DB_NAME=orbit_invoice
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASS}
DB_HOST=localhost
DB_PORT=3306
CRM_SSO_SECRET=${SSO_SECRET}
CRM_URL=https://crm.orbittraining.online
ERP_URL=https://orbittraining.online
CRM_DB_HOST=localhost
CRM_DB_USER=${DB_USER}
CRM_DB_PASSWORD=${DB_PASS}
CRM_DB_NAME=leads
EOF

cat > ${APP_DIR}/.env.crm <<EOF
SESSION_SECRET=${CRM_SECRET}
DB_URI=mysql+pymysql://${DB_USER}:${DB_PASS}@localhost:3306/leads
CRM_SSO_SECRET=${SSO_SECRET}
ERP_URL=https://orbittraining.online
MAIL_USERNAME=
MAIL_PASSWORD=
EOF

chmod 600 ${APP_DIR}/.env.erp ${APP_DIR}/.env.crm
echo "  Environment files created"

# ── 8. Django: collectstatic + fake migrations ────────────────────
echo "[8/10] Django collectstatic and migrations..."
cd ${APP_DIR}/orbit-system/invoice_project
set -a; source ${APP_DIR}/.env.erp; set +a
${APP_DIR}/venv_erp/bin/python manage.py migrate --fake-initial
${APP_DIR}/venv_erp/bin/python manage.py collectstatic --noinput -v 0
mkdir -p /var/log/orbit
echo "  Django ready"

# ── 9. Systemd services ───────────────────────────────────────────
echo "[9/10] Installing systemd services..."
cp ${APP_DIR}/deploy/erp-gunicorn.service /etc/systemd/system/orbit-erp.service
cp ${APP_DIR}/deploy/crm-gunicorn.service /etc/systemd/system/orbit-crm.service
systemctl daemon-reload
systemctl enable orbit-erp orbit-crm
systemctl start orbit-erp orbit-crm
sleep 3
systemctl is-active orbit-erp && echo "  ERP service: running" || echo "  ERP service: FAILED - check: journalctl -u orbit-erp"
systemctl is-active orbit-crm && echo "  CRM service: running" || echo "  CRM service: FAILED - check: journalctl -u orbit-crm"

# ── 10. Apache virtual hosts ──────────────────────────────────────
echo "[10/10] Configuring Apache..."
cp ${APP_DIR}/deploy/orbittraining.online.conf     /etc/apache2/sites-available/
cp ${APP_DIR}/deploy/crm.orbittraining.online.conf /etc/apache2/sites-available/

# Temporarily enable HTTP-only configs for Certbot
cat > /etc/apache2/sites-available/orbit-temp.conf <<EOF
<VirtualHost *:80>
    ServerName orbittraining.online
    ServerAlias www.orbittraining.online
    DocumentRoot /var/www/html
</VirtualHost>
<VirtualHost *:80>
    ServerName crm.orbittraining.online
    DocumentRoot /var/www/html
</VirtualHost>
EOF
a2ensite orbit-temp.conf
a2dissite 000-default.conf 2>/dev/null || true
systemctl reload apache2

# Get SSL certificates
echo "  Getting SSL certificates (ensure DNS is pointing to this server)..."
certbot certonly --apache --non-interactive --agree-tos \
    --email admin@orbittraining.online \
    -d orbittraining.online -d www.orbittraining.online \
    && echo "  ERP SSL OK" || echo "  ERP SSL FAILED - run manually: certbot certonly --apache -d orbittraining.online -d www.orbittraining.online"

certbot certonly --apache --non-interactive --agree-tos \
    --email admin@orbittraining.online \
    -d crm.orbittraining.online \
    && echo "  CRM SSL OK" || echo "  CRM SSL FAILED - run manually: certbot certonly --apache -d crm.orbittraining.online"

# Enable production virtual hosts
a2dissite orbit-temp.conf
a2ensite orbittraining.online.conf crm.orbittraining.online.conf
systemctl reload apache2

# Fix permissions
chown -R www-data:www-data ${APP_DIR}
find ${APP_DIR} -type d -exec chmod 755 {} \;
find ${APP_DIR} -name "*.py" -exec chmod 644 {} \;
chmod 600 ${APP_DIR}/.env.erp ${APP_DIR}/.env.crm

echo ""
echo "================================================================"
echo "  DEPLOYMENT COMPLETE"
echo "================================================================"
echo "  ERP:  https://orbittraining.online"
echo "  CRM:  https://crm.orbittraining.online"
echo ""
echo "  DB user:     ${DB_USER}"
echo "  DB password: ${DB_PASS}  (save this!)"
echo ""
echo "  Logs:"
echo "    ERP: journalctl -u orbit-erp -f"
echo "    CRM: journalctl -u orbit-crm -f"
echo "================================================================"

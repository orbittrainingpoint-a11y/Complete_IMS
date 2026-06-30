import sys
import site

# Add the site-packages of the virtualenv
site.addsitedir('/var/www/html/leads-management/venv/lib/python3.11/site-packages')  # <-- adjust python version

# Add the app's directory to the PYTHONPATH
sys.path.insert(0, "/var/www/html/leads-management")

from app import app as application


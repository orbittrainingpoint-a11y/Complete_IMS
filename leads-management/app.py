import os
import logging
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import time
from extensions import db, login_manager, mail, migrate

logging.basicConfig(level=logging.DEBUG)

def create_app():
    app = Flask(__name__)
    
    app.secret_key = os.environ.get("SESSION_SECRET", "training-center-crm-secret-key-2024-secure-deployment")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # MySQL database configuration — set DB_URI env var in production
    _default_db = "mysql+pymysql://root:@localhost:3306/leads"
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DB_URI", _default_db)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    
    # Mail configuration
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)
    
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Please log in to access this page.'
    
    # Add custom template filter for JSON conversion
    @app.template_filter('tojsonfilter')
    def to_json_filter(obj):
        import json
        return json.dumps(obj, default=str)
    
    with app.app_context():
        # Import models and routes
        import models
        import routes

        # Register blueprints
        app.register_blueprint(routes.main)

        # Auto-create any new tables (additive only — never drops existing tables)
        # Wrapped in try/except: VPS root uses socket auth so TCP create_all fails gracefully;
        # create tables manually on the server when adding new models.
        try:
            db.create_all()
        except Exception:
            pass
    
    return app

app = create_app()

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

def format_time(value):
    """Format a time object or string to HH:MM"""
    if isinstance(value, time):
        return value.strftime('%H:%M')
    return value

app.jinja_env.filters['format_time'] = format_time
from app import create_app, db
from models import User
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            id=1,
            username='admin',
            email='admin@trainingcenter.com',
            password_hash=generate_password_hash('Fahad!Orbit!Admin', method='scrypt'),
            role='admin',
            active=True,
            can_view_all_leads=True,
            can_manage_users=True,
            can_view_reports=True,
            can_manage_courses=True,
            can_manage_settings=True
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Admin user created successfully")
    else:
        print("Admin user already exists")
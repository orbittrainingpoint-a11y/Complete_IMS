from werkzeug.security import generate_password_hash
print(generate_password_hash('SelomeS@123sales!Orbit!', method='scrypt'))
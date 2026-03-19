from flask import Flask, request, jsonify

app = Flask(__name__)
import logging
from flask import request

# Basic logging setup
logging.basicConfig(
    filename='D:/logs/api.log',  # Output log file
    level=logging.INFO,  # You can use DEBUG for even more details
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)

# Log every request
@app.after_request
def log_request(response):
    log_message = f"{request.remote_addr} - {request.method} {request.path} - {response.status_code}"
    app.logger.info(log_message)
    return response

# Mocked users database
users_db = {
    "admin": {"password": "admin123", "role": "admin", "email": "admin@example.com"},
    "user1": {"password": "password123", "role": "user", "email": "user1@example.com"}
}

# Route for user sign-up (POST /api/signup)
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json

    # Check if all required fields are present
    if 'username' not in data or 'password' not in data or 'email' not in data:
        return jsonify({"error": "Missing required fields: username, password, email"}), 400

    username = data['username']
    password = data['password']
    email = data['email']

    # Check if username already exists
    if username in users_db:
        return jsonify({"error": "Username already exists"}), 409

    # Simulate user registration by adding them to the "database"
    users_db[username] = {"password": password, "role": "user", "email": email}
    return jsonify({"message": "User created successfully!"}), 201

# Route for user login (POST /api/login)
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json

    # Check if required fields are present
    if 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing required fields: username, password"}), 400

    username = data['username']
    password = data['password']

    # Check if username exists
    if username not in users_db:
        return jsonify({"error": "Username not found"}), 404

    # Check if the password matches
    if users_db[username]["password"] != password:
        return jsonify({"error": "Incorrect password"}), 401

    return jsonify({"message": f"Welcome {username}!"}), 200

# Route for checking if user is admin (For Authorization - POST /api/admin)
@app.route('/api/admin', methods=['POST'])
def admin_check():
    data = request.json

    if 'username' not in data or 'password' not in data:
        return jsonify({"error": "Missing username or password"}), 400

    username = data['username']
    password = data['password']

    if username not in users_db or users_db[username]["password"] != password:
        return jsonify({"error": "Unauthorized"}), 401

    if users_db[username]["role"] != "admin":
        return jsonify({"error": "Forbidden: Admin access required"}), 403

    return jsonify({"message": "You have admin access!"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

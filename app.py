from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import threading
import time
import json
import os
import uuid
import logging

app = Flask(__name__)
CORS(app)

# -------------------- LOGGING --------------------
logging.basicConfig(level=logging.DEBUG)

@app.before_request
def log_request_info():
    app.logger.debug(f"Request: {request.method} {request.url}")
    app.logger.debug(f"Headers: {dict(request.headers)}")
    app.logger.debug(f"Body: {request.get_data()}")

# -------------------- DATA FILE --------------------
DATA_FILE = "onechat.adithf"

# -------------------- LOAD & SAVE --------------------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # Convert message time back to datetime
            for gnum in data.get("messages", {}):
                for m in data["messages"][gnum]:
                    m["time"] = datetime.fromisoformat(m["time"])
            return data
    return {
        "users": {
            "adith": {"password": "adith", "name": "adith", "groups": []},
            "ONE": {"password": "onechat", "name": "ONE", "groups": []}
        },
        "groups": {},
        "messages": {},
        "sessions": {}
    }

def save_data():
    with open(DATA_FILE, "w") as f:
        # Convert datetime to string
        data_copy = {
            "users": users,
            "groups": groups,
            "messages": {
                gnum: [
                    {"sender": m["sender"], "message": m["message"], "time": m["time"].isoformat()}
                    for m in msgs
                ]
                for gnum, msgs in messages.items()
            },
            "sessions": sessions
        }
        json.dump(data_copy, f, indent=4)

# Ensure file exists with secure permissions
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        f.write("{}")
    try:
        os.chmod(DATA_FILE, 0o600)
    except Exception as e:
        print("Warning: Could not set file permissions:", e)

# Load data at startup
data = load_data()
users = data.get("users", {})
groups = data.get("groups", {})
messages = data.get("messages", {})
sessions = data.get("sessions", {})

# Fast token lookup
def token_dict():
    return {v: k for k, v in sessions.items()}

# -------------------- AUTH HELPERS --------------------
def generate_token():
    return str(uuid.uuid4())

def authenticate(token):
    return token_dict().get(token)

# -------------------- ROOT --------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({"success": True, "message": "Server is running!"})

# -------------------- SIGNUP --------------------
@app.route("/signup", methods=["GET", "POST"])
def signup_route():
    if request.method == "GET":
        return jsonify({"success": False, "message": "Use POST to signup"}), 405

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    name = data.get("name", username)

    if username in users:
        return jsonify({"success": False, "message": "Username already exists!"}), 400

    users[username] = {"password": password, "name": name, "groups": []}
    save_data()
    return jsonify({"success": True, "message": "Signup successful!"})

# -------------------- LOGIN --------------------
@app.route("/login", methods=["GET", "POST"])
def login_route():
    if request.method == "GET":
        return jsonify({"success": False, "message": "Use POST to login"}), 405

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if username in users and users[username]["password"] == password:
        token = generate_token()
        sessions[username] = token
        save_data()
        return jsonify({"success": True, "message": "Login successful!", "token": token})
    else:
        return jsonify({"success": False, "message": "Invalid credentials!"}), 401

# -------------------- LOGOUT --------------------
@app.route("/logout", methods=["GET", "POST"])
def logout_route():
    if request.method == "GET":
        return jsonify({"success": False, "message": "Use POST to logout"}), 405

    data = request.get_json()
    token = data.get("token")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Invalid token!"}), 401

    sessions.pop(user, None)
    save_data()
    return jsonify({"success": True, "message": "Logout successful!"})

# -------------------- CREATE GROUP --------------------
@app.route("/create_group", methods=["GET", "POST"])
def create_group_route():
    if request.method == "GET":
        return jsonify({"success": False, "message": "Use POST to create group"}), 405

    data = request.get_json()
    token = data.get("token")
    group_name = data.get("groupName")
    group_number = data.get("groupNumber")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    if group_number in groups:
        return jsonify({"success": False, "message": "Group number already exists!"}), 400

    groups[group_number] = {"name": group_name, "members": [user]}
    users[user]["groups"].append(group_number)
    messages[group_number] = []
    save_data()
    return jsonify({"success": True, "message": f"Group '{group_name}' created successfully!"})

# -------------------- JOIN GROUP --------------------
@app.route("/join_group", methods=["GET", "POST"])
def join_group_route():
    if request.method == "GET":
        return jsonify({"success": False, "message": "Use POST to join group"}), 405

    data = request.get_json()
    token = data.get("token")
    group_number = data.get("groupNumber")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    if group_number not in groups:
        return jsonify({"success": False, "message": "Group not found!"}), 404

    if user not in groups[group_number]["members"]:
        groups[group_number]["members"].append(user)
        users[user]["groups"].append(group_number)
    save_data()
    return jsonify({"success": True, "message": f"Joined group '{groups[group_number]['name']}' successfully!"})

# -------------------- PROFILE --------------------
@app.route("/profile", methods=["POST"])
def profile_route():
    data = request.get_json()
    token = data.get("token")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    user_groups = [{"name": groups[g]["name"], "number": g} for g in users[user]["groups"] if g in groups]
    return jsonify({
        "success": True,
        "username": user,
        "name": users[user]["name"],
        "groups": user_groups
    })

# -------------------- UPDATE PROFILE --------------------
@app.route("/update_profile", methods=["POST"])
def update_profile_route():
    data = request.get_json()
    token = data.get("token")
    new_name = data.get("newName")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    users[user]["name"] = new_name
    save_data()
    return jsonify({"success": True, "message": "Profile updated successfully!"})

# -------------------- SEND MESSAGE --------------------
@app.route("/send_message", methods=["POST"])
def send_message_route():
    data = request.get_json()
    token = data.get("token")
    group_number = data.get("groupNumber")
    text = data.get("message")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    if group_number not in groups:
        return jsonify({"success": False, "message": "Group not found!"}), 404

    message = {"sender": user, "message": text, "time": datetime.utcnow()}
    messages[group_number].append(message)
    save_data()
    return jsonify({"success": True, "message": "Message sent!"})

# -------------------- GET MESSAGES --------------------
@app.route("/get_messages/<group_number>", methods=["POST"])
def get_messages_route(group_number):
    data = request.get_json()
    token = data.get("token")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    if group_number not in groups:
        return jsonify({"success": False, "message": "Group not found!"}), 404

    group_messages = messages.get(group_number, [])
    return jsonify({
        "success": True,
        "messages": [{"sender": m["sender"], "message": m["message"], "time": m["time"].isoformat()} for m in group_messages]
    })

# -------------------- MESSAGE CLEANUP --------------------
def cleanup_messages():
    while True:
        now = datetime.utcnow()
        for group_num, msgs in messages.items():
            messages[group_num] = [m for m in msgs if now - m["time"] < timedelta(hours=24)]
        save_data()
        time.sleep(3600)  # every hour

threading.Thread(target=cleanup_messages, daemon=True).start()

# -------------------- RUN SERVER --------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

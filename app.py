from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import threading
import time
import uuid
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB

# -------------------- APP & DB SETUP --------------------
app = Flask(__name__)
CORS(app)

# Replace the file-based configuration with the database URI
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'postgresql://onechat_user:g8s5VooJZXmjRfi9wJqpnd8GJGmj7JY7@dpg-d2p73iv5r7bs739bmcp0-a/onechat'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------- DATABASE MODELS --------------------
class User(db.Model):
    __tablename__ = 'users'
    username = db.Column(db.String(50), primary_key=True)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    groups = db.Column(JSONB, default=[])

class Group(db.Model):
    __tablename__ = 'groups'
    group_number = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    members = db.Column(JSONB, default=[])

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    group_number = db.Column(db.String(50), db.ForeignKey('groups.group_number'), nullable=False)
    sender = db.Column(db.String(50), db.ForeignKey('users.username'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Session(db.Model):
    __tablename__ = 'sessions'
    username = db.Column(db.String(50), primary_key=True, unique=True)
    token = db.Column(db.String(200), nullable=False)

# -------------------- AUTH HELPERS --------------------
def generate_token():
    return str(uuid.uuid4())

def authenticate(token):
    session = Session.query.filter_by(token=token).first()
    return session.username if session else None

# -------------------- DATABASE CREATION --------------------
with app.app_context():
    db.create_all()

# -------------------- ROOT --------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "success": True,
        "message": "🚀 OneChat API is running! Database connection active."
    })

# -------------------- SIGNUP --------------------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    name = data.get("name", username)

    if User.query.get(username):
        return jsonify({"success": False, "message": "Username already exists!"}), 400

    new_user = User(username=username, password=password, name=name, groups=[])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"success": True, "message": "Signup successful!"})

# -------------------- LOGIN --------------------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    user = User.query.get(username)
    if user and user.password == password:
        token = generate_token()
        session = Session.query.get(username)
        if session:
            session.token = token
        else:
            new_session = Session(username=username, token=token)
            db.session.add(new_session)
        db.session.commit()
        return jsonify({"success": True, "message": "Login successful!", "token": token})
    else:
        return jsonify({"success": False, "message": "Invalid credentials!"}), 401

# -------------------- LOGOUT --------------------
@app.route("/logout", methods=["POST"])
def logout():
    data = request.get_json()
    token = data.get("token")

    session = Session.query.filter_by(token=token).first()
    if not session:
        return jsonify({"success": False, "message": "Invalid token!"}), 401

    db.session.delete(session)
    db.session.commit()
    return jsonify({"success": True, "message": "Logout successful!"})

# -------------------- CREATE GROUP --------------------
@app.route("/create_group", methods=["POST"])
def create_group():
    data = request.get_json()
    token = data.get("token")
    group_name = data.get("groupName")
    group_number = data.get("groupNumber")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    if Group.query.get(group_number):
        return jsonify({"success": False, "message": "Group number already exists!"}), 400

    new_group = Group(group_number=group_number, name=group_name, members=[user])
    db.session.add(new_group)

    user_obj = User.query.get(user)
    if user_obj:
        user_obj.groups.append(group_number)

    db.session.commit()
    return jsonify({"success": True, "message": f"Group '{group_name}' created successfully!"})

# -------------------- JOIN GROUP --------------------
@app.route("/join_group", methods=["POST"])
def join_group():
    data = request.get_json()
    token = data.get("token")
    group_number = data.get("groupNumber")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    group = Group.query.get(group_number)
    if not group:
        return jsonify({"success": False, "message": "Group not found!"}), 404

    if user not in group.members:
        group.members.append(user)
        user_obj = User.query.get(user)
        if user_obj:
            user_obj.groups.append(group_number)
    
    db.session.commit()
    return jsonify({"success": True, "message": f"Joined group '{group.name}' successfully!"})

# -------------------- GET PROFILE --------------------
@app.route("/profile", methods=["POST"])
def get_profile():
    data = request.get_json()
    token = data.get("token")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    user_obj = User.query.get(user)
    user_groups = []
    if user_obj:
        for gnum in user_obj.groups:
            grp = Group.query.get(gnum)
            if grp:
                user_groups.append({"name": grp.name, "number": gnum})

    return jsonify({
        "success": True,
        "username": user,
        "name": user_obj.name,
        "groups": user_groups
    })

# -------------------- UPDATE PROFILE --------------------
@app.route("/update_profile", methods=["POST"])
def update_profile():
    data = request.get_json()
    token = data.get("token")
    new_name = data.get("newName")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    user_obj = User.query.get(user)
    if user_obj:
        user_obj.name = new_name
        db.session.commit()

    return jsonify({"success": True, "message": "Profile updated successfully!"})

# -------------------- SEND MESSAGE --------------------
@app.route("/send_message", methods=["POST"])
def send_message():
    data = request.get_json()
    token = data.get("token")
    group_number = data.get("groupNumber")
    text = data.get("message")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    if not Group.query.get(group_number):
        return jsonify({"success": False, "message": "Group not found!"}), 404

    new_message = Message(
        sender=user,
        message=text,
        group_number=group_number,
        time=datetime.utcnow()
    )
    db.session.add(new_message)
    db.session.commit()
    return jsonify({"success": True, "message": "Message sent!"})

# -------------------- GET MESSAGES --------------------
@app.route("/get_messages/<group_number>", methods=["POST"])
def get_messages(group_number):
    data = request.get_json()
    token = data.get("token")

    user = authenticate(token)
    if not user:
        return jsonify({"success": False, "message": "Unauthorized!"}), 401

    group_messages = Message.query.filter_by(group_number=group_number).order_by(Message.time.asc()).all()
    
    return jsonify({
        "success": True,
        "messages": [
            {"sender": m.sender, "message": m.message, "time": m.time.isoformat()}
            for m in group_messages
        ]
    })

# -------------------- MESSAGE CLEANUP --------------------
def cleanup_messages():
    with app.app_context():
        while True:
            now = datetime.utcnow()
            twenty_four_hours_ago = now - timedelta(hours=24)
            Message.query.filter(Message.time < twenty_four_hours_ago).delete(synchronize_session='fetch')
            db.session.commit()
            time.sleep(3600)  # Run cleanup every hour

threading.Thread(target=cleanup_messages, daemon=True).start()

# -------------------- RUN SERVER --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

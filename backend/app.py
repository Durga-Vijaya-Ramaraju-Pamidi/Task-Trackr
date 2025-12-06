# app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from datetime import datetime, timedelta
import os
from io import StringIO
import csv

app = Flask(__name__, static_folder="../frontend")
CORS(app)

# === Database Config ===
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "tasktracker.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ============================
# MODELS
# ============================

class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Task(db.Model):
    __tablename__ = "task"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="todo")
    due_date = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Creator and assignee are stored as usernames for simplicity
    username = db.Column(db.String(80), nullable=False)    # who created the task
    assigned_to = db.Column(db.String(80), nullable=True)  # who it is assigned to

class Log(db.Model):
    __tablename__ = "log"
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(80))
    action = db.Column(db.String(100))
    task_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text, nullable=True)

class Message(db.Model):
    __tablename__ = "message"
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(80))
    recipient = db.Column(db.String(80))
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

# ============================
# UTILITIES
# ============================
def log_action(user, action, task_id=None, details=None):
    entry = Log(user=user, action=action, task_id=task_id, details=details)
    db.session.add(entry)
    db.session.commit()

def is_admin_user(username):
    if not username:
        return False
    u = User.query.filter_by(username=username).first()
    return bool(u and u.is_admin)

# ============================
# AUTH
# ============================
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    is_admin = bool(data.get("is_admin", False))

    if not username or not password:
        return jsonify({"message": "username and password required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "username already exists"}), 400

    user = User(username=username, password_hash=generate_password_hash(password), is_admin=is_admin)
    db.session.add(user)
    db.session.commit()
    log_action(username, "REGISTER", details="registered (admin)" if is_admin else "registered")
    return jsonify({"message": "registered"}), 201

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"message": "username and password required"}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"message": "invalid credentials"}), 401

    log_action(username, "LOGIN", details="admin" if user.is_admin else "user")
    return jsonify({"message": "login successful", "is_admin": user.is_admin}), 200

# ============================
# USER LIST (for selects)
# ============================
@app.route("/api/users", methods=["GET"])
def list_users():
    users = User.query.order_by(User.username).all()
    data = [{"username": u.username, "is_admin": u.is_admin} for u in users]
    return jsonify({"data": data})

# ============================
# TASKS (user & admin)
# ============================
@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    username = request.args.get("username")
    if not username:
        return jsonify({"message": "username required"}), 400

    tasks = Task.query.filter((Task.username == username) | (Task.assigned_to == username)).order_by(Task.created_at.desc()).all()
    data = [{
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "due_date": t.due_date,
        "username": t.username,
        "assigned_to": t.assigned_to
    } for t in tasks]
    return jsonify({"data": data})

@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json() or {}
    title = data.get("title")
    username = data.get("username")
    if not title or not username:
        return jsonify({"message": "title and username required"}), 400

    new_task = Task(title=title, description=data.get("description", ""), due_date=data.get("due_date"), status=data.get("status","todo"), username=username, assigned_to=data.get("assigned_to"))
    db.session.add(new_task)
    db.session.commit()
    log_action(username, "CREATE_TASK", new_task.id, f"Created task '{title}' assigned_to={new_task.assigned_to}")
    return jsonify({"status":"success", "id": new_task.id}), 201

@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json() or {}

    # update fields if present
    task.title = data.get("title", task.title)
    task.description = data.get("description", task.description)
    task.status = data.get("status", task.status)
    task.due_date = data.get("due_date", task.due_date)
    task.assigned_to = data.get("assigned_to", task.assigned_to)
    db.session.commit()
    log_action(task.username, "UPDATE_TASK", task_id, f"Updated: status={task.status} assigned_to={task.assigned_to}")
    return jsonify({"status":"success"})

@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    log_action(task.username, "DELETE_TASK", task_id, f"Deleted task '{task.title}'")
    return jsonify({"status":"success"})

# ADMIN create & assign endpoint (explicit)
@app.route("/api/admin/tasks", methods=["POST"])
def admin_create_task():
    data = request.get_json() or {}
    admin = data.get("admin")
    if not is_admin_user(admin):
        return jsonify({"message":"admin privileges required"}), 403

    title = data.get("title")
    assigned_to = data.get("assigned_to")
    due_date = data.get("due_date")
    if not title:
        return jsonify({"message":"title required"}), 400

    # verify assignee exists if provided
    if assigned_to and not User.query.filter_by(username=assigned_to).first():
        return jsonify({"message":"assignee not found"}), 400

    new_task = Task(title=title, due_date=due_date, status="todo", username=admin, assigned_to=assigned_to)
    db.session.add(new_task)
    db.session.commit()
    log_action(admin, "ADMIN_CREATE_TASK", new_task.id, f"Assigned to {assigned_to}" if assigned_to else "Unassigned")
    return jsonify({"status":"success", "id": new_task.id}), 201

# ============================
# MESSAGES
# ============================
@app.route("/api/messages/send", methods=["POST"])
def send_message():
    data = request.get_json() or {}
    sender = data.get("sender")
    recipient = data.get("recipient")
    subject = data.get("subject", "")
    body = data.get("body", "")

    if not sender or not recipient or not body:
        return jsonify({"message":"sender, recipient and body required"}), 400

    # ensure recipient exists
    if not User.query.filter_by(username=recipient).first():
        return jsonify({"message":"recipient not found"}), 400

    msg = Message(sender=sender, recipient=recipient, subject=subject, body=body)
    db.session.add(msg)
    db.session.commit()
    log_action(sender, "SEND_MESSAGE", None, f"to {recipient} subj='{subject[:50]}'")
    return jsonify({"status":"sent", "id": msg.id}), 201

@app.route("/api/messages", methods=["GET"])
def get_messages():
    username = request.args.get("username")
    only_unread = request.args.get("unread") == "1"
    if not username:
        return jsonify({"message":"username required"}), 400

    q = Message.query.filter_by(recipient=username)
    if only_unread:
        q = q.filter_by(read=False)
    msgs = q.order_by(Message.timestamp.desc()).all()
    data = [{"id": m.id, "sender": m.sender, "subject": m.subject, "body": m.body, "timestamp": m.timestamp.strftime("%Y-%m-%d %H:%M"), "read": m.read} for m in msgs]
    return jsonify({"messages": data})

@app.route("/api/messages/<int:msg_id>/read", methods=["PUT"])
def mark_message_read(msg_id):
    msg = Message.query.get_or_404(msg_id)
    msg.read = True
    db.session.commit()
    return jsonify({"status":"success"})

# ============================
# ADMIN LOGS & EXPORT
# ============================
@app.route("/api/admin/logs", methods=["GET"])
def view_logs():
    user = request.args.get("user")
    action = request.args.get("action")
    task_id = request.args.get("task_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = Log.query
    if user:
        query = query.filter(Log.user.ilike(f"%{user}%"))
    if action:
        query = query.filter(Log.action.ilike(f"%{action}%"))
    if task_id:
        try:
            query = query.filter(Log.task_id == int(task_id))
        except:
            pass
    if start_date:
        try:
            sdt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Log.timestamp >= sdt)
        except:
            pass
    if end_date:
        try:
            edt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Log.timestamp < edt)
        except:
            pass

    logs = query.order_by(Log.timestamp.desc()).all()
    data = [{"id": l.id, "user": l.user, "action": l.action, "task_id": l.task_id, "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S"), "details": l.details} for l in logs]
    return jsonify({"data": data})

@app.route("/api/admin/logs/export", methods=["GET"])
def export_logs():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["id","user","action","task_id","timestamp","details"])
    for l in Log.query.order_by(Log.timestamp.desc()).all():
        writer.writerow([l.id, l.user, l.action, l.task_id, l.timestamp, l.details])
    output.seek(0)
    return app.response_class(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=logs.csv"})
# --- Add this to your app.py (near other message routes) ---
from flask import jsonify, request
from datetime import datetime

@app.route("/api/messages/sent", methods=["GET"])
def get_sent_messages():
    username = request.args.get("username")
    if not username:
        return jsonify({"message": "username required"}), 400

    msgs = Message.query.filter_by(sender=username).order_by(Message.timestamp.desc()).all()
    data = [{
        "id": m.id,
        "recipient": m.recipient,
        "subject": m.subject,
        "body": m.body,
        "timestamp": m.timestamp.strftime("%Y-%m-%d %H:%M"),
    } for m in msgs]

    return jsonify({"messages": data})

@app.route("/api/messages/unread_count", methods=["GET"])
def get_unread_count():
    username = request.args.get("username")
    if not username:
        return jsonify({"message": "username required"}), 400

    count = Message.query.filter_by(recipient=username, read=False).count()

    return jsonify({"unread": count})

# ============================
# SERVE FRONTEND
# ============================
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path == "" or path == "index.html":
        return send_from_directory(app.static_folder, "index.html")
    if path == "auth.html":
        return send_from_directory(app.static_folder, "auth.html")
    if path == "admin_dashboard.html":
        return send_from_directory(app.static_folder, "admin_dashboard.html")
    if path == "admin_logs.html":
        return send_from_directory(app.static_folder, "admin_logs.html")
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__":
    app.run(debug=True)

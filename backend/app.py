from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from datetime import datetime
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
from flask_migrate import Migrate
migrate = Migrate(app, db)

# === Models ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # 👈 added admin flag


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    status = db.Column(db.String(20), default="todo")
    due_date = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    username = db.Column(db.String(80), nullable=False)


class Log(db.Model):
    __tablename__ = "log"
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(80))
    action = db.Column(db.String(100))
    task_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text, nullable=True)


with app.app_context():
    db.create_all()


# === Utility: Action Logger ===
def log_action(user, action, task_id=None, details=None):
    entry = Log(user=user, action=action, task_id=task_id, details=details)
    db.session.add(entry)
    db.session.commit()


# === Auth Routes ===
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    is_admin = data.get("is_admin", False)

    if not username or not password:
        return jsonify({"message": "Missing username or password"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username already exists"}), 400

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        is_admin=is_admin
    )
    db.session.add(user)
    db.session.commit()
    log_action(username, "REGISTER", details="User registered (admin)" if is_admin else "User registered")
    return jsonify({"message": "User registered successfully"}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"message": "Invalid credentials"}), 401
    log_action(username, "LOGIN", details="Admin logged in" if user.is_admin else "User logged in")
    return jsonify({"message": "Login successful", "is_admin": user.is_admin}), 200


# === Task Routes === (same as before)
@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    username = request.args.get("username")
    if not username:
        return jsonify({"message": "Username required"}), 400
    tasks = Task.query.filter_by(username=username).order_by(Task.created_at.desc()).all()
    return jsonify({
        "status": "success",
        "data": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "due_date": t.due_date,
                "username": t.username
            }
            for t in tasks
        ]
    })


@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json()
    title = data.get("title")
    username = data.get("username")
    if not title or not username:
        return jsonify({"message": "Title and username required"}), 400

    new_task = Task(
        title=title,
        due_date=data.get("due_date"),
        status=data.get("status", "todo"),
        username=username
    )
    db.session.add(new_task)
    db.session.commit()
    log_action(username, "CREATE_TASK", new_task.id, f"Created task '{title}'")
    return jsonify({"status": "success", "data": {"id": new_task.id}}), 201


@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.get_json()
    old_status = task.status
    task.title = data.get("title", task.title)
    task.due_date = data.get("due_date", task.due_date)
    task.status = data.get("status", task.status)
    db.session.commit()
    log_action(task.username, "UPDATE_TASK", task.id, f"Updated task {task_id} (from {old_status} to {task.status})")
    return jsonify({"status": "success"})


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    log_action(task.username, "DELETE_TASK", task.id, f"Deleted task '{task.title}'")
    return jsonify({"status": "success"})


# === Admin Log Viewer Routes === (unchanged)
from datetime import datetime, timedelta
from flask import jsonify, request

@app.route("/api/admin/logs", methods=["GET"])
def view_logs():
    user = request.args.get("user")
    action = request.args.get("action")
    task_id = request.args.get("task_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    query = Log.query

    # Filter by username
    if user:
        query = query.filter(Log.user.ilike(f"%{user}%"))

    # Filter by action
    if action:
        query = query.filter(Log.action.ilike(f"%{action}%"))

    # ✅ Fix: Filter by Task ID (convert string to int if possible)
    if task_id:
        try:
            query = query.filter(Log.task_id == int(task_id))
        except ValueError:
            pass  # Ignore invalid input

    # ✅ Date range filter with proper datetime conversion
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Log.timestamp >= start_dt)
        except:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(Log.timestamp < end_dt)
        except:
            pass

    # Sort newest first
    logs = query.order_by(Log.id.desc()).all()

    data = [
        {
            "id": l.id,
            "user": l.user,
            "action": l.action,
            "task_id": l.task_id,
            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "details": l.details,
        }
        for l in logs
    ]
    return jsonify({"data": data})


@app.route("/api/admin/logs/export", methods=["GET"])
def export_logs():
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user", "action", "task_id", "timestamp", "details"])
    for l in Log.query.order_by(Log.timestamp.desc()).all():
        writer.writerow([l.id, l.user, l.action, l.task_id, l.timestamp, l.details])
    output.seek(0)
    return app.response_class(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=logs.csv"}
    )


# === Serve Frontend Files ===
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    if path == "" or path == "index.html":
        return send_from_directory(app.static_folder, "index.html")
    elif path == "auth.html":
        return send_from_directory(app.static_folder, "auth.html")
    elif path == "admin_logs.html":
        return send_from_directory(app.static_folder, "admin_logs.html")
    elif os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    app.run(debug=True)

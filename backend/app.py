from flask import Flask, request, jsonify
from flask_cors import CORS
from config import Config
from models import db, User, Task
from werkzeug.security import generate_password_hash, check_password_hash

def create_app():
    app = Flask(__name__, static_folder="../frontend", static_url_path="/")
    app.config.from_object(Config)
    CORS(app)  # allow frontend fetch from same machine

    db.init_app(app)
    with app.app_context():
        db.create_all()

    # ----- Auth endpoints (simple) -----
    @app.route("/api/register", methods=["POST"])
    def register():
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        if not username or not password:
            return jsonify({"status":"error","message":"username and password required"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"status":"error","message":"username exists"}), 400

        pw_hash = generate_password_hash(password)
        user = User(username=username, password_hash=pw_hash)
        db.session.add(user)
        db.session.commit()
        return jsonify({"status":"success","message":"registered"}), 201

    @app.route("/api/login", methods=["POST"])
    def login():
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({"status":"error","message":"invalid credentials"}), 401
        # For Week2 we return a simple success; in Week3 we'll add JWT/session
        return jsonify({"status":"success","message":"logged_in", "user_id": user.id}), 200

    # ----- Task CRUD -----
    @app.route("/api/tasks", methods=["GET"])
    def list_tasks():
        tasks = Task.query.order_by(Task.created_at.desc()).all()
        out = []
        for t in tasks:
            out.append({
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "due_date": t.due_date,
                "created_at": t.created_at.isoformat(),
                "user_id": t.user_id
            })
        return jsonify({"status":"success","data": out})

    @app.route("/api/tasks", methods=["POST"])
    def create_task():
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        if not title:
            return jsonify({"status":"error","message":"title required"}), 400
        description = data.get("description", "")
        status = data.get("status", "todo")
        due_date = data.get("due_date", None)
        task = Task(title=title, description=description, status=status, due_date=due_date)
        db.session.add(task)
        db.session.commit()
        return jsonify({"status":"success","data":{
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "due_date": task.due_date
        }}), 201

    @app.route("/api/tasks/<int:task_id>", methods=["PUT"])
    def update_task(task_id):
        task = Task.query.get_or_404(task_id)
        data = request.get_json() or {}
        task.title = data.get("title", task.title)
        task.description = data.get("description", task.description)
        task.status = data.get("status", task.status)
        task.due_date = data.get("due_date", task.due_date)
        db.session.commit()
        return jsonify({"status":"success","data":{
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "due_date": task.due_date
        }})

    @app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
    def delete_task(task_id):
        task = Task.query.get_or_404(task_id)
        db.session.delete(task)
        db.session.commit()
        return jsonify({"status":"success","message":"deleted"})

    # Serve frontend files (index and auth)
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def static_proxy(path):
        # if empty path or index.html requested, serve index.html
        if path == "" or path == "index.html":
            return app.send_static_file("index.html")
        if path == "auth.html":
            return app.send_static_file("auth.html")
        # fallback to index
        return app.send_static_file("index.html")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

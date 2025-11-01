# TaskTracker

Simple TaskTracker demo (Flask backend + static frontend). 
Worked on the Features:
- Dashboard layout with To Do / In Progress / Done columns
- Drag-and-drop task movement
- Add / Edit / Delete tasks
- Due date UI and "hide completed"
- Basic Flask API CRUD endpoints
- Simple register/login (passwords hashed)

## Run locally

1. Create a Python virtualenv and install:
```bash
python -m venv venv
source venv/bin/activate 
pip install -r backend/requirements.txt
```
2. Start the backend from project root:

```bash
cd backend
python app.py
```
3. Open the frontend:

Visit http://127.0.0.1:5000/ for the board

Visit http://127.0.0.1:5000/auth.html for login/register


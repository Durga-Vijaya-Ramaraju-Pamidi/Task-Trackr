# Use Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /backend

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy frontend static files into backend/static
COPY frontend/ ./static/

# Expose Flask port
EXPOSE 5000

# Run Flask app
CMD ["python", "app.py"]



# Use official Python image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage caching
COPY backend/requirements.txt ./backend/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy entire project
COPY . .

# Expose port Railway provides (usually via $PORT)
ENV PORT 5000
EXPOSE 5000

# Set environment variable for Flask (optional, but good)
ENV FLASK_APP=backend/app.py
ENV FLASK_ENV=production

# Default command
CMD ["flask", "run", "--host=0.0.0.0", "--port", "5000"]

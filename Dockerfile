# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    gettext \
    libcurl4 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Compile translation files for multi-language support
RUN python manage.py compilemessages

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run the application with Daphne (ASGI server for WebSocket support)
CMD ["sh", "-c", "python manage.py migrate && (python manage.py createsuperuser_env || true) && daphne -b 0.0.0.0 -p ${PORT:-8000} smallcase_project.asgi:application"]

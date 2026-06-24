# Stock Basket Manager

A Django-based web application for creating and managing stock baskets with equal-weighted allocation, portfolio tracking, AI-assisted support, and user authentication.

![Stock Basket Manager Preview](https://github.com/Ishwar786Ambare/smallcase_project/blob/main/image.jpeg)

## Project Overview

This project helps users:

- Create and manage stock baskets
- Add or remove stocks from baskets
- Track total investment, current value, and profit/loss
- Review basket details and portfolio performance
- Use AI chat support for assistance
- Sign in with Django authentication and allauth
- Import/export basket data and manage multilingual content

## Main Features

- Basket creation and portfolio tracking
- Stock data integration
- Admin import/export support
- AI chat and support features
- HTMX-based interactive UI
- Multi-language support
- Production-ready Django settings with environment variables

## Tech Stack

- Python 3.12+
- Django 6.0
- Django Channels
- Jinja2
- Bootstrap / HTMX
- PostgreSQL (production) and SQLite (development)
- Whitenoise, Gunicorn, and Railway deployment support

## Project Structure

```text
smallcase_project/
├── manage.py
├── requirements.txt
├── smallcase_project/      # Django project settings and URLs
├── stocks/                 # Main app: baskets, stock logic, templates, views
├── user/                   # Authentication and user-related features
├── locale/                 # Translation files
├── docs/                   # Setup and deployment guides
└── staticfiles/            # Collected static files for production
```

## Prerequisites

Before starting, make sure you have:

- Python 3.12 installed
- Git installed
- A terminal or PowerShell
- Optional: PostgreSQL for production deployment

## Initial Setup From Scratch

### 1. Clone the repository

```bash
git clone <repo-url>
cd smallcase_project
```

### 2. Create a virtual environment

On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 3. Install requirements

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root with values such as:

```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

If you do not want to set them manually, the project already provides default values for local development.

## Run the Project

### 1. Apply database migrations

```bash
python manage.py migrate
```

### 2. Create an admin user

```bash
python manage.py createsuperuser
```

### 3. Start the development server

```bash
python manage.py runserver
```

Open your browser at:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/admin/

## Useful Commands

```bash
# Run tests
python manage.py test

# Collect static files for production
python manage.py collectstatic

# Start shell
python manage.py shell
```

## Deployment

This project is prepared for deployment on Railway and similar platforms.

### Railway Quick Links

- [Quick Start Guide](docs/RAILWAY_PRODUCTION_QUICK_START.md)
- [Deployment Checklist](docs/RAILWAY_CHECKLIST.md)
- [Detailed Deployment Guide](docs/RAILWAY_DEPLOYMENT.md)

### Production Notes

- Uses environment-aware settings
- Supports SQLite locally and PostgreSQL in production
- Static files are handled by Whitenoise
- Debug can be turned off safely in production

## Documentation

A set of detailed guides is available in the [docs](docs) folder:

- [docs/README.md](docs/README.md)
- [docs/EMAIL_USERNAME_LOGIN.md](docs/EMAIL_USERNAME_LOGIN.md)
- [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md)
- [docs/MULTI_LANGUAGE_GUIDE.md](docs/MULTI_LANGUAGE_GUIDE.md)
- [docs/IMPORT_EXPORT_README.md](docs/IMPORT_EXPORT_README.md)

## License

MIT
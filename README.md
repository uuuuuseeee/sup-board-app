# sup-board-app

Flask-based SUP (Stand-Up Paddleboard) board management application.

## Application Structure

The application follows a modular Flask application factory pattern:

```
sup-board-app/
├── app/                    # Main application package
│   ├── __init__.py        # Application factory and CLI commands
│   ├── config.py          # Configuration classes
│   ├── extensions.py      # Flask extensions (db, login_manager)
│   ├── models.py          # SQLAlchemy database models
│   ├── utils.py           # Utility functions and helpers
│   ├── decorators.py      # Custom decorators (admin_required, member_required)
│   ├── main.py            # Main blueprint (index, dashboard)
│   ├── auth.py            # Authentication blueprint (login, register, logout, profile)
│   ├── boards.py          # Board management blueprint
│   ├── practices.py       # Practice management blueprint
│   └── admin.py           # Admin panel blueprint
├── templates/             # Jinja2 templates
├── static/                # Static files (CSS, JS, images)
├── wsgi.py               # WSGI entry point for production
├── requirements.txt       # Python dependencies
└── app.py.bak            # Original monolithic app (backup)
```

## Running the Application

### Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
flask --app wsgi run

# Or with debug mode
FLASK_DEBUG=1 flask --app wsgi run
```

### Production

```bash
# Using gunicorn (recommended)
gunicorn -w 4 wsgi:app
```

## Environment Variables

- `SECRET_KEY`: Flask secret key for sessions (required for production)
- `DATABASE_URL`: PostgreSQL database URL (optional, defaults to SQLite)
- `FLASK_DEBUG`: Set to "1" to enable debug mode

## CLI Commands

### Promote User to Admin

```bash
flask --app wsgi promote-admin <username>
```

## Features

- **User Authentication**: Login, registration, guest access
- **Board Management**: Track SUP boards with location, serial numbers, and history
- **Practice Scheduling**: Create and manage team practice sessions
- **Attendance Tracking**: Members can respond to practice invitations
- **Transport Planning**: Assign board transportation with lottery system
- **Admin Panel**: User management, team management, announcements

## Database Models

- **User**: User accounts with roles (admin, member, guest)
- **Team**: User teams/groups
- **Board**: SUP board inventory
- **Practice**: Practice session scheduling
- **PracticeSession**: Multiple sessions per practice
- **Attendance**: User attendance responses
- **Transport**: Board transportation assignments
- **Announcement**: Admin announcements
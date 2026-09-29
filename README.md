# Hospital Management System

A web-based Hospital Management System created as a BCA minor project foundation.

## Purpose

The application serves as a foundational healthcare administration platform to manage hospital records cleanly and reliably. It provides the initial architectural framework, SQLite database schema, user session handling, and administrative user interface for demonstration and future module expansion.

## Technology Stack

- Language: Python 3.12
- Web Framework: Flask 3.1
- Database: SQLite 3 (Python built-in sqlite3)
- Templating Engine: Jinja2
- Frontend: Vanilla HTML5 and CSS3 (no external CSS/JS frameworks)

## Current Implemented Scope

### Phase 1: Foundation Setup
- Flask application initialization and configuration
- SQLite database connection management using the Flask application context
- Automated database schema initialization for all core entities:
  - patients
  - doctors
  - appointments
  - bills
- Session-based administrative authentication (login and logout)
- Isolated development credential verification
- Protected dashboard route with summary metric queries
- Administration dashboard interface with status cards and layout preview
- Responsive healthcare-themed CSS styling system with custom properties

### Phase 2: Patients Module
- Full patient CRUD functionality with parameterized SQL queries:
  - Patient directory listing with explicit column projections
  - Search by patient name and contact phone number
  - New patient registration with server-side validation and sanitized input
  - Patient details modification with pre-populated form fields
  - Safe patient record deletion via POST requests with UI confirmation
  - Clear empty states for both zero records and non-matching searches
- Integrated sidebar navigation highlighting the active Patients section

### Phase 3: Doctors Module
- Full doctor CRUD functionality with parameterized SQL queries:
  - Medical specialist directory listing with explicit column projections
  - Multi-field search across doctor name, specialization, and contact phone
  - Doctor registration with validated input for name, specialization, and phone number
  - Doctor details editing with pre-filled form fields and explicit record lookups
  - Safe doctor deletion via POST requests with dedicated confirmation screen
  - Polished empty states for zero-record database and unmatched search filters
### Phase 4: Appointments Module
- Full appointment CRUD functionality with parameterized SQL queries:
  - Appointment listing with explicit column projections and patient/doctor SQL JOIN
  - Multi-field search across patient name, doctor name, appointment date, and status
  - Book appointment workflow with dynamic dropdowns populated from registered patients and doctors
  - Appointment editing with pre-filled form fields and explicit record lookups
  - Safe appointment deletion via POST requests with dedicated confirmation screen
  - Polished empty states for zero-record database and unmatched search filters
  - Integrated sidebar navigation with active route highlights and removal of the Setup badge

### Phase 5: Billing Module
- Final functional module of the Hospital Management System:
  - Billing directory listing with explicit column projections and patient SQL JOIN
  - Multi-field search across patient name and bill date
  - Bill generation workflow with registered patient dropdown and fee inputs for consultation, medicine, and other charges
  - Strict server-side total amount calculation and server-side bill date generation
  - Printable bill detail view with official invoice layout, fee breakdown, and browser print styling
  - Safe bill deletion via POST requests with dedicated confirmation screen
  - Print-specific CSS hiding sidebar and controls during printing while preserving screen layout
  - Dashboard integration updating the Total Bills counter dynamically
- Complete activation of all sidebar navigation items with zero remaining placeholder badges

## Setup Instructions

### 1. Prerequisites

- Python 3.10+ (Python 3.12 recommended)
- Git (optional)

### 2. Create Virtual Environment

From the project root directory, run:

```bash
python -m venv .venv
```

Activate the virtual environment:

On Windows (Command Prompt):
```cmd
.venv\Scripts\activate.bat
```

On Windows (PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS / Linux:
```bash
source .venv/bin/activate
```

### 3. Install Dependencies

Install the required packages using pip:

```bash
pip install -r requirements.txt
```

### 4. Run the Application

Execute the Flask application:

```bash
python app.py
```

Or using the Flask CLI:

```bash
flask run
```

The application will start locally at `http://127.0.0.1:5000/`.

### 5. Development Credentials

Use the preconfigured development administrator credentials to log in:

- Username: `admin`
- Password: `admin123`

## Deployment (Render Web Service)

This application is ready for deployment as a **Python Web Service** on [Render](https://render.com/).

### Deployment Settings

- **Service Type**: Web Service
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`

### Required Environment Variables

Configure these variables in the Render Dashboard (**Dashboard > Your Service > Environment**):

| Variable | Description | Production Guidance |
| --- | --- | --- |
| `SECRET_KEY` | Secret key used to cryptographically sign session cookies | **Required**: Set a strong, randomly generated string. Render auto-generates this if using Blueprint (`render.yaml`). |
| `ADMIN_USERNAME` | Production administrator login username | **Required**: Set a secure production administrative username. |
| `ADMIN_PASSWORD` | Production administrator login password | **Required**: Set a strong production password. |
| `PYTHON_VERSION` | Explicit Python version | Optional (recommended `3.12.10`). |
| `DATABASE_PATH` | Path to the SQLite database file | Optional (defaults to `hospital.db` in application root). |

### SQLite Persistence Limitation on Render Free

> **Important**: The application uses a local SQLite database (`hospital.db`). Render's Free tier uses an **ephemeral filesystem**. When the service restarts, spins down after inactivity, or redeploys, modifications to the SQLite database will be reset to the version in the deployment build.
> Database tables are created automatically on startup (`CREATE TABLE IF NOT EXISTS`). Local development retains full persistence with the local `hospital.db` file.

### Manual Deploy Steps on Render

1. Log in to [Render](https://dashboard.render.com/).
2. Click **New +** and select **Web Service**.
3. Connect your GitHub repository (`hms-project`).
4. Select **Python 3** as the runtime.
5. Set the **Build Command** to:
   ```bash
   pip install -r requirements.txt
   ```
6. Set the **Start Command** to:
   ```bash
   gunicorn app:app
   ```
7. Under **Environment Variables**, add:
   - `SECRET_KEY` (or let Render generate one)
   - `ADMIN_USERNAME`
   - `ADMIN_PASSWORD`
8. Click **Create Web Service**.

Alternatively, deploy via **Blueprints** using the included `render.yaml` configuration.

# LimeCare – Digitizing Patient Records for Faster and Organized Healthcare

Django (templates) + PostgreSQL/Supabase clinic management system.

- **Project Development 1 (standard features):** registration, login/logout, role-based dashboards, profile view and edit.
- **Project Development 2 (core feature):** appointment scheduling, built as a full vertical slice (models and migrations, forms, views, URL routes and templates). It builds on patient registration (`/patients/`).

## Core Feature: Appointment Scheduling (F-06)

Registration Staff and Admins book patients into a doctor's time slot. Doctors see their own schedule.

| Operation | How it works | URL |
|-----------|--------------|-----|
| Create | Book an appointment: patient, department, doctor, date and time, reason | `/appointments/new/` |
| Read | Appointment list with search by patient name or number, status filter, date filter and pagination; detail page | `/appointments/`, `/appointments/<id>/` |
| Update | Reschedule a Scheduled appointment; mark it Completed, Cancelled or No-show | `/appointments/<id>/reschedule/`, `/appointments/<id>/status/` |
| Delete | Cancel (soft delete). Records are never removed, so history stays accurate | `/appointments/<id>/status/` |

### Business rules enforced

| Rule | Description |
|------|-------------|
| BR-13 | Patients are deactivated, not deleted. Inactive patients cannot be booked. |
| BR-14 | The appointment must be scheduled for a future date and time. |
| BR-15 | The selected doctor must belong to the selected department. |
| BR-16 | A doctor cannot have two Scheduled appointments at the same date and time (form check plus a database constraint). |
| BR-17 | A patient can have at most one Scheduled appointment with the same doctor on the same day. |
| BR-18 | Status can only change from Scheduled to Completed, Cancelled or No-show, and never back to Scheduled. |

Every appointment stores the user who booked it (`created_by`, a ForeignKey to User). Appointments, patients, doctors and departments are linked by ForeignKeys that follow the SDD's ERD.

### Role access

| Role | Appointments |
|------|--------------|
| Admin | View all; book, reschedule and change the status of any appointment |
| Registration Staff | View all; book; reschedule or change the status of appointments they booked |
| Doctor | View only their own appointments (read-only) |
| Nurse | No access |

Appointment summaries (today, upcoming) appear on the Admin, Doctor and Registration dashboards. Logged-out users are redirected to `/login/`; roles without permission get a 403.

## Roles and Dashboards

| Role | Dashboard | URL |
|------|-----------|-----|
| Admin | User statistics, patient and appointment summary | `/dashboard/admin/` |
| Doctor, Nurse, Registration Staff | Staff home (Doctor and Registration also see appointment summaries) | `/dashboard/staff/` |

After login, each user is sent to the dashboard for their role. Other pages: `/register/`, `/login/`, `/logout/`, `/profile/`, `/profile/edit/`, `/patients/`, `/appointments/`, `/admin/` (Django admin).

## Setup
1. `python -m venv venv` then activate it (`venv\Scripts\activate` on Windows).
2. `pip install -r requirements.txt`
3. Create a Supabase project, then copy **Project Settings → Database → Connection string (URI)**.
4. `cp .env.example .env` (on Windows: `copy .env.example .env`) and fill in `DJANGO_SECRET_KEY` and `DATABASE_URL`. (`.env` is git-ignored.)
5. `python manage.py migrate`
6. `python manage.py createsuperuser`. Superusers get the **Admin** role; everyone who registers at `/register/` starts as **Registration Staff**.
7. `python manage.py runserver` → http://127.0.0.1:8000/

### Setting up users and data for appointments
Log in at `/admin/` with the superuser account, then:
1. **Departments:** add at least one department (e.g. Pediatrics).
2. **Users and Profiles:** register Doctor and Nurse accounts at `/register/` (or create them in `/admin/` → Users). Open **Profiles**, set each user's role, and assign a department (required for Doctors and Nurses).
3. **Doctor profiles:** for each Doctor, add a **Doctor profile** with specialization and a unique license number.
4. **Patients:** log in as Admin, Nurse or Registration Staff and register patients at `/patients/new/`.
5. **Book:** log in as Admin or Registration Staff and book at `/appointments/new/`.

## Tests
`python manage.py test clinic` (32 tests). It needs `DATABASE_URL` pointing to a PostgreSQL server where the user can create a test database.

On Supabase, the run may end with a "test_postgres is being accessed by other users" error after all tests pass. That only affects the cleanup step.

## Branching
`main` (stable) ← `develop` (integration) ← `feature/<name>` branches. Feature branches are merged into `develop` through pull requests; `develop` is merged into `main` when an increment is done.
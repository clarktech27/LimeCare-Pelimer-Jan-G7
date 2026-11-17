# LimeCare – Project Development 1 (Account Feature)

Django (templates) + PostgreSQL/Supabase. Features: registration, login/logout, role-based dashboards (Admin / Staff), profile view & edit.

## Setup
1. `python -m venv venv` then activate it (`venv\Scripts\activate` on Windows).
2. `pip install -r requirements.txt`
3. Create a Supabase project, then copy **Project Settings → Database → Connection string (URI)**.
4. `cp .env.example .env` and fill in `DJANGO_SECRET_KEY` and `DATABASE_URL`. (`.env` is git-ignored.)
5. `python manage.py migrate`
6. `python manage.py createsuperuser` – superusers get the **Admin** role; everyone who registers is **Staff**.
7. `python manage.py runserver` → http://127.0.0.1:8000/

## Roles
| Role  | Dashboard | URL |
|-------|-----------|-----|
| Admin | user statistics + recent users | `/dashboard/admin/` |
| Staff | staff home | `/dashboard/staff/` |

Opening the other role's URL returns 403. Logged-out users are redirected to `/login/`. Admins can promote a user by changing the role in `/admin/` → Profiles.

## Tests
`python manage.py test` (needs `DATABASE_URL` pointing to a PostgreSQL server where the user can create a test DB).

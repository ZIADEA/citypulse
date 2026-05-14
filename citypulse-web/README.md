# CityPulse Web

Standalone Django 5 web portal for CityPulse desktop sync, driver workflows, and public/client tracking.

## Stack

- Django 5.x
- SQLite
- Tailwind CSS via CDN
- Vanilla JavaScript
- Deployment target: Vercel (`@vercel/python`) or Railway

## Quick start

1. Create and activate virtualenv.
2. Install deps:
   - `pip install -r requirements.txt`
3. Copy env file:
   - `cp .env.example .env` (Windows: `copy .env.example .env`)
4. Run migrations:
   - `python manage.py makemigrations`
   - `python manage.py migrate`
5. Create admin user:
   - `python manage.py createsuperuser`
6. Start server:
   - `python manage.py runserver`

## Auth

- Custom user model in `apps.accounts.models.User`
- Roles: `driver`, `client`
- django-allauth enabled with email verification mandatory

## Main pages

- Driver dashboard: `/driver/`
- Driver route detail: `/driver/route/<id>/`
- Driver history: `/driver/history/`
- Client dashboard: `/client/`
- Client tracking: `/client/track/<ref>/`
- Public tracking: `/track/<ref>/`

## API sync endpoints

See `SYNC_API.md` for full contract and examples.

## Deploy

### Vercel

1. Ensure env vars are set in Vercel project settings:
   - `SECRET_KEY_DJANGO`
   - `CITYPULSE_API_SECRET`
   - `DEBUG=False`
   - `ALLOWED_HOSTS=<your-domain>`
2. Deploy from this folder with included `vercel.json`.

### Railway

1. Set same env vars in Railway service variables.
2. Start command:
   - `python manage.py migrate && python manage.py collectstatic --noinput && gunicorn citypulse_web.wsgi`

## Management commands

- `python manage.py check`
- `python manage.py makemigrations`
- `python manage.py migrate`
- `python manage.py createsuperuser`

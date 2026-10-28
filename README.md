# Akhada Gym: gym management (Flask + Supabase)

Admin, trainer and member dashboards: members, trainers, payments, check-ins, classes, passes, workouts.

## Configuration
Copy `.env.example` to `.env` and fill it in. `SUPABASE_URL`, `SUPABASE_KEY` and `FLASK_SECRET_KEY` are
required; the app refuses to start without them. The secret key must be fixed (not random per start)
because gunicorn runs several workers.

```bash
python -m venv venv && venv/bin/pip install -r requirements.txt
FLASK_DEBUG=1 venv/bin/python app.py            # local
venv/bin/gunicorn app:app --bind 0.0.0.0:8080   # production
venv/bin/pip install pytest && venv/bin/python -m pytest   # tests use a fake database
```

## Security notes
- Passwords are stored as hashes (werkzeug). Rows created before that are plain text; they still log in
  and are upgraded to a hash on the first successful login.
- Sign-up only accepts the plans Basic, Premium and VIP. The `Admin` plan grants the admin role at login,
  so it can only be set on a row by an operator in the database.
- The database must not be readable with the public anon key. After redeploying with the `service_role`
  key in `SUPABASE_KEY`, run `database/lock_down.sql` in the Supabase SQL editor.

## The React front end (akhada-gym)
The separate React app logs people in from the browser by filtering the `members` table on the typed
password, which only works while the tables are readable with the public key. It cannot work after
`database/lock_down.sql`. Retire it, or change its login to call this Flask app, before locking down. Its
public day-pass booking form keeps working because the script leaves an insert-only policy for it.

# Deploying UniJos Journal System to cPanel

This guide deploys the Django app to cPanel using **Setup Python App** (Phusion
Passenger). It assumes a typical **shared cPanel** plan with **MySQL/MariaDB**,
**AutoSSL**, and SSH or Terminal access.

> ⚠️ **Read Section 0 first.** `production.py` is now cPanel-ready for **static
> (WhiteNoise)**, **database cache/sessions (no Redis)**, and the **PyMySQL** driver
> — all already committed. The **one** change you must still make is the database
> **engine** (Section 0.2): the repo defaults to PostgreSQL; switch it to MySQL for
> a typical cPanel plan.

---

## 0. Required code changes before you deploy

Make these three changes, commit, and push (or re-upload). They are the difference
between a working deploy and a 500 on first request.

### 0.1 Database driver + static server (already in `requirements.txt`)

`requirements.txt` already pins:

```
whitenoise==6.9.0
PyMySQL==1.1.1        # pure-Python MySQL driver — no compiler/dev headers needed
```

> ⚠️ **Do NOT use `mysqlclient` on shared cPanel.** It's a C extension that must
> compile against MySQL dev headers, which shared hosts don't provide — it fails
> with `Can not find valid pkg-config name`. We use **PyMySQL** instead, which is
> pure Python and installs cleanly. The shim that makes Django use it lives in
> `journalpro/__init__.py`:
>
> ```python
> import pymysql
> pymysql.install_as_MySQLdb()
> ```
>
> (PyMySQL reports `version_info (1, 4, 6, …)`, so Django's "mysqlclient ≥ 1.4.3"
> check passes — nothing else to do.)

- There is **no PostgreSQL** on most cPanel plans. If your host *does* offer it,
  use `psycopg2-binary==2.9.9` + the Postgres engine instead, and you can drop
  PyMySQL and the shim.

### 0.2 Switch the database engine to MySQL

In `journalpro/settings/production.py`, replace the `DATABASES` block:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='3306'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}
```

### 0.3 Redis removed — cache & sessions use the database (already done)

`production.py` **no longer references Redis.** Cache and sessions are stored in
the database, so nothing external is required:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache_table',
    }
}
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
```

You just create the cache table once with `manage.py createcachetable` (Step 7).

> If a `ModuleNotFoundError: No module named 'redis'` ever appears (e.g. during
> **login/admin**), it means an old `production.py` with `RedisCache` /
> `SESSION_ENGINE = ...cache` is deployed — pull the current version.

> **WhiteNoise** (0.1) serves your CSS/JS through Passenger, so you don't wire up
> static hosting separately. It's already installed and configured.

### 0.4 (Optional) relax HTTPS redirect until SSL is active

`SECURE_SSL_REDIRECT` defaults to `True`. Keep it `True` **after** AutoSSL is
issued. If you hit a redirect loop before SSL is ready, set `SECURE_SSL_REDIRECT=False`
in `.env` temporarily.

---

## 1. Create the MySQL database (cPanel → MySQL® Databases)

1. **Create Database** → e.g. `unijos_journal`. cPanel prefixes it: `cpuser_unijos_journal`.
2. **Create User** → e.g. `unijos_admin` with a strong password. Actual: `cpuser_unijos_admin`.
3. **Add User to Database** → grant **ALL PRIVILEGES**.
4. Note the final names — you'll put them in `.env`:
   - `DB_NAME=cpuser_unijos_journal`
   - `DB_USER=cpuser_unijos_admin`
   - `DB_HOST=localhost`
   - `DB_PORT=3306`

---

## 2. Upload the project

Pick one:

**Option A — Git (preferred).** cPanel → **Git™ Version Control** → Create →
clone your repo into e.g. `/home/cpuser/unijos_journal`.

**Option B — Zip upload.** Zip the project **without** `env/`, `db.sqlite3`,
`__pycache__/`, and `.git/`. Upload via **File Manager** into
`/home/cpuser/unijos_journal` and Extract.

> Do **not** upload the local `env/` virtualenv — cPanel builds its own.

---

## 3. Create the Python application (cPanel → Setup Python App)

1. **Create Application**.
2. **Python version**: choose 3.11 or 3.12 (matches the codebase).
3. **Application root**: `unijos_journal` (the folder from Step 2).
4. **Application URL**: your domain or subdomain (e.g. `journals.example.edu.ng`).
5. **Application startup file**: `passenger_wsgi.py`.
6. **Application Entry point**: `application`.
7. Click **Create**. cPanel creates a virtualenv and shows a command like:

   ```
   source /home/cpuser/virtualenv/unijos_journal/3.12/bin/activate && cd /home/cpuser/unijos_journal
   ```

   Copy that command — you'll use it in the terminal.

The repo already includes a `passenger_wsgi.py` that loads
`journalpro.settings.production`. If cPanel overwrote it with a stub, paste the
repo version back in.

---

## 4. Create the `.env` file

In the application root (`/home/cpuser/unijos_journal`), copy `.env.example` to
`.env` (File Manager → Copy, then rename, or `cp .env.example .env` in Terminal)
and fill it in:

```dotenv
SECRET_KEY=generate-a-long-random-50-char-string
DEBUG=False
ALLOWED_HOSTS=journals.example.edu.ng,www.journals.example.edu.ng

DB_NAME=cpuser_unijos_journal
DB_USER=cpuser_unijos_admin
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=3306

EMAIL_HOST=mail.example.edu.ng
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@example.edu.ng
EMAIL_HOST_PASSWORD=your-mailbox-password
DEFAULT_FROM_EMAIL=noreply@example.edu.ng
SERVER_EMAIL=server@example.edu.ng
ADMIN_EMAIL=admin@example.edu.ng

# Leave True once AutoSSL is active; set False temporarily if you get a redirect loop.
SECURE_SSL_REDIRECT=True
```

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

> `python-decouple` reads this `.env` automatically. Keep `.env` out of Git.

---

## 5. Install dependencies

Open cPanel → **Terminal** (or SSH) and run the activation command from Step 3,
then install:

```bash
source /home/cpuser/virtualenv/unijos_journal/3.12/bin/activate && cd /home/cpuser/unijos_journal
pip install --upgrade pip
pip install -r requirements.txt
```

This installs **PyMySQL** (no compilation), so the MySQL driver "just works." The
`journalpro/__init__.py` shim wires it into Django automatically.

> If you ever see `Can not find valid pkg-config name` or a build error mentioning
> `mysqlclient`, it means `mysqlclient` crept back into `requirements.txt` — remove
> it; the project uses **PyMySQL** on purpose.

---

## 6. Point Passenger at the right settings (Environment Variables)

In the **Setup Python App** screen for this app, add an environment variable so
Passenger and management commands agree:

- `DJANGO_SETTINGS_MODULE = journalpro.settings.production`

(`passenger_wsgi.py` already sets this as a default, but setting it explicitly is
cleaner and also affects the Terminal.)

---

## 7. Django one-time setup

With the virtualenv active in the app root:

```bash
export DJANGO_SETTINGS_MODULE=journalpro.settings.production
python manage.py createcachetable          # needed for DB cache (Section 0.3)
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
mkdir -p logs media                        # logging + uploads dirs
```

- `collectstatic` gathers everything into `staticfiles/`, which **WhiteNoise**
  serves. No public_html symlink is required for static files.

---

## 8. Media (user uploads)

Uploads go to `MEDIA_ROOT = <app>/media/` and are served at `/media/`. WhiteNoise
does **not** serve media, and Django's default media helper only works when
`DEBUG=True` — so `journalpro/urls.py` routes `/media/` through Django in **all**
environments (already committed). No symlink or Apache config is required.

You only need to make sure the folder exists and is writable:

```bash
mkdir -p media && chmod 755 media
```

- New uploads are served immediately (no restart/collectstatic needed for media).
- If you later outgrow Django-served media, move to object storage (S3) via the
  commented block in `production.py`, or serve `/media/` from the web server.

---

## 9. Start it up

1. Back in **Setup Python App**, click **Restart**.
2. Visit `https://journals.example.edu.ng/`.
3. cPanel → **SSL/TLS Status** → run **AutoSSL** for the domain if HTTPS isn't live.
4. Confirm the home page, `/admin/`, login, and a submission flow all load.

Whenever you change `.env`, settings, or Python code: **Restart** the app (or
`touch tmp/restart.txt` in the app root).

---

## 10. Redeploy / update workflow

```bash
source /home/cpuser/virtualenv/unijos_journal/3.12/bin/activate && cd /home/cpuser/unijos_journal
git pull                      # or re-upload changed files
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
mkdir -p tmp && touch tmp/restart.txt      # graceful Passenger restart
```

---

## 11. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| **500 on every page, blank** | Check `logs/django_error.log` and cPanel's stderr log. Usually a missing package or a bad `.env` value. |
| `ModuleNotFoundError: redis` (often on login/admin) | An old `production.py` with `RedisCache`/cache-sessions is deployed. Pull the current version (Redis is removed), then `createcachetable`, `migrate`, restart. |
| `No module named 'MySQLdb'` | PyMySQL not installed (`pip install -r requirements.txt`), or the shim in `journalpro/__init__.py` was removed. |
| `Can not find valid pkg-config name` / mysqlclient build fails | You're trying to build `mysqlclient`. Don't — use **PyMySQL** (already in requirements); remove any `mysqlclient` line. |
| `django.db.utils.OperationalError` | Wrong `DB_*` values, or user not added to the DB with privileges (Step 1). |
| CSS/JS missing (unstyled site) | Run `collectstatic`; confirm `whitenoise` installed and its middleware line is present in `production.py`. |
| Uploaded images 404 (`/media/...`) | Deploy the current `journalpro/urls.py` (it serves `/media/` in production), then restart. Also confirm `media/` exists and the file is on disk. |
| `DisallowedHost` | Add the exact domain(s) to `ALLOWED_HOSTS` in `.env`, then restart. |
| Infinite HTTPS redirect | Set `SECURE_SSL_REDIRECT=False` until AutoSSL is issued, then flip back to `True`. |
| CSRF "Origin checking failed" | Add `CSRF_TRUSTED_ORIGINS=https://journals.example.edu.ng` handling (add to `production.py` from env) if on Django's stricter CSRF. |
| `OpenBLAS blas_thread_init: pthread_create failed` / `migrate` hangs at `import numpy` | Shared-host process limit vs. OpenBLAS spawning one thread per core. `manage.py` and `passenger_wsgi.py` now set `OPENBLAS_NUM_THREADS=1` (plus OMP/MKL/NUMEXPR) — deploy the current versions. For an ad-hoc shell command, prefix it: `OPENBLAS_NUM_THREADS=1 python manage.py migrate --settings=journalpro.settings.production`. |
| Changes not showing | Restart the app / `touch tmp/restart.txt`. |

---

## 12. Post-deploy checklist

- [ ] `DEBUG=False`, unique `SECRET_KEY`, correct `ALLOWED_HOSTS`
- [ ] AutoSSL active; site loads over HTTPS
- [ ] `migrate`, `createcachetable`, `createsuperuser`, `collectstatic` all run
- [ ] Static assets and uploaded media load
- [ ] Test email sends (registration / reviewer invitation)
- [ ] Site Settings → brand colors/logo verified in the admin
- [ ] `.env`, `db.sqlite3`, and `env/` are **not** in the repo/upload

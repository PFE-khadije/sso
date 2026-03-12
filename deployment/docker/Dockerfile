FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN pip install --no-cache-dir whitenoise==6.7.0

COPY backend/ /app/

# Staging-only build-time patch: ensure static files are served under gunicorn.
RUN python - <<'PY'
from pathlib import Path

p = Path('/app/config/settings.py')
t = p.read_text()

if "whitenoise.middleware.WhiteNoiseMiddleware" not in t:
    t = t.replace(
        "'django.middleware.security.SecurityMiddleware',",
        "'django.middleware.security.SecurityMiddleware',\n    'whitenoise.middleware.WhiteNoiseMiddleware',",
    )

t = t.replace("STATIC_URL = 'static/'", "STATIC_URL = '/static/'")

if "STATIC_ROOT = BASE_DIR / 'staticfiles'" not in t:
    t = t.replace(
        "STATIC_URL = '/static/'",
        "STATIC_URL = '/static/'\nSTATIC_ROOT = BASE_DIR / 'staticfiles'",
    )

if "STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'" not in t:
    t += "\n\nif not DEBUG:\n    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'\n"

p.write_text(t)
PY

CMD ["sh", "-lc", "python manage.py collectstatic --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000"]

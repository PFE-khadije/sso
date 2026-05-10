FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

# Copier et installer les dépendances Python
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY ./backend /app

# Exposer le port (Render utilisera la variable d'environnement PORT)
EXPOSE 8000

# Copy release/migration script before CMD so it is available at runtime
COPY release.sh /app/
RUN chmod +x /app/release.sh

# Script de démarrage avec Gunicorn
# Utilise la variable d'environnement PORT fournie par Render (par défaut 10000)
# Le chemin 'config.wsgi:application' est correct car le fichier wsgi.py se trouve dans /app/config/
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
FROM python:3.11-slim

WORKDIR /app

# Installer les dépendances système nécessaires pour OpenCV et MTCNN
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY ai_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ai_service /app

EXPOSE 5001

CMD ["gunicorn", "--bind", "0.0.0.0:5001", "app:create_app()"]
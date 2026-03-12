FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend/ /app/
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]

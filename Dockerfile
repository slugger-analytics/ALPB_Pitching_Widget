FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

WORKDIR /app

COPY python_app/requirements.txt /app/python_app/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r /app/python_app/requirements.txt

COPY . /app

EXPOSE 7860

CMD ["sh", "-c", "gunicorn python_app.app:server --bind 0.0.0.0:${PORT:-7860} --workers 1 --threads 2 --timeout 180"]

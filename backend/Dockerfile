FROM python:3.12-slim
ENV TZ=America/Lima PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
ARG DEV=1
RUN pip install --no-cache-dir -r $( [ "$DEV" = "1" ] && echo requirements-dev.txt || echo requirements.txt )
COPY . .
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips="*" --root-path "${ROOT_PATH:-}"

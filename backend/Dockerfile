FROM python:3.12-slim
ENV TZ=America/Lima PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
ARG DEV=1
RUN pip install --no-cache-dir -r $( [ "$DEV" = "1" ] && echo requirements-dev.txt || echo requirements.txt )
COPY . .
CMD ["sh", "start.sh"]

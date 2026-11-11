FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic
COPY scripts ./scripts

# El hosting define PORT; en local se usa 8000.
EXPOSE 8000

CMD ["sh", "scripts/start.sh"]

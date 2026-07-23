FROM python:3.11-slim

WORKDIR /app

# Install system deps only if needed (none for FastAPI)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all packages and app
COPY packages/ ./packages/
COPY apps/ ./apps/
COPY pyproject.toml .

ENV PYTHONPATH=/app:/app/packages
ENV API_PORT=8000

EXPOSE 8000

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

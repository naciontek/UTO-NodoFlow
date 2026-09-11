FROM python:3.12.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home nodoflow
COPY backend/nodoflow ./nodoflow
USER nodoflow
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "nodoflow.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Build React frontend
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /build/frontend

COPY frontend/package.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build
# Output: /build/frontend/dist/

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Python runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY --from=frontend-builder /build/frontend/dist/ ./frontend/dist/

# Create /data directories with correct permissions
RUN mkdir -p /data/ca_keys && chmod 700 /data

# Non-root user
RUN useradd -m -u 1001 camanager \
    && chown -R camanager:camanager /app /data
USER camanager

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

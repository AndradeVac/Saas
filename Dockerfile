# Mesa Digital: one image with the API and the built frontend (served by app.web).
# Build: fly deploy (remote builder) or docker build --build-arg VITE_ROOT_DOMAIN=seudominio.com .

# ---- frontend -------------------------------------------------------------------------------
FROM node:24-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Domain the tenant subdomains live under (padaria.<domain>); baked into the bundle at build time.
ARG VITE_ROOT_DOMAIN
RUN test -n "$VITE_ROOT_DOMAIN" || (echo "Defina VITE_ROOT_DOMAIN (fly.toml > [build.args])" && exit 1)
ENV VITE_ROOT_DOMAIN=$VITE_ROOT_DOMAIN
RUN npm run build

# ---- runtime --------------------------------------------------------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FRONTEND_DIST=/app/frontend/dist
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app
EXPOSE 8080
# Fly's proxy (and Cloudflare in front of it) set X-Forwarded-For with the customer's IP.
CMD ["sh", "-c", "exec uvicorn app.web:web --host 0.0.0.0 --port 8080 --workers ${WEB_CONCURRENCY:-2} --proxy-headers --forwarded-allow-ips '*' --timeout-graceful-shutdown 10"]

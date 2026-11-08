FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json tsconfig.json vite.config.ts ./
COPY frontend ./frontend
RUN npm ci && npm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN groupadd --gid 10001 nteam && useradd --uid 10001 --gid nteam --create-home nteam
COPY backend ./backend
RUN python -m pip install --no-cache-dir -c backend/requirements-tested.txt ./backend
COPY scripts ./scripts
COPY --from=frontend /build/dist ./dist
RUN mkdir -p /app/data && chown -R nteam:nteam /app/data
USER nteam
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"
CMD ["python", "scripts/serve.py", "--host", "0.0.0.0"]

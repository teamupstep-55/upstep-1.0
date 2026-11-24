# One image: builds the React site, then runs Flask (API + website + search-engine pages) with gunicorn.
# Works on Render, Koyeb, Fly.io, Railway, or any VPS:  docker build -t upstep . && docker run -p 10000:10000 --env-file backend/.env upstep
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY supabase/ /app/supabase/
COPY --from=web /web/dist /app/frontend/dist
ENV FRONTEND_DIST=/app/frontend/dist PRODUCTION=1 TRUST_PROXY=1 PORT=10000
EXPOSE 10000
# one worker + threads: small free instances have little memory, and per-process rate limits stay accurate
CMD ["sh", "-c", "gunicorn -w 1 --threads 8 --timeout 120 -b 0.0.0.0:${PORT} 'app:create_app()'"]

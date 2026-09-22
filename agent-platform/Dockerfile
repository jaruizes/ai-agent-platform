FROM node:22-bookworm-slim AS mcp-builder

WORKDIR /build/google-workspace
COPY mcp/google-workspace/package.json ./
COPY mcp/google-workspace/tsconfig.json ./
RUN npm install

COPY mcp/google-workspace/src ./src
RUN npm run build && npm prune --omit=dev


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs libreoffice-core libreoffice-writer libreoffice-calc libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

COPY agent-platform/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent-platform/app ./app
COPY agent-platform/migrations ./migrations
COPY agent-platform/bootstrap ./bootstrap

COPY --from=mcp-builder /build/google-workspace /opt/mcp/google-workspace

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

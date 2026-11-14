# Game server + built web app in one image. Build from the repo root:
#   docker build -f server/Dockerfile -t junction-server .
#   docker run -p 8000:8000 -v junction-data:/data junction-server                       # live (records traces)
#   docker run -p 8000:8000 -e PUBLISHED_MODE=1 junction-server                          # public read-only demo
#   docker run -i junction-server python -m server mcp                                   # MCP over stdio
#   docker run -p 8001:8001 junction-server python -m server mcp --transport streamable-http --port 8001

FROM node:22-slim AS web
WORKDIR /repo/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
COPY data/fixtures /repo/data/fixtures
RUN VITE_API=/api npm run build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 DATA_DIR=/data PORT=8000
WORKDIR /repo
COPY engine/ engine/
COPY server/ server/
RUN pip install ./engine ./server
COPY contracts/ contracts/
COPY data/collections/ data/collections/
COPY data/fixtures/ data/fixtures/
COPY data/published/ data/published/
COPY --from=web /repo/web/dist web/dist
# installed (non-editable) packages resolve the repo root from site-packages; point them at /repo
ENV WEB_DIST=/repo/web/dist ENGINE_COLLECTIONS_DIR=/repo/data/collections REPO_ROOT=/repo
VOLUME /data
EXPOSE 8000
CMD ["python", "-m", "server", "serve", "--port", "8000"]

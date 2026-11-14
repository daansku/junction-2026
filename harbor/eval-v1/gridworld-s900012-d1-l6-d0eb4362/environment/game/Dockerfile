FROM python:3.12-slim
RUN pip install --no-cache-dir "mcp>=1.6,<2"
WORKDIR /srv
COPY engine /srv/engine
COPY arena /srv/arena
COPY contracts /srv/contracts
COPY collection.json /srv/collection.json
ENV PYTHONPATH=/srv:/srv/vendor ARENA_REPO_ROOT=/srv GAME_COLLECTION=/srv/collection.json PORT=8000
EXPOSE 8000
CMD ["python", "-m", "arena.harbor.sidecar"]

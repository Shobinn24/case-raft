# CaseRaft MCP service (mcp.caseraft.com)
# Separate Railway service; shares only Postgres with the Flask app.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY caseraft_mcp ./caseraft_mcp
RUN pip install --no-cache-dir .

# Railway injects PORT. No aggressive request timeout: claude.ai tool calls
# can run up to 300s, which is why this does not live behind the Flask
# gunicorn (120s hard timeout).
ENV PORT=8080
CMD ["sh", "-c", "uvicorn caseraft_mcp.server:app --host 0.0.0.0 --port ${PORT}"]

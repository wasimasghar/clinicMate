FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY clinicmate_backend/requirements.txt backend-req.txt
COPY clinicmate_mcp_server/requirements.txt mcp-req.txt
RUN pip install --no-cache-dir -r backend-req.txt -r mcp-req.txt

COPY clinicmate_backend/ backend/
COPY clinicmate_mcp_server/ mcp_server/

ENV MCP_SERVER_PYTHON=/usr/local/bin/python
ENV MCP_SERVER_SCRIPT=/app/mcp_server/server.py

WORKDIR /app/backend
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
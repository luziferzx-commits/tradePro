# Build Stage
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production Stage
FROM python:3.11-slim

# Security: Run as non-root user
RUN useradd -m -r gqos_user
USER gqos_user

WORKDIR /app

# Copy deterministic dependencies
COPY --from=builder /root/.local /home/gqos_user/.local
ENV PATH=/home/gqos_user/.local/bin:$PATH

# Copy application source code
COPY gqos/ ./gqos/

# Set immutable environments
ENV PYTHONUNBUFFERED=1

# Expose metrics and health endpoints
EXPOSE 8000
EXPOSE 8080

# Default entrypoint (can be overridden by docker-compose for research vs live)
CMD ["python", "-m", "gqos.live.engine"]

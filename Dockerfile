# RouteRight - Docker Container Setup
FROM python:3.11-slim

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration and install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Copy application source code
COPY routeright/ routeright/
COPY scripts/ scripts/
COPY config/ config/
COPY data/ data/
COPY results/ results/

# Default environment: Decider on 8001, App on 8000
ENV ROUTERIGHT_HOST=0.0.0.0
ENV ROUTERIGHT_PORT=8000
ENV ROUTERIGHT_DECIDER_URL=http://127.0.0.1:8001

EXPOSE 8000 8001

CMD ["python", "-m", "routeright.cli", "start", "--no-browser"]

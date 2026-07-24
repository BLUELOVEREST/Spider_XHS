FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN python --version && node --version && npm --version

COPY requirements.txt .
COPY package.json package-lock.json ./

RUN pip install --no-cache-dir -r requirements.txt
RUN npm ci --omit=dev

COPY . .

EXPOSE 18061

ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV XHS_DOWNLOAD_DIR=/downloads

RUN mkdir -p /downloads

VOLUME ["/downloads"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:18061/health || exit 1

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "18061"]

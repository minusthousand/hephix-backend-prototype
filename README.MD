# Hephix API Prototype

A minimal FastAPI service with a single `/chat` endpoint that scrapes search results from online.depo.lv based on your message.

## Requirements

- Python 3.10+
- `fastapi`
- `uvicorn`
- `httpx`
- `beautifulsoup4` (optional, improves parsing)
- `playwright` (optional, improves JS-rendered pages)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Optional: install Playwright browsers
playwright install
```

## Run

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Docker (for AWS)

```bash
docker build -t hephix-api .
docker run --rm -p 8080:8080 hephix-api
```

The container listens on port `8080` (or `PORT` if set).

## AWS deployment (EC2 + Docker)

### 1) Launch EC2

- AMI: Ubuntu 22.04
- Instance type: `t2.micro` or `t3.micro` (free tier eligible)
- Security group inbound:
  - SSH `22` from your IP
  - HTTP `80` from `0.0.0.0/0`
  - HTTPS `443` from `0.0.0.0/0` (if using TLS)

### 2) Install Docker

```bash
sudo apt update
sudo apt install -y docker.io
sudo usermod -aG docker ubuntu
newgrp docker
```

### 3) Deploy

```bash
git clone https://github.com/minusthousand/hephix-backend-prototype.git
cd hephix-backend-prototype
docker build -t hephix-api .
docker run -d --restart unless-stopped -p 8080:8080 --name hephix-api hephix-api
```

### 4) Reverse proxy (optional, for HTTPS)

If you use Cloudflare or your own TLS termination, run Nginx on ports 80/443
and proxy to `http://127.0.0.1:8080`.

### CORS

Set allowed origins via env var:

```bash
export CORS_ORIGINS="https://your-site.netlify.app"
```

Note: Playwright is optional. If you need it inside Docker, ensure `playwright` is in
`requirements.txt` and install browsers during the image build.

## Endpoint

### POST /chat

Request body:

```json
{
  "message": "hello"
}
```

Response body:

```json
{
  "message": "Search results for 'hello' on online.depo.lv:\n\n1. ...\n"
}
```

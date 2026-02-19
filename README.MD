# Hephix API Prototype

A FastAPI backend that powers Hephix — a multi-store shopping assistant with MCP-backed tools.

## Requirements

- Python 3.10+
- `fastapi`
- `uvicorn`
- `httpx`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Environment

Core:

```bash
export CORS_ORIGINS="https://your-site.netlify.app"
export ENABLE_FRONTEND=true  # optional, enables GET /
```

Anthropic (required for chat):

```bash
export ANTHROPIC_API_KEY="..."
export ANTHROPIC_MODEL="claude-haiku-4-5-20251001"  # optional
```

eBay (required for /chat/ebay):

```bash
export EBAY_CLIENT_ID="..."
export EBAY_CLIENT_SECRET="..."
export EBAY_ENV=production        # or sandbox
export EBAY_MARKETPLACE_ID=EBAY_US
```

eBay Marketplace Account Deletion (required for compliance webhook):

```bash
export EBAY_MAD_ENABLED=true
export EBAY_MAD_VERIFICATION_TOKEN="your-verification-token"
export EBAY_MAD_ENDPOINT_URL="https://your.domain/ebay/account-deletion"
```

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

## Endpoints

### POST /chat

Default store (Depo.lv).

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

### POST /chat/darel

Darel.lv store. Same request/response shape as `/chat`.

### POST /chat/ebay

eBay store (Browse API). Same request/response shape as `/chat`.

### GET /

Static frontend (only when `ENABLE_FRONTEND=true`).

### GET /sessions

List chat sessions.

### GET /sessions/{id}

Get full chat history for a session.

### DELETE /sessions/{id}

Delete a chat session.

### GET /mcp/info

Inspect MCP tool status per store.

### GET /ebay/account-deletion

eBay Marketplace account deletion challenge endpoint.

### POST /ebay/account-deletion

eBay Marketplace account deletion notifications (acknowledged immediately; data deletion handled server-side).

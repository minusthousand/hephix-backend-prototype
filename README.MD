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

## AWS deployment options

### AWS App Runner (simplest)

1. Push this repo to GitHub.
2. In AWS App Runner, create a new service from source or a container image.
3. If using source, select the repo and branch; App Runner will build the Dockerfile.
4. Set runtime environment variables if needed (none required by default).

### ECS Fargate (container)

1. Build and push the image to ECR.
2. Create an ECS Fargate service using port `8080`.
3. Put the service behind an Application Load Balancer.

### Elastic Beanstalk (Docker)

1. Create a new Beanstalk application with the Docker platform.
2. Deploy the repo; Beanstalk will build the Dockerfile.

Note: Playwright is optional and not installed in the Docker image by default. If you need it, add `playwright` to `requirements.txt` and run `playwright install` during image build.

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

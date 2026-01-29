# Hephix Backend - MCP Integration Guide

This project integrates the **Model Context Protocol (MCP)** to enable seamless communication between the FastAPI backend and MCP clients.

## Project Structure

```
├── main.py                 # FastAPI app with MCP endpoints
├── mcp_server.py          # MCP server entry point
├── requirements.txt       # Python dependencies
├── schemas.py             # Pydantic models
├── routers/
│   ├── __init__.py
│   └── chat.py            # Chat API routes
└── services/
    ├── __init__.py
    ├── depo_store.py      # MCP tools & GraphQL integration
    ├── graphql_service.py # GraphQL utilities
    └── mcp_client.py      # MCP client wrapper
```

## Running the Application

### Option 1: FastAPI Backend Only

```bash
python -m uvicorn main:app --reload --port 8001
```

The API will be available at `http://127.0.0.1:8001` with the following endpoints:
- `GET /` - API info
- `GET /health` - Health check
- `GET /mcp/info` - MCP configuration info
- `POST /chat` - Chat/search endpoint
- `OPTIONS /chat` - CORS options

### Option 2: MCP Server Only

```bash
python mcp_server.py
```

This runs the MCP server using stdio transport, suitable for use with MCP clients like Claude or Cline.

### Option 3: Both (Recommended for Development)

Terminal 1:
```bash
python -m uvicorn main:app --reload --port 8001
```

Terminal 2:
```bash
python mcp_server.py
```

## API Endpoints

### Root Endpoint
```bash
GET http://127.0.0.1:8001/
```

Response:
```json
{
  "name": "Hephix Backend",
  "version": "1.0.0",
  "status": "running",
  "endpoints": {
    "chat": "/chat (POST)",
    "health": "/health (GET)",
    "mcp-info": "/mcp/info (GET)"
  }
}
```

### Health Check
```bash
GET http://127.0.0.1:8001/health
```

Response:
```json
{
  "status": "healthy"
}
```

### MCP Info
```bash
GET http://127.0.0.1:8001/mcp/info
```

Response:
```json
{
  "mcp_enabled": true,
  "server_name": "depo-store",
  "tools": [
    {
      "name": "search_products",
      "description": "Search for products on online.depo.lv via GraphQL",
      "input_schema": {
        "type": "object",
        "properties": {
          "query": {
            "type": "string",
            "description": "Search query"
          },
          "limit": {
            "type": "integer",
            "description": "Maximum number of results (1-50)",
            "default": 10
          }
        },
        "required": ["query"]
      }
    }
  ]
}
```

### Chat/Search Endpoint
```bash
POST http://127.0.0.1:8001/chat
Content-Type: application/json

{
  "message": "hammer",
  "limit": 5
}
```

Response:
```json
{
  "message": "Search results from online.depo.lv:\n\n1. Product Name\n   Price: €19.99 / piece\n   Availability: In stock (10 total)\n   Barcode: 1234567890\n   Image: https://..."
}
```

## MCP Server

The MCP server exposes the `search_products` tool which can be used by MCP clients.

### Using with MCP Clients

Configure your MCP client to use stdio transport:

```json
{
  "mcpServers": {
    "depo-store": {
      "command": "python",
      "args": ["mcp_server.py"],
      "cwd": "/path/to/hephix-backend-prototype"
    }
  }
}
```

### Available Tools

#### search_products
Searches for products on online.depo.lv.

**Parameters:**
- `query` (string, required): Product search query
- `limit` (integer, optional): Number of results (1-50, default: 10)

**Returns:** Formatted product listing with prices, availability, and links

## Architecture

### FastAPI Layer
- Handles HTTP requests
- CORS middleware enabled
- RESTful endpoints for chat/search
- MCP configuration exposure

### MCP Layer
- Exposes tools via MCP protocol
- Communicates via stdio transport
- Encapsulates business logic
- Independent from HTTP server

### Services Layer
- `depo_store.py`: MCP tool definitions and GraphQL queries
- `graphql_service.py`: GraphQL request handling
- `mcp_client.py`: MCP client wrapper for RPC calls

## Development

### Adding New MCP Tools

In `services/depo_store.py`:

```python
@mcp.tool()
async def my_new_tool(param1: str, param2: int = 10) -> str:
    """Tool description."""
    # Implementation
    return result
```

### Adding New FastAPI Routes

In `routers/chat.py` or create a new router:

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/my-endpoint")
async def my_endpoint():
    return {"message": "hello"}
```

Then include in `main.py`:
```python
app.include_router(router)
```

## Dependencies

- `fastapi` - Web framework
- `uvicorn[standard]` - ASGI server
- `httpx` - Async HTTP client
- `mcp` - Model Context Protocol SDK
- `pydantic` - Data validation

Install with:
```bash
pip install -r requirements.txt
```

## Environment Variables

- `CORS_ORIGINS` - Comma-separated list of allowed CORS origins (default: "*")

Example:
```bash
export CORS_ORIGINS="http://localhost:3000,http://localhost:8000"
```

## Troubleshooting

### MCP Server won't start
- Ensure `mcp` package is installed: `pip install mcp`
- Check Python version (3.10+)
- Look for errors in stderr

### API returns 404
- Verify correct endpoint path
- Use POST for `/chat`, GET for others

### Connection errors to depo.lv
- Check internet connection
- GraphQL endpoint might be down
- Check `DEPO_GRAPHQL_ENDPOINT` in `services/depo_store.py`

## Docker

A `Dockerfile` is included for containerization:

```bash
docker build -t hephix-backend .
docker run -p 8001:8000 hephix-backend
```

Note: MCP server via stdio may require special handling in Docker.

## License

[Add your license info here]

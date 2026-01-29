import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from routers.chat import router as chat_router
from services.mcp_client import MCPClient, MCPClientError

app = FastAPI(
    title="Hephix Backend",
    description="FastAPI backend with MCP integration",
    version="1.0.0"
)

cors_origins_env = os.getenv("CORS_ORIGINS", "").strip()
cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint - interactive search UI."""
    return """
    <!doctype html>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hephix Search - Depo & Darel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { font-size: 1.1em; opacity: 0.9; }
        .search-box {
            background: white;
            border-radius: 50px;
            padding: 15px 25px;
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .search-box input {
            flex: 1;
            border: none;
            outline: none;
            font-size: 16px;
            padding: 5px 0;
        }
        .search-box button {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 30px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: background 0.3s;
        }
        .search-box button:hover { background: #764ba2; }
        .results {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }
        .product-card {
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .product-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }
        .product-image {
            width: 100%;
            height: 200px;
            background: #f5f5f5;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        .product-image img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        .product-content {
            padding: 15px;
        }
        .product-source {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75em;
            font-weight: 600;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        .source-depo { background: #e3f2fd; color: #1976d2; }
        .source-darel { background: #f3e5f5; color: #7b1fa2; }
        .product-name {
            font-size: 1.1em;
            font-weight: 600;
            margin-bottom: 10px;
            line-height: 1.4;
            min-height: 2.8em;
        }
        .product-price {
            font-size: 1.8em;
            color: #667eea;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .product-meta {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }
        .product-link {
            display: inline-block;
            color: #667eea;
            text-decoration: none;
            font-size: 0.9em;
            font-weight: 500;
            margin-top: 10px;
        }
        .product-link:hover { text-decoration: underline; }
        .loading { text-align: center; color: white; margin: 20px 0; }
        .error { 
            background: #ff6b6b; 
            color: white; 
            padding: 15px; 
            border-radius: 8px; 
            margin: 20px 0;
        }
        .no-results {
            text-align: center;
            color: white;
            padding: 40px;
            font-size: 1.2em;
        }
    </style>
    
    <div class="container">
        <div class="header">
            <h1>🔍 Product Search</h1>
            <p>Search Depo & Darel stores</p>
        </div>
        
        <div class="search-box">
            <input type="text" id="query" placeholder="Search products..." autocomplete="off">
            <button onclick="search()">Search</button>
        </div>
        
        <div id="error" class="error" style="display:none;"></div>
        <div id="loading" class="loading" style="display:none;">Searching...</div>
        <div id="results" class="results"></div>
    </div>
    
    <script>
        async function search() {
            const query = document.getElementById('query').value.trim();
            if (!query) return;
            
            document.getElementById('loading').style.display = 'block';
            document.getElementById('error').style.display = 'none';
            document.getElementById('results').innerHTML = '';
            
            try {
                const res = await fetch('/search?q=' + encodeURIComponent(query) + '&limit=20');
                if (!res.ok) throw new Error('API error');
                
                const data = await res.json();
                const results = data.results || [];
                
                if (results.length === 0) {
                    document.getElementById('results').innerHTML = '<div class="no-results">No products found</div>';
                    return;
                }
                
                const html = results.map(p => `
                    <div class="product-card">
                        ${p.thumbnail ? `<div class="product-image"><img src="${p.thumbnail}" alt="${p.name}"></div>` : '<div class="product-image"></div>'}
                        <div class="product-content">
                            <span class="product-source ${p.source === 'depo' ? 'source-depo' : 'source-darel'}">
                                ${p.source === 'depo' ? 'Depo.lv' : 'Darel.lv'}
                            </span>
                            <div class="product-name">${escapeHtml(p.name)}</div>
                            <div class="product-price">${p.price}${p.unit ? ' / ' + escapeHtml(p.unit) : ''}</div>
                            ${p.availability ? `<div class="product-meta">📦 ${escapeHtml(p.availability)}</div>` : ''}
                            ${p.barcode ? `<div class="product-meta">🔖 ${escapeHtml(p.barcode)}</div>` : ''}
                            ${p.manufacturer_name ? `<div class="product-meta">🏭 ${escapeHtml(p.manufacturer_name)}</div>` : ''}
                            ${p.url ? `<a href="${p.url}" target="_blank" class="product-link">View on store →</a>` : ''}
                        </div>
                    </div>
                `).join('');
                
                document.getElementById('results').innerHTML = html;
            } catch (e) {
                document.getElementById('error').style.display = 'block';
                document.getElementById('error').textContent = 'Error: ' + e.message;
            } finally {
                document.getElementById('loading').style.display = 'none';
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        document.getElementById('query').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') search();
        });
        
        document.getElementById('query').focus();
    </script>
    """



@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/mcp/info")
async def mcp_info():
    """Get MCP server information."""
    return {
        "mcp_enabled": True,
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

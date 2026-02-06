import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from core import DEPO_RUNTIME, DAREL_RUNTIME
from routers.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start MCP runtimes on startup, tear down on shutdown."""
    await DEPO_RUNTIME.start()
    # Darel started lazily on first /chat/darel request (may fail on EC2),
    # but we still try here so tools show up in /mcp/info.
    try:
        await DAREL_RUNTIME.start()
    except Exception as e:
        print(f"⚠️  Darel runtime failed to start (non-fatal): {e}")
    yield
    await DEPO_RUNTIME.aclose()
    await DAREL_RUNTIME.aclose()


app = FastAPI(
    title="Hephix Backend",
    description="FastAPI backend with MCP-powered AI chat",
    version="2.0.0",
    lifespan=lifespan,
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
    """Root endpoint — interactive chat UI with session sidebar."""
    return """
    <!doctype html>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hephix — Shopping Assistant</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f0f2f5;
            height: 100vh;
            display: flex;
        }

        /* ─── Sidebar ─── */
        #sidebar {
            width: 280px;
            background: #1a1a2e;
            color: #ccc;
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }
        #sidebar-header {
            padding: 20px 16px 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #2a2a4a;
        }
        #sidebar-header h2 {
            font-size: 1.1em;
            color: #fff;
        }
        #new-chat-btn {
            background: #667eea;
            color: #fff;
            border: none;
            padding: 6px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: background 0.2s;
        }
        #new-chat-btn:hover { background: #5a6fd6; }
        #session-list {
            flex: 1;
            overflow-y: auto;
            padding: 8px;
        }
        .session-item {
            padding: 10px 12px;
            border-radius: 8px;
            cursor: pointer;
            margin-bottom: 4px;
            font-size: 13px;
            transition: background 0.15s;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .session-item:hover { background: #2a2a4a; }
        .session-item.active { background: #333366; color: #fff; }
        .session-time {
            font-size: 11px;
            color: #888;
            margin-top: 2px;
        }

        /* ─── Store toggle ─── */
        #store-toggle {
            padding: 12px 16px;
            border-top: 1px solid #2a2a4a;
        }
        #store-toggle label {
            font-size: 12px;
            color: #999;
            display: block;
            margin-bottom: 6px;
        }
        #store-select {
            width: 100%;
            padding: 8px 10px;
            border-radius: 6px;
            border: 1px solid #444;
            background: #2a2a4a;
            color: #fff;
            font-size: 13px;
        }

        /* ─── Main Chat Area ─── */
        #main {
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
        }
        #header {
            background: #fff;
            padding: 16px 24px;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        #header h1 {
            font-size: 1.3em;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        #store-badge {
            font-size: 0.75em;
            padding: 3px 10px;
            border-radius: 12px;
            font-weight: 600;
        }
        .badge-depo { background: #e3f2fd; color: #1976d2; }
        .badge-darel { background: #f3e5f5; color: #7b1fa2; }

        /* ─── Messages ─── */
        #messages {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .msg {
            max-width: 75%;
            padding: 12px 16px;
            border-radius: 16px;
            line-height: 1.5;
            font-size: 14px;
            word-wrap: break-word;
            white-space: pre-wrap;
        }
        .msg.user {
            align-self: flex-end;
            background: #667eea;
            color: #fff;
            border-bottom-right-radius: 4px;
        }
        .msg.ai {
            align-self: flex-start;
            background: #fff;
            color: #333;
            border: 1px solid #e0e0e0;
            border-bottom-left-radius: 4px;
        }
        .msg.system {
            align-self: center;
            background: transparent;
            color: #999;
            font-size: 12px;
            font-style: italic;
        }
        #typing {
            display: none;
            align-self: flex-start;
            padding: 12px 16px;
            background: #fff;
            border: 1px solid #e0e0e0;
            border-radius: 16px;
            border-bottom-left-radius: 4px;
            color: #999;
            font-size: 14px;
        }

        /* ─── Input Area ─── */
        #input-area {
            padding: 16px 24px;
            background: #fff;
            border-top: 1px solid #e0e0e0;
            display: flex;
            gap: 10px;
        }
        #msg-input {
            flex: 1;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 24px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }
        #msg-input:focus { border-color: #667eea; }
        #send-btn {
            background: #667eea;
            color: #fff;
            border: none;
            padding: 12px 24px;
            border-radius: 24px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: background 0.2s;
        }
        #send-btn:hover { background: #5a6fd6; }
        #send-btn:disabled { background: #ccc; cursor: not-allowed; }

        /* ─── Welcome ─── */
        .welcome {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }
        .welcome h2 {
            font-size: 1.8em;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .welcome p { font-size: 1em; line-height: 1.6; }
    </style>

    <div id="sidebar">
        <div id="sidebar-header">
            <h2>💬 Chats</h2>
            <button id="new-chat-btn" onclick="newChat()">+ New</button>
        </div>
        <div id="session-list"></div>
        <div id="store-toggle">
            <label>Store</label>
            <select id="store-select" onchange="onStoreChange()">
                <option value="depo" selected>🏠 Depo.lv (default)</option>
                <option value="darel">🔧 Darel.lv</option>
            </select>
        </div>
    </div>

    <div id="main">
        <div id="header">
            <h1>🛒 Hephix</h1>
            <span id="store-badge" class="badge-depo">DEPO.LV</span>
        </div>
        <div id="messages">
            <div class="welcome">
                <h2>Welcome to Hephix</h2>
                <p>Your AI shopping assistant for Latvian stores.<br>
                   Try: "Find me power drills" or "What screws do you have?"</p>
            </div>
        </div>
        <div id="typing">Thinking...</div>
        <div id="input-area">
            <input type="text" id="msg-input" placeholder="Ask about products..." autocomplete="off" autofocus>
            <button id="send-btn" onclick="send()">Send</button>
        </div>
    </div>

    <script>
        const messagesEl = document.getElementById('messages');
        const inputEl = document.getElementById('msg-input');
        const sendBtn = document.getElementById('send-btn');
        const typingEl = document.getElementById('typing');
        const sessionListEl = document.getElementById('session-list');
        const storeSelect = document.getElementById('store-select');
        const storeBadge = document.getElementById('store-badge');

        let sid = localStorage.getItem('hephix_sid') || '';
        let store = localStorage.getItem('hephix_store') || 'depo';
        let isWelcome = true;

        storeSelect.value = store;
        updateBadge();

        function updateBadge() {
            if (store === 'darel') {
                storeBadge.textContent = 'DAREL.LV';
                storeBadge.className = 'badge-darel';
            } else {
                storeBadge.textContent = 'DEPO.LV';
                storeBadge.className = 'badge-depo';
            }
        }

        function onStoreChange() {
            store = storeSelect.value;
            localStorage.setItem('hephix_store', store);
            updateBadge();
            // Start a new chat when switching stores
            newChat();
        }

        function chatEndpoint() {
            return store === 'darel' ? '/chat/darel' : '/chat';
        }

        function addMessage(role, text) {
            if (isWelcome) {
                messagesEl.innerHTML = '';
                isWelcome = false;
            }
            const div = document.createElement('div');
            div.className = 'msg ' + role;
            div.textContent = text;
            messagesEl.appendChild(div);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        async function send() {
            const text = inputEl.value.trim();
            if (!text) return;

            inputEl.value = '';
            addMessage('user', text);
            sendBtn.disabled = true;
            typingEl.style.display = 'block';
            messagesEl.scrollTop = messagesEl.scrollHeight;

            try {
                const res = await fetch(chatEndpoint(), {
                    method: 'POST',
                    headers: { 'content-type': 'application/json' },
                    body: JSON.stringify({ session_id: sid || undefined, message: text }),
                });
                const data = await res.json();
                sid = data.session_id;
                localStorage.setItem('hephix_sid', sid);
                addMessage('ai', data.response);
                loadSessions();
            } catch (e) {
                addMessage('system', 'Error: ' + e.message);
            } finally {
                sendBtn.disabled = false;
                typingEl.style.display = 'none';
            }
        }

        function newChat() {
            sid = '';
            localStorage.removeItem('hephix_sid');
            messagesEl.innerHTML =
                '<div class="welcome">' +
                '<h2>Welcome to Hephix</h2>' +
                '<p>Your AI shopping assistant for Latvian stores.<br>' +
                'Try: "Find me power drills" or "What screws do you have?"</p>' +
                '</div>';
            isWelcome = true;
            loadSessions();
        }

        async function loadSessions() {
            try {
                const res = await fetch('/sessions?limit=50');
                const data = await res.json();
                sessionListEl.innerHTML = '';
                data.sessions.forEach(s => {
                    const div = document.createElement('div');
                    const isDarel = s.session_id.startsWith('darel-');
                    const icon = isDarel ? '🔧' : '🏠';
                    div.className = 'session-item' + (s.session_id === sid ? ' active' : '');
                    const ts = new Date(s.updated_at * 1000).toLocaleString();
                    div.innerHTML = icon + ' ' + s.session_id.slice(0, 12) + '...'
                        + '<div class="session-time">' + ts + '</div>';
                    div.onclick = () => loadSession(s.session_id);
                    sessionListEl.appendChild(div);
                });
            } catch (e) {
                console.error('Failed to load sessions:', e);
            }
        }

        async function loadSession(id) {
            try {
                const res = await fetch('/sessions/' + id);
                const data = await res.json();
                sid = data.session_id;
                localStorage.setItem('hephix_sid', sid);

                // Switch store selector to match session
                if (sid.startsWith('darel-')) {
                    store = 'darel';
                } else {
                    store = 'depo';
                }
                storeSelect.value = store;
                localStorage.setItem('hephix_store', store);
                updateBadge();

                messagesEl.innerHTML = '';
                isWelcome = false;

                (data.messages || []).forEach(m => {
                    const type = m.type || 'unknown';
                    if (type === 'system' || type === 'tool') return;

                    let content = '';
                    if (m.data && m.data.content !== undefined) {
                        if (typeof m.data.content === 'string') {
                            content = m.data.content;
                        } else if (Array.isArray(m.data.content)) {
                            content = m.data.content
                                .filter(p => p.type === 'text' && p.text)
                                .map(p => p.text)
                                .join('\\n');
                        } else {
                            content = JSON.stringify(m.data.content);
                        }
                    }

                    if (!content.trim()) return;
                    if (type === 'human') addMessage('user', content);
                    else if (type === 'ai') addMessage('ai', content);
                });

                loadSessions();
            } catch (e) {
                console.error('Failed to load session:', e);
            }
        }

        inputEl.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
            }
        });

        // Boot
        loadSessions();
        if (sid) loadSession(sid);
    </script>
    """


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/mcp/info")
async def mcp_info():
    """Get MCP server information."""
    def _tools_for(runtime):
        if not runtime.tools:
            return []
        return [
            {"name": t.name, "description": getattr(t, "description", "")}
            for t in runtime.tools
        ]

    return {
        "mcp_enabled": True,
        "default_store": "depo",
        "servers": {
            "depo": {
                "status": "running" if DEPO_RUNTIME.tools else "stopped",
                "endpoint": "/chat",
                "tools": _tools_for(DEPO_RUNTIME),
            },
            "darel": {
                "status": "running" if DAREL_RUNTIME.tools else "stopped",
                "endpoint": "/chat/darel",
                "tools": _tools_for(DAREL_RUNTIME),
            },
        },
    }

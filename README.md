# vercel-mcp 🚀

**MCP Server for the Vercel REST API** — Manage projects, deployments, domains, environment variables, and teams from any MCP-compatible client (Claude Desktop, OpenClaw, Cursor, etc.).

> ⚡ Zero dependencies. Just Python 3.7+ and a Vercel API token.

## Features

- **Projects** — List, inspect, manage
- **Deployments** — List, inspect, trigger redeployments
- **Domains** — List, add, verify DNS configuration
- **Environment Variables** — List and set secrets for projects
- **Teams** — List teams and their metadata
- **Secrets** — List account-level secrets
- **Dual-mode** — Run as stdio MCP server or standalone HTTP REST API

### 12 Tools

| Tool | Description |
|------|-------------|
| `list_projects` | List all projects with framework, URLs, metadata |
| `get_project` | Detailed project info including deployments and env count |
| `list_deployments` | List deployments, filter by project/state |
| `get_deployment` | Detailed deployment info with aliases and config |
| `create_deployment` | Trigger a new deployment manually |
| `list_domains` | List domains for a project or account |
| `add_domain` | Add a custom domain to a project |
| `verify_domain` | Check domain verification status and DNS config |
| `list_env_vars` | List environment variables for a project |
| `set_env_var` | Set environment variables on a project |
| `list_teams` | List teams the user belongs to |
| `get_user` | Get authenticated user info |
| `list_secrets` | List account-level secrets |

## Quick Start

```bash
# Set your Vercel API token
export VERCEL_API_TOKEN="your_token_here"

# Run as stdio MCP server (for Claude Desktop, OpenClaw, etc.)
python3 vercel_mcp.py

# Run with debug logging
python3 vercel_mcp.py --debug

# Run as HTTP REST server
python3 vercel_mcp.py --http --port 8080
```

## Register with an MCP Host

### Claude Desktop
```json
{
  "mcpServers": {
    "vercel": {
      "command": "python3",
      "args": ["/path/to/vercel_mcp.py"],
      "env": {
        "VERCEL_API_TOKEN": "your_token_here"
      }
    }
  }
}
```

### OpenClaw
```bash
mcporter config add vercel stdio \
  --command "python3 /path/to/vercel_mcp.py" \
  --env "VERCEL_API_TOKEN=your_token_here"
```

### Cursor
```bash
cursor mcp add vercel --type stdio \
  --command "python3 /path/to/vercel_mcp.py" \
  --env VERCEL_API_TOKEN=your_token_here
```

## HTTP REST API

When running in HTTP mode (`--http`), the server provides:

```
GET  /         — Server health + tool list
GET  /health   — Server health
GET  /tools    — Tool definitions
POST /mcp      — JSON-RPC MCP endpoint
```

```bash
# Check health
curl http://localhost:8080/health

# Call a tool
curl -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"mcp.callTool","params":{"name":"list_projects","arguments":{"limit":5}}}'
```

## How to Get a Vercel API Token

1. Go to [vercel.com/account/tokens](https://vercel.com/account/tokens)
2. Click **Create Token**
3. Give it a name (e.g., "vercel-mcp")
4. Copy the token and set `VERCEL_API_TOKEN`

## Architecture

```
vercel_mcp.py
├── MCP Stdio Transport (stdin/stdout) ← MCP clients
├── HTTP REST Server (--http) ← curl/browsers
├── Vercel API Client (urllib, zero-deps)
│   ├── GET /v9/projects
│   ├── GET /v6/deployments
│   ├── POST /v13/deployments
│   ├── GET /v10/projects/{id}/env
│   └── ...
└── Retry logic (exponential backoff for 429/5xx)
```

## Why vercel-mcp?

No proper MCP server for Vercel existed — only the Next.js MCP adapter. This is a standalone, zero-dependency tool that covers the full Vercel REST API surface: projects, deployments, domains, env vars, secrets, and teams.

## License

MIT — Built by [Kevin](https://github.com/amerilain), autonomous AI agent.

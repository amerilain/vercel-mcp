#!/usr/bin/env python3
"""
vercel-mcp — MCP Server for Vercel REST API

Model Context Protocol server that exposes Vercel platform management as MCP tools.
Zero dependencies beyond Python standard library.

Protocol: JSON-RPC 2.0 over stdio (MCP stdio transport)

Usage:
    # Set Vercel API token (required)
    export VERCEL_API_TOKEN="your_token_here"

    # Run as stdio MCP server
    python3 vercel_mcp.py

    # Run with debug logging
    python3 vercel_mcp.py --debug

    # Run as HTTP REST server (dual-mode)
    python3 vercel_mcp.py --http --port 8080

To register with an MCP host:
    mcporter config add vercel stdio --command "python3 /path/to/vercel_mcp.py"
"""

import json
import sys
import os
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone
import traceback
import time
import random
import http.server

API_BASE = "https://api.vercel.com"
VERSION = "0.1.0"
DEBUG = False
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0


# ─── API Helpers ────────────────────────────────────────────────────────────

def get_token():
    """Get Vercel API token from environment."""
    token = os.environ.get("VERCEL_API_TOKEN") or os.environ.get("VERCEL_TOKEN")
    if not token:
        return None
    return token


def api_get(path, params=None, team_id=None):
    """Make a GET request to Vercel API with retry logic."""
    token = get_token()
    if not token:
        raise RuntimeError("VERCEL_API_TOKEN environment variable not set")

    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    if team_id:
        sep = "&" if params else "?"
        url += f"{sep}teamId={urllib.parse.quote(team_id)}"

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "vercel-mcp/2.0"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            last_error = RuntimeError(f"API error {e.code}: {body[:300]}")
            if e.code in (429, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                if DEBUG:
                    print(f"[DEBUG] Retry {attempt+1}/{MAX_RETRIES} after {delay:.1f}s (HTTP {e.code})",
                          file=sys.stderr)
                time.sleep(delay)
                continue
            raise last_error
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_error = RuntimeError(f"Connection error: {e}")
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            raise last_error
    raise last_error or RuntimeError("Unknown API error")


def api_post(path, data, team_id=None):
    """Make a POST request to Vercel API."""
    token = get_token()
    if not token:
        raise RuntimeError("VERCEL_API_TOKEN environment variable not set")

    url = f"{API_BASE}{path}"
    if team_id:
        url += f"?teamId={urllib.parse.quote(team_id)}"

    body = json.dumps(data).encode("utf-8")
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, data=body, headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "vercel-mcp/2.0"
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                if raw.strip():
                    return json.loads(raw)
                return {}
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            last_error = RuntimeError(f"API error {e.code}: {body[:300]}")
            if e.code in (429, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            raise last_error
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_error = RuntimeError(f"Connection error: {e}")
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            raise last_error
    raise last_error or RuntimeError("Unknown API error")


def api_delete(path, team_id=None, params=None):
    """Make a DELETE request to Vercel API."""
    token = get_token()
    if not token:
        raise RuntimeError("VERCEL_API_TOKEN environment variable not set")

    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    if team_id:
        sep = "&" if (params and url != f"{API_BASE}{path}") else "?"
        url += f"{sep}teamId={urllib.parse.quote(team_id)}"

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, method="DELETE", headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "vercel-mcp/2.0"
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode()
                if raw.strip():
                    return json.loads(raw)
                return {}
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            last_error = RuntimeError(f"API error {e.code}: {body[:300]}")
            if e.code in (429, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            raise last_error
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_error = RuntimeError(f"Connection error: {e}")
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue
            raise last_error
    raise last_error or RuntimeError("Unknown API error")


# ─── MCP Tool Handlers ──────────────────────────────────────────────────────

def handle_list_projects(args):
    """List all Vercel projects."""
    limit = args.get("limit", 20)
    team_id = args.get("teamId")
    data = api_get("/v9/projects", params={"limit": limit}, team_id=team_id)
    projects = data.get("projects", [])
    result = []
    for p in projects:
        result.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "framework": p.get("framework"),
            "updatedAt": p.get("updatedAt"),
            "createdAt": p.get("createdAt"),
            "productionDeployment": p.get("productionDeployment", {}).get("url") if p.get("productionDeployment") else None,
            "targets": list(p.get("targets", {}).keys()) if p.get("targets") else []
        })
    return {"projects": result, "total": data.get("pagination", {}).get("count", len(projects))}


def handle_get_project(args):
    """Get details for a specific project."""
    name_or_id = args.get("idOrName")
    team_id = args.get("teamId")
    if not name_or_id:
        raise ValueError("idOrName is required")
    data = api_get(f"/v9/projects/{urllib.parse.quote(name_or_id)}", team_id=team_id)
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "framework": data.get("framework"),
        "createdAt": data.get("createdAt"),
        "updatedAt": data.get("updatedAt"),
        "productionDeployment": data.get("productionDeployment", {}).get("url") if data.get("productionDeployment") else None,
        "link": data.get("link", {}).get("repo") if data.get("link") else None,
        "targets": list(data.get("targets", {}).keys()) if data.get("targets") else [],
        "latestDeployments": [d.get("url") for d in (data.get("latestDeployments") or [])],
        "env": len(data.get("env") or []),
    }


def handle_list_deployments(args):
    """List deployments for a project or all projects."""
    limit = args.get("limit", 20)
    team_id = args.get("teamId")
    app = args.get("app")
    state = args.get("state")  # BUILDING, ERROR, READY, etc.
    params = {"limit": limit}
    if app:
        params["app"] = app
    if state:
        params["state"] = state
    data = api_get("/v6/deployments", params=params, team_id=team_id)
    deployments = data.get("deployments", [])
    result = []
    for d in deployments:
        result.append({
            "uid": d.get("uid"),
            "name": d.get("name"),
            "url": d.get("url"),
            "state": d.get("state"),
            "createdAt": d.get("createdAt"),
            "buildingAt": d.get("buildingAt"),
            "readyAt": d.get("readyAt"),
            "meta": d.get("meta", {}),
        })
    return {"deployments": result, "total": data.get("pagination", {}).get("count", len(deployments))}


def handle_get_deployment(args):
    """Get details for a specific deployment."""
    dep_id = args.get("id")
    team_id = args.get("teamId")
    if not dep_id:
        raise ValueError("id is required")
    data = api_get(f"/v13/deployments/{urllib.parse.quote(dep_id)}", team_id=team_id)
    return {
        "uid": data.get("uid"),
        "name": data.get("name"),
        "url": data.get("url"),
        "state": data.get("state"),
        "readyState": data.get("readyState"),
        "createdAt": data.get("createdAt"),
        "buildingAt": data.get("buildingAt"),
        "readyAt": data.get("readyAt"),
        "inspectorUrl": data.get("inspectorUrl"),
        "target": data.get("target"),
        "alias": data.get("alias", []),
        "meta": data.get("meta", {}),
        "functions": list(data.get("functions", {}).keys()) if data.get("functions") else None,
    }


def handle_create_deployment(args):
    """Create a new deployment (rerun or manual)."""
    name = args.get("name")
    team_id = args.get("teamId")
    deploy_to_prod = args.get("deployToProduction", False)
    force_new = args.get("forceNew", False)
    if not name:
        raise ValueError("name is required")
    
    payload = {"name": name, "deployToProduction": deploy_to_prod, "forceNew": force_new}
    data = api_post(f"/v13/deployments", data=payload, team_id=team_id)
    return {
        "uid": data.get("uid"),
        "name": data.get("name"),
        "url": data.get("url"),
        "state": data.get("state"),
        "createdAt": data.get("createdAt"),
        "target": data.get("target"),
        "inspectorUrl": f"https://vercel.com/{data.get('inspectorUrl', '')}",
    }


def handle_list_domains(args):
    """List all domains for a project or account."""
    limit = args.get("limit", 20)
    team_id = args.get("teamId")
    project = args.get("project")
    if project:
        data = api_get(f"/v9/projects/{urllib.parse.quote(project)}/domains",
                       params={"limit": limit}, team_id=team_id)
    else:
        data = api_get("/v5/domains", params={"limit": limit}, team_id=team_id)
    
    items = data.get("domains", data.get("domains", []))
    # Vercel returns domains in different structures
    if isinstance(items, list) and items and isinstance(items[0], dict):
        result = []
        for d in items:
            result.append({
                "name": d.get("name") or d.get("domain"),
                "verified": d.get("verified"),
                "createdAt": d.get("createdAt") or d.get("created"),
                "nameservers": d.get("nameservers", []),
            })
        return {"domains": result, "total": data.get("pagination", {}).get("count", len(result))}
    return {"domains": items, "total": len(items) if isinstance(items, list) else 0}


def handle_add_domain(args):
    """Add a domain to a project."""
    project = args.get("project")
    domain = args.get("domain")
    team_id = args.get("teamId")
    if not project or not domain:
        raise ValueError("project and domain are required")
    payload = {"name": domain}
    data = api_post(f"/v10/projects/{urllib.parse.quote(project)}/domains",
                    data=payload, team_id=team_id)
    return {
        "name": data.get("name") or domain,
        "verified": data.get("verified"),
        "verification": data.get("verification", []),
    }


def handle_verify_domain(args):
    """Check domain verification status."""
    domain = args.get("domain")
    team_id = args.get("teamId")
    if not domain:
        raise ValueError("domain is required")
    data = api_get(f"/v4/domains/{urllib.parse.quote(domain)}/verify", team_id=team_id)
    return {
        "name": data.get("name") or domain,
        "verified": data.get("verified"),
        "verification": data.get("verification", []),
    }


def handle_list_env_vars(args):
    """List environment variables for a project."""
    project = args.get("project")
    team_id = args.get("teamId")
    if not project:
        raise ValueError("project is required")
    data = api_get(f"/v10/projects/{urllib.parse.quote(project)}/env", team_id=team_id)
    envs = data.get("envs", data.get("env", []))
    result = []
    for e in envs:
        result.append({
            "id": e.get("id"),
            "key": e.get("key"),
            "type": e.get("type"),
            "target": e.get("target", []),
            "updatedAt": e.get("updatedAt"),
            "createdAt": e.get("createdAt"),
        })
    return {"environmentVariables": result, "total": len(result)}


def handle_set_env_var(args):
    """Create or update an environment variable for a project."""
    project = args.get("project")
    key = args.get("key")
    value = args.get("value")
    team_id = args.get("teamId")
    target = args.get("target", ["production", "preview", "development"])
    env_type = args.get("type", "encrypted")
    
    if not project or not key or value is None:
        raise ValueError("project, key, and value are required")
    
    payload = {
        "key": key,
        "value": value,
        "target": target if isinstance(target, list) else [target],
        "type": env_type,
    }
    data = api_post(f"/v10/projects/{urllib.parse.quote(project)}/env",
                    data=payload, team_id=team_id)
    return {
        "id": data.get("id"),
        "key": data.get("key", key),
        "target": data.get("target", target),
    }


def handle_list_teams(args):
    """List all teams the user belongs to."""
    data = api_get("/v2/teams", params={"limit": args.get("limit", 20)})
    teams = data.get("teams", [])
    result = []
    for t in teams:
        result.append({
            "id": t.get("id"),
            "slug": t.get("slug"),
            "name": t.get("name"),
            "createdAt": t.get("createdAt"),
            "members": t.get("members", {}).get("count", 0) if t.get("members") else 0,
        })
    return {"teams": result, "total": len(result)}


def handle_get_user(args):
    """Get authenticated user info."""
    data = api_get("/v2/user")
    user = data.get("user", data)
    return {
        "id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "username": user.get("username"),
        "createdAt": user.get("createdAt"),
        "avatar": user.get("avatar"),
    }


def handle_get_secrets(args):
    """List all secrets for the account."""
    limit = args.get("limit", 20)
    team_id = args.get("teamId")
    data = api_get("/v3/secrets", params={"limit": limit}, team_id=team_id)
    secrets = data.get("secrets", [])
    result = []
    for s in secrets:
        result.append({
            "name": s.get("name"),
            "createdAt": s.get("createdAt"),
            "updatedAt": s.get("updatedAt"),
        })
    return {"secrets": result, "total": len(result)}


# ─── Tool Registry ──────────────────────────────────────────────────────────

TOOLS = {
    "list_projects": {
        "handler": handle_list_projects,
        "description": "List all Vercel projects with their framework, deployment URLs, and metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of projects to return (default 20)"},
                "teamId": {"type": "string", "description": "Team ID for team-scoped operations"}
            }
        }
    },
    "get_project": {
        "handler": handle_get_project,
        "description": "Get detailed information about a specific Vercel project including deployments and env vars count.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "idOrName": {"type": "string", "description": "Project ID or name"},
                "teamId": {"type": "string", "description": "Team ID for team-scoped operations"}
            },
            "required": ["idOrName"]
        }
    },
    "list_deployments": {
        "handler": handle_list_deployments,
        "description": "List deployments across projects or for a specific project. Filter by state (BUILDING, ERROR, READY).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum deployments to return"},
                "app": {"type": "string", "description": "Filter by project name"},
                "state": {"type": "string", "description": "Filter by state: BUILDING, ERROR, READY, QUEUED, CANCELED"},
                "teamId": {"type": "string", "description": "Team ID"}
            }
        }
    },
    "get_deployment": {
        "handler": handle_get_deployment,
        "description": "Get detailed information about a specific deployment including state, aliases, and configuration.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Deployment ID or URL"},
                "teamId": {"type": "string", "description": "Team ID"}
            },
            "required": ["id"]
        }
    },
    "create_deployment": {
        "handler": handle_create_deployment,
        "description": "Trigger a new deployment manually. Use to redeploy the latest commit or force a fresh build.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project name to deploy"},
                "deployToProduction": {"type": "boolean", "description": "Deploy to production immediately"},
                "forceNew": {"type": "boolean", "description": "Force new deployment even if no changes"},
                "teamId": {"type": "string", "description": "Team ID"}
            },
            "required": ["name"]
        }
    },
    "list_domains": {
        "handler": handle_list_domains,
        "description": "List all domains for a project or across the account.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum domains to return"},
                "project": {"type": "string", "description": "Filter by project name/ID to see its domains"},
                "teamId": {"type": "string", "description": "Team ID"}
            }
        }
    },
    "add_domain": {
        "handler": handle_add_domain,
        "description": "Add a custom domain to a Vercel project. Returns verification requirements if domain isn't pre-verified.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name or ID"},
                "domain": {"type": "string", "description": "Domain name to add (e.g., example.com)"},
                "teamId": {"type": "string", "description": "Team ID"}
            },
            "required": ["project", "domain"]
        }
    },
    "verify_domain": {
        "handler": handle_verify_domain,
        "description": "Check the verification status of a domain and get DNS configuration instructions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Domain name to verify"},
                "teamId": {"type": "string", "description": "Team ID"}
            },
            "required": ["domain"]
        }
    },
    "list_env_vars": {
        "handler": handle_list_env_vars,
        "description": "List all environment variables for a project (values redacted, shows key names only).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name or ID"},
                "teamId": {"type": "string", "description": "Team ID"}
            },
            "required": ["project"]
        }
    },
    "set_env_var": {
        "handler": handle_set_env_var,
        "description": "Set an environment variable for a project. Target can be production, preview, and/or development.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name or ID"},
                "key": {"type": "string", "description": "Environment variable name"},
                "value": {"type": "string", "description": "Environment variable value"},
                "target": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Target environments: production, preview, development"
                },
                "type": {
                    "type": "string",
                    "description": "Type: encrypted, plain, secret (default encrypted)",
                    "default": "encrypted"
                },
                "teamId": {"type": "string", "description": "Team ID"}
            },
            "required": ["project", "key", "value"]
        }
    },
    "list_teams": {
        "handler": handle_list_teams,
        "description": "List all teams the authenticated user belongs to.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum teams to return"}
            }
        }
    },
    "get_user": {
        "handler": handle_get_user,
        "description": "Get information about the authenticated Vercel user.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    "list_secrets": {
        "handler": handle_get_secrets,
        "description": "List all secrets for the account or team.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum secrets to return"},
                "teamId": {"type": "string", "description": "Team ID"}
            }
        }
    },
}


# ─── MCP Protocol ───────────────────────────────────────────────────────────

def handle_list_tools():
    """Return tool definitions for MCP."""
    tools = []
    for name, info in TOOLS.items():
        tools.append({
            "name": name,
            "description": info["description"],
            "inputSchema": info.get("inputSchema", {"type": "object", "properties": {}}),
        })
    return tools


def handle_call_tool(name, args):
    """Execute a tool and return result."""
    tool = TOOLS.get(name)
    if not tool:
        raise ValueError(f"Unknown tool: {name}")
    result = tool["handler"](args)
    return [{"type": "text", "text": json.dumps(result, indent=2)}]


def process_mcp_message(msg):
    """Process a single JSON-RPC 2.0 MCP message."""
    msg_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params", {})

    if method == "mcp.listTools":
        tools = handle_list_tools()
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}}
    elif method == "mcp.callTool":
        name = params.get("name")
        args = params.get("arguments", {})
        try:
            content = handle_call_tool(name, args)
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"content": content}}
        except Exception as e:
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32000, "message": str(e),
                          "data": traceback.format_exc() if DEBUG else None}
            }
    elif method == "mcp.ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    else:
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


# ─── Transport: STDIO MCP ──────────────────────────────────────────────────

def run_stdio():
    """Run as stdio MCP server (read JSON-RPC from stdin, write to stdout)."""
    if DEBUG:
        print("[DEBUG] vercel-mcp starting in stdio mode", file=sys.stderr)

    # Send initialize response
    init_msg = sys.stdin.readline()
    if init_msg.strip():
        try:
            init = json.loads(init_msg)
            if init.get("method") == "mcp.initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": init.get("id"),
                    "result": {
                        "protocolVersion": "2024-05-15",
                        "serverInfo": {"name": "vercel-mcp", "version": VERSION},
                        "capabilities": {"tools": {}}
                    }
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            pass

    # Main loop
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            resp = process_mcp_message(msg)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError as e:
            err = {"jsonrpc": "2.0", "error": {"code": -32700, "message": f"Parse error: {e}"}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err = {"jsonrpc": "2.0", "error": {"code": -32603, "message": f"Internal error: {e}"}}
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()


# ─── Transport: HTTP REST ───────────────────────────────────────────────────

class MCPHTTPHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for dual-mode REST API."""

    def do_GET(self):
        if self.path == "/" or self.path == "/health":
            self._json_response({"status": "ok", "version": VERSION, "name": "vercel-mcp",
                                 "tools": list(TOOLS.keys())})
        elif self.path == "/tools":
            tools = handle_list_tools()
            self._json_response({"tools": tools})
        else:
            self._json_response({"error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/mcp":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                msg = json.loads(body)
                resp = process_mcp_message(msg)
                self._json_response(resp)
            except json.JSONDecodeError as e:
                self._json_response({"error": f"parse error: {e}"}, 400)
        else:
            self._json_response({"error": "not found"}, 404)

    def _json_response(self, data, status=200):
        body = json.dumps(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, fmt, *args):
        if DEBUG:
            super().log_message(fmt, *args)


def run_http(port=8080):
    """Run as HTTP REST server."""
    if DEBUG:
        print(f"[DEBUG] vercel-mcp starting HTTP server on port {port}", file=sys.stderr)
    server = http.server.HTTPServer(("0.0.0.0", port), MCPHTTPHandler)
    print(f"vercel-mcp HTTP server listening on http://0.0.0.0:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        server.server_close()


# ─── Entry Point ────────────────────────────────────────────────────────────

def main():
    global DEBUG
    args = sys.argv[1:]

    if "--debug" in args:
        DEBUG = True
        args.remove("--debug")

    if "--http" in args or "--serve" in args:
        port = 8080
        for i, a in enumerate(args):
            if a == "--port" and i + 1 < len(args):
                try:
                    port = int(args[i + 1])
                except ValueError:
                    pass
        run_http(port)
    else:
        run_stdio()


if __name__ == "__main__":
    main()

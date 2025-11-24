#!/usr/bin/env python3
"""
XUI Manager - Backup Update Server
Отдельный сервер для управления обновлениями агента
Работает на отдельном порту и всегда доступен
"""

import os
import sys
import json
import subprocess
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import JSONResponse
import secrets
import uvicorn

# Configuration
UPDATE_SERVER_PORT = 8889
VERSION_FILE = "/opt/xui-manager/app/version.py"
UPDATE_SCRIPT = "/opt/xui-manager/update.sh"
GITHUB_API_URL = "https://api.github.com/repos/khiziresmars/xmanager/releases/latest"

# Get credentials from environment or use defaults
ADMIN_USERNAME = os.getenv("XUI_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("XUI_ADMIN_PASS", "admin")

app = FastAPI(
    title="XUI Manager Update Server",
    description="Backup server for managing agent updates",
    version="1.0.0"
)

security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify basic auth credentials"""
    correct_username = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

def get_local_version():
    """Get current version from local file"""
    try:
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, 'r') as f:
                content = f.read()
                import re
                match = re.search(r'CURRENT_VERSION\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
        return None
    except Exception as e:
        return None

@app.get("/")
async def root():
    """Root endpoint - server status"""
    return {
        "service": "XUI Manager Update Server",
        "status": "running",
        "port": UPDATE_SERVER_PORT,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/status")
async def get_status(username: str = Depends(verify_credentials)):
    """Get system status"""
    local_version = get_local_version()
    agent_installed = local_version is not None

    # Check if main agent is running
    agent_running = False
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "xui-manager"],
            capture_output=True, text=True
        )
        agent_running = result.stdout.strip() == "active"
    except:
        pass

    return {
        "agent_installed": agent_installed,
        "agent_running": agent_running,
        "local_version": local_version,
        "update_server_version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/version")
async def get_version(username: str = Depends(verify_credentials)):
    """Get local version"""
    version = get_local_version()
    if version:
        return {"version": version, "installed": True}
    else:
        return {"version": None, "installed": False, "error": "Agent not installed or version file not found"}

@app.get("/api/check-update")
async def check_update(username: str = Depends(verify_credentials)):
    """Check for available updates from GitHub"""
    local_version = get_local_version()

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(GITHUB_API_URL) as response:
                if response.status != 200:
                    raise HTTPException(status_code=502, detail="GitHub API error")

                data = await response.json()
                latest_version = data.get("tag_name", "").lstrip('v')

                update_available = False
                if local_version and latest_version:
                    # Simple version comparison
                    local_parts = [int(x) for x in local_version.split('.')]
                    latest_parts = [int(x) for x in latest_version.split('.')]
                    update_available = latest_parts > local_parts

                return {
                    "local_version": local_version,
                    "latest_version": latest_version,
                    "update_available": update_available,
                    "release_url": data.get("html_url"),
                    "published_at": data.get("published_at")
                }
    except aiohttp.ClientError as e:
        raise HTTPException(status_code=502, detail=f"Network error: {str(e)}")

@app.post("/api/update")
async def perform_update(username: str = Depends(verify_credentials)):
    """Execute update script"""
    if not os.path.exists(UPDATE_SCRIPT):
        raise HTTPException(status_code=404, detail="Update script not found")

    try:
        # Run update script
        result = subprocess.run(
            ["bash", UPDATE_SCRIPT],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes timeout
            cwd="/opt/xui-manager"
        )

        success = result.returncode == 0
        new_version = get_local_version() if success else None

        return {
            "success": success,
            "new_version": new_version,
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Update timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/restart-agent")
async def restart_agent(username: str = Depends(verify_credentials)):
    """Restart the main XUI Manager agent"""
    try:
        result = subprocess.run(
            ["systemctl", "restart", "xui-manager"],
            capture_output=True,
            text=True,
            timeout=30
        )

        success = result.returncode == 0

        # Check if agent is running after restart
        check = subprocess.run(
            ["systemctl", "is-active", "xui-manager"],
            capture_output=True, text=True
        )
        is_running = check.stdout.strip() == "active"

        return {
            "success": success,
            "is_running": is_running,
            "message": "Agent restarted successfully" if success else "Failed to restart agent",
            "stderr": result.stderr if result.stderr else None
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Restart timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stop-agent")
async def stop_agent(username: str = Depends(verify_credentials)):
    """Stop the main XUI Manager agent"""
    try:
        result = subprocess.run(
            ["systemctl", "stop", "xui-manager"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "success": result.returncode == 0,
            "message": "Agent stopped" if result.returncode == 0 else "Failed to stop agent"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/start-agent")
async def start_agent(username: str = Depends(verify_credentials)):
    """Start the main XUI Manager agent"""
    try:
        result = subprocess.run(
            ["systemctl", "start", "xui-manager"],
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "success": result.returncode == 0,
            "message": "Agent started" if result.returncode == 0 else "Failed to start agent"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agent-logs")
async def get_agent_logs(
    lines: int = Query(50, ge=1, le=500),
    username: str = Depends(verify_credentials)
):
    """Get recent agent logs"""
    try:
        result = subprocess.run(
            ["journalctl", "-u", "xui-manager", "-n", str(lines), "--no-pager"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return {
            "logs": result.stdout,
            "lines": lines
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def main():
    """Run the update server"""
    print(f"Starting XUI Manager Update Server on port {UPDATE_SERVER_PORT}")
    print(f"Username: {ADMIN_USERNAME}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=UPDATE_SERVER_PORT,
        log_level="info"
    )

if __name__ == "__main__":
    main()

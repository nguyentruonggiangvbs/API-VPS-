#!/usr/bin/env python3
"""
API-VPS Deploy Agent

Runs on VPS and executes safe deployment actions triggered by webhook.
"""

import os
import subprocess
from fastapi import FastAPI, Request

app = FastAPI(title="API VPS Deploy Agent")

SECRET = os.getenv("DEPLOY_SECRET", "change-me")
PROJECT = os.getenv("PROJECT_PATH", "/opt/api-vps")


def run(command):
    return subprocess.getoutput(command)


@app.get("/health")
def health():
    return {"status": "running", "agent": "deploy-agent"}


@app.post("/deploy")
async def deploy(request: Request):
    token = request.headers.get("x-deploy-secret")

    if token != SECRET:
        return {"error": "unauthorized"}

    result = []

    result.append(run(f"cd {PROJECT} && git pull"))
    result.append(run(f"cd {PROJECT} && docker compose up -d --build"))

    return {
        "status": "completed",
        "logs": result
    }

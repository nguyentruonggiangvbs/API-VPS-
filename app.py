from fastapi import FastAPI, Header, HTTPException
import subprocess
import shutil
import os

app = FastAPI(title="API VPS Control Center")

API_KEY = os.getenv("API_KEY", "change-me")


def auth(x_api_key: str | None):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/")
def home():
    return {"status": "running", "service": "api-vps"}


@app.get("/system/info")
def system_info(x_api_key: str | None = Header(default=None)):
    auth(x_api_key)
    disk = shutil.disk_usage("/")
    return {
        "disk_total": disk.total,
        "disk_used": disk.used,
        "disk_free": disk.free,
        "cpu": subprocess.getoutput("top -bn1 | grep Cpu"),
        "memory": subprocess.getoutput("free -m"),
    }


@app.get("/docker/list")
def docker_list(x_api_key: str | None = Header(default=None)):
    auth(x_api_key)
    return {"containers": subprocess.getoutput("docker ps")}


@app.post("/docker/restart/{container}")
def docker_restart(container: str, x_api_key: str | None = Header(default=None)):
    auth(x_api_key)
    return {"result": subprocess.getoutput(f"docker restart {container}")}


@app.get("/docker/logs/{container}")
def docker_logs(container: str, x_api_key: str | None = Header(default=None)):
    auth(x_api_key)
    return {"logs": subprocess.getoutput(f"docker logs --tail 200 {container}")}

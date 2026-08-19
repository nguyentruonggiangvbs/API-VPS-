from fastapi import FastAPI
import subprocess

app = FastAPI(title="API VPS Controller")

@app.get("/")
def home():
    return {
        "status": "running",
        "service": "api-vps"
    }

@app.get("/status")
def status():
    return {
        "docker": subprocess.getoutput("docker ps")
    }

@app.post("/restart/{container}")
def restart(container:str):
    return {
        "result": subprocess.getoutput(
            f"docker restart {container}"
        )
    }

@app.get("/logs/{container}")
def logs(container:str):
    return {
        "logs": subprocess.getoutput(
            f"docker logs --tail 100 {container}"
        )
    }

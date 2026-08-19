from fastapi import APIRouter, HTTPException
from . import file_manager, terminal, docker_manager

router = APIRouter(prefix="/control")


@router.get("/files")
def list_files(path: str = "/opt"):
    return file_manager.list_files(path)


@router.delete("/files")
def delete_file(path: str):
    return file_manager.delete_path(path)


@router.post("/terminal")
def execute_terminal(command: str):
    return terminal.execute(command)


@router.get("/docker")
def docker_list():
    return docker_manager.list_containers()


@router.post("/docker/{action}/{container}")
def docker_action(action: str, container: str):
    actions = {
        "start": docker_manager.start_container,
        "stop": docker_manager.stop_container,
        "restart": docker_manager.restart_container,
        "logs": docker_manager.logs_container,
    }
    if action not in actions:
        raise HTTPException(status_code=400, detail="Invalid action")
    return actions[action](container)

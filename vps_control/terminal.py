import subprocess

ALLOWED_COMMANDS = {
    'docker ps',
    'docker stats --no-stream',
    'df -h',
    'free -h'
}


def execute(command):
    if command not in ALLOWED_COMMANDS:
        raise PermissionError('Command blocked')

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True
    )

    return {
        'stdout': result.stdout,
        'stderr': result.stderr
    }

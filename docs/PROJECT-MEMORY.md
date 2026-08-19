# API-VPS Project Memory

## Purpose

This repository is the central source of truth for VPS management.

## Current status

Completed:

- FastAPI backend
- Docker based deployment
- Web dashboard
- CPU/RAM/Disk monitoring
- Docker container listing
- Dashboard served from API

## VPS information

Project:

```
/opt/api-vps
```

Service:

```
api-vps
```

Port:

```
9000
```

## Development rules

- GitHub is the main source.
- Avoid editing production VPS directly unless testing.
- Every feature should be committed to GitHub.
- Deployment should happen through controlled updates.

## Planned features

### File Manager

- Browse directories
- Upload files
- Download files
- Delete files

### Docker Manager

- Start
- Stop
- Restart
- Logs

### Deployment Agent

Goal:

```
GitHub Push
    |
    v
Automatic VPS Update
    |
    v
Docker Rebuild
```

### Monitoring

- CPU chart
- RAM chart
- Disk chart
- Network chart

## Notes for future sessions

Always read this document before changing architecture.

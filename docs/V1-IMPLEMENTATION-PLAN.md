# API-VPS Control Center v1 Implementation Plan

## Goal
Build a private VPS management panel similar to a lightweight CloudPanel/Portainer.

## Modules

### 1. Backend API
- [x] FastAPI base
- [x] System information
- [x] Docker status
- [x] Initial dashboard API
- [ ] File Manager API integration
- [ ] Terminal API integration
- [ ] Backup API

### 2. Dashboard
- [x] Basic dashboard
- [ ] Full sidebar navigation
- [ ] Docker management UI
- [ ] File Manager UI
- [ ] Terminal UI
- [ ] Logs UI

### 3. Deployment
- [x] GitHub documentation
- [x] Deploy Agent architecture
- [x] Nginx architecture
- [ ] Production webhook deployment
- [ ] Health check and rollback

### 4. Security
- [ ] Authentication
- [ ] API key management
- [ ] Audit logs
- [ ] HTTPS deployment

### 5. Operations
- [ ] Backup manager
- [ ] Restore manager
- [ ] Monitoring charts
- [ ] Alert system

## Deployment principle

GitHub is the source of truth.

Flow:

GitHub -> CI/CD -> VPS Agent -> Docker -> Running Services

## VPS target

Project path:

/opt/api-vps

Main service:

API port 9000

Dashboard:

/dashboard/

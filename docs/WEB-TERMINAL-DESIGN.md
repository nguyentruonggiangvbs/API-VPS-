# API-VPS Web Terminal Design

## Goal
Browser terminal for VPS administration.

## Features
- Execute approved commands
- Stream output
- Command history
- Permission control
- Audit logs

## Planned API

POST /terminal/execute
GET /terminal/history
GET /terminal/logs

## Security
- Disabled by default
- API key required
- Command whitelist
- User audit trail

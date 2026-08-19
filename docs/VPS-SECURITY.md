# VPS Security Plan

## Deploy Agent

- Agent port: 9100
- Must use DEPLOY_SECRET
- Do not expose without reverse proxy/authentication

## Docker

Recommended:

```
/var/run/docker.sock:/var/run/docker.sock
```

Only trusted services should access Docker socket.

## Production Checklist

- Use HTTPS
- Use firewall rules
- Change default secrets
- Backup configuration
- Limit API access by IP/API key

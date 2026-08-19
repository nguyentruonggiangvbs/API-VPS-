# API-VPS File Manager Design

## Goal
Web based VPS file management.

## Features
- Browse folders
- Read text files
- Upload files
- Create folders
- Rename
- Delete
- Download

## API planned

GET /files/list?path=/opt/api-vps
GET /files/read?path=
POST /files/upload
POST /files/create-folder
DELETE /files/delete

## Security
- Require API key
- Restrict allowed root folders
- Audit every action

## Dashboard menu

Dashboard
Docker
Files
Terminal
Logs
Backup
Settings

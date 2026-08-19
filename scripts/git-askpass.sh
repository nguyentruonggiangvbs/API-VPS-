#!/bin/sh
case "$1" in
  *Username*) printf '%s\n' "${GIT_HTTP_USERNAME:-x-access-token}" ;;
  *Password*) printf '%s\n' "${GIT_HTTP_TOKEN:-}" ;;
  *) printf '\n' ;;
esac

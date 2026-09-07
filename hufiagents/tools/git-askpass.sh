#!/bin/sh
# GIT_ASKPASS helper for GitTool.push (docs/DECISIONS.md ADR-011).
# Contains no secret and is safe to check in: the real credential is read
# only from HUFI_GIT_PUSH_TOKEN, an environment variable set for the single
# git-push subprocess invocation only. git calls this script once for the
# username prompt and once for the password prompt, passing the prompt text
# as $1.
case "$1" in
    Username*|username*)
        printf '%s\n' "x-access-token"
        ;;
    Password*|password*)
        printf '%s\n' "$HUFI_GIT_PUSH_TOKEN"
        ;;
    *) exit 1 ;;
esac

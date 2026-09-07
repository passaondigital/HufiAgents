"""Bubblewrap boundary for untrusted project commands.

The project checkout is the only writable host mount.  This module deliberately
does not offer a permissive fallback: executing a project script without this
boundary is a credential escape.
"""

import os
from pathlib import Path

BWRAP = "/usr/bin/bwrap"
PROJECT_EXECUTABLES = {
    "/usr/bin/npm": "/usr/bin/npm",
    "/usr/bin/node": "/usr/bin/node",
    "/usr/bin/python3": "/usr/bin/python3",
    "/usr/bin/pytest": "/usr/bin/pytest",
    "/bin/sh": "/usr/bin/dash",
    "/bin/echo": "/usr/bin/echo",
}


def available() -> bool:
    return os.path.isfile(BWRAP) and os.access(BWRAP, os.X_OK)


def project_argv(argv: list[str], workspace: Path) -> list[str]:
    """Return a closed, networkless bwrap invocation for a project command."""
    if not available():
        raise PermissionError("project code execution requires available Bubblewrap sandbox")
    root = workspace.resolve()
    if root.is_symlink():
        raise PermissionError("workspace root cannot be a symlink")
    executable = PROJECT_EXECUTABLES.get(argv[0])
    if executable is None:
        raise PermissionError("project command is not permitted in Bubblewrap sandbox")
    # Bind only the declared runtime plus shared libraries read-only.  In
    # particular there is no /usr/bin directory mount: sudo, systemctl, docker
    # and arbitrary host executables cannot be started from project code.
    return [
        BWRAP,
        "--die-with-parent",
        "--unshare-user",
        "--uid",
        "0",
        "--gid",
        "0",
        "--unshare-pid",
        "--unshare-net",
        "--unshare-ipc",
        "--unshare-uts",
        "--clearenv",
        "--setenv",
        "PATH",
        "/usr/bin:/bin",
        "--setenv",
        "HOME",
        "/workspace",
        "--setenv",
        "TMPDIR",
        "/tmp",
        "--setenv",
        "LANG",
        "C.UTF-8",
        "--dir",
        "/usr",
        "--dir",
        "/usr/bin",
        "--dir",
        "/bin",
        *([] if argv[0] == "/usr/bin/npm" else ["--ro-bind", executable, argv[0]]),
        "--ro-bind",
        "/usr/bin/env",
        "/usr/bin/env",
        "--ro-bind",
        "/usr/bin/node",
        "/usr/bin/node",
        "--ro-bind",
        "/usr/bin/dash",
        "/usr/bin/sh",
        "--ro-bind",
        "/usr/lib",
        "/usr/lib",
        *(
            [
                "--symlink",
                "../lib/node_modules/npm/bin/npm-cli.js",
                "/usr/bin/npm",
            ]
            if argv[0] == "/usr/bin/npm"
            else []
        ),
        "--ro-bind",
        "/lib",
        "/lib",
        "--ro-bind",
        "/lib64",
        "/lib64",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--tmpfs",
        "/tmp",
        "--bind",
        str(root),
        "/workspace",
        "--chdir",
        "/workspace",
        "--",
        *argv,
    ]


def credential_argv(argv: list[str], workspace: Path) -> list[str]:
    """Put trusted credentialed Git/GitHub execution in a killable PID tree.

    This is not the untrusted-code sandbox.  It preserves the explicitly
    allowlisted HTTPS/loopback transport while bwrap's parent-death handling
    and PID namespace guarantee that descendants are killed with its init.
    """
    if not available():
        raise PermissionError("credential execution requires available Bubblewrap containment")
    root = workspace.resolve()
    return [
        BWRAP,
        "--die-with-parent",
        "--unshare-user",
        "--uid",
        "0",
        "--gid",
        "0",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--ro-bind",
        "/",
        "/",
        "--bind",
        str(root),
        str(root),
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--chdir",
        str(root),
        "--",
        *argv,
    ]

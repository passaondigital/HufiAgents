"""Conservative validation for repositories used by the privileged Git executor."""

import configparser
import re
from pathlib import Path
from urllib.parse import urlsplit


def validate_remote(value):
    # No URL credentials, remote helpers, scp syntax, ambiguous escapes or redirects.
    if not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise PermissionError("unsafe configured Git remote")
    if Path(value).is_absolute() and not value.startswith("//"):
        return "file"  # Operator-configured local fixtures; never receive the token.
    try:
        url = urlsplit(value)
        port = url.port
        valid = (
            url.scheme in {"https", "http"}
            and url.hostname
            and url.username is None
            and url.password is None
            and not url.query
            and not url.fragment
            and not any(c in value for c in "\\%")
            and url.path.startswith("/")
            and all(part not in {".", ".."} for part in url.path.split("/"))
            and (url.scheme == "https" or url.hostname in {"127.0.0.1", "::1"})
            and (port is None or port > 0)
        )
    except ValueError:
        valid = False
    if not valid:
        raise PermissionError("unsafe configured Git remote")
    return url.scheme


def validate_metadata(root):
    metadata = root / ".git"
    if metadata.is_symlink() or not metadata.is_dir():
        raise PermissionError("external Git directory forbidden")
    for entry in metadata.rglob("*"):
        if entry.is_symlink() or (entry.is_file() and entry.stat().st_nlink > 1):
            raise PermissionError("Git metadata links forbidden")
    config = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        config.read_string((metadata / "config").read_text())
        if config.defaults():
            raise ValueError
        for section in config.sections():
            if section == "core":
                allowed = {
                    "repositoryformatversion",
                    "filemode",
                    "bare",
                    "logallrefupdates",
                    "ignorecase",
                    "precomposeunicode",
                }
                if config.get(section, "bare", fallback="false") != "false":
                    raise ValueError
                if config.get(section, "repositoryformatversion", fallback="0") != "0":
                    raise ValueError
            elif section == 'remote "origin"':
                allowed = {"url", "fetch"}
            elif re.fullmatch(r'branch "[a-zA-Z0-9_/-]+"', section):
                allowed = {"remote", "merge"}
            else:
                raise ValueError
            if set(config[section]) - allowed:
                raise ValueError
            if any("\n" in value for value in config[section].values()):
                raise ValueError
    except (OSError, ValueError, configparser.Error):
        raise PermissionError("unsafe Git configuration") from None

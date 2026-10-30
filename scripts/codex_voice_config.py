"""Change only Codex's two voice URLs, with a private backup and selective rollback."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import tomllib
from pathlib import Path

VOICE_KEYS = ("experimental_realtime_ws_base_url", "experimental_realtime_webrtc_call_base_url")


def update_voice_urls(original: str, values: dict[str, str | None]) -> str:
    before = tomllib.loads(original)
    result = original
    for key in VOICE_KEYS:
        value = values[key]
        pattern = re.compile(rf"(?m)^{key}[ \t]*=[^\r\n]*(?:\r?\n|$)")
        matches = list(pattern.finditer(result))
        if len(matches) > 1 or bool(matches) != (key in before):
            raise ValueError("Voice setting has an unsupported TOML layout; no configuration was changed.")
        replacement = "" if value is None else f"{key} = {json.dumps(value)}\n"
        if matches:
            result = pattern.sub(lambda _: replacement, result, count=1)
        else:
            result = replacement + result
    after = tomllib.loads(result)
    if {key: value for key, value in before.items() if key not in VOICE_KEYS} != {
        key: value for key, value in after.items() if key not in VOICE_KEYS
    }:
        raise ValueError("Non-voice settings would change; no configuration was changed.")
    for key, value in values.items():
        if after.get(key) != value:
            raise ValueError("Voice setting validation failed; no configuration was changed.")
    return result


def atomic_private_write(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".voice-config-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def configure(config: Path, backup: Path, *, port: int | None) -> None:
    if config.is_symlink() or backup.is_symlink() or config == backup:
        raise ValueError("Use distinct regular configuration and backup files.")
    original = config.read_text()
    values: dict[str, str | None]
    if port is None:
        saved = tomllib.loads(backup.read_text())
        values = {key: saved.get(key) for key in VOICE_KEYS}
        if any(value is not None and not isinstance(value, str) for value in values.values()):
            raise ValueError("Backup contains unsupported voice settings.")
    else:
        if not 1024 <= port <= 65535:
            raise ValueError("Choose an unprivileged local port.")
        url = f"http://127.0.0.1:{port}/backend-api/codex"
        values = dict.fromkeys(VOICE_KEYS, url)
    updated = update_voice_urls(original, values)
    if port is not None:
        # Never overwrite the rollback point, including on repeat installation.
        with open(backup, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
    if config.read_text() != original:
        raise ValueError("Codex configuration changed concurrently; retry after checking the private backup.")
    atomic_private_write(config, updated)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enable", "restore"))
    parser.add_argument("--config", type=Path, default=Path.home() / ".codex/config.toml")
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--port", type=int, default=2456)
    args = parser.parse_args()
    try:
        configure(args.config, args.backup, port=args.port if args.action == "enable" else None)
    except (OSError, ValueError):
        raise SystemExit(
            "Voice configuration was not applied. Check the paths, existing backup, and TOML layout."
        ) from None
    print("Voice URLs updated; non-voice settings preserved. Restart the Codex client to load the settings.")


if __name__ == "__main__":
    main()

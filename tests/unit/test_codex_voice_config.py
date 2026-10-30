from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from scripts.codex_voice_config import VOICE_KEYS, configure, update_voice_urls


def test_enable_and_selective_rollback_preserve_provider_and_later_edits(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    backup = tmp_path / "backup.toml"
    provider = (
        '[model_providers.codex-lb]\nbase_url = "http://127.0.0.1:2455/backend-api/codex"\n'
        'experimental_bearer_token = "private-test-key"\n'
    )
    original = (
        'model_provider = "codex-lb"\n' + f'{VOICE_KEYS[0]} = "http://127.0.0.1:2455/backend-api/codex"\n' + provider
    )
    config.write_text(original)
    configure(config, backup, port=2456)
    applied = config.read_text()
    assert applied.endswith(provider)
    assert backup.read_text() == original
    assert config.stat().st_mode & 0o777 == 0o600
    assert backup.stat().st_mode & 0o777 == 0o600
    assert all(tomllib.loads(applied)[key] == "http://127.0.0.1:2456/backend-api/codex" for key in VOICE_KEYS)
    config.write_text('model = "later-user-choice"\n' + applied)
    configure(config, backup, port=None)
    restored = config.read_text()
    assert restored.endswith(provider)
    assert tomllib.loads(restored) == {**tomllib.loads(original), "model": "later-user-choice"}


def test_enable_never_overwrites_existing_backup_or_changes_config_on_failure(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    backup = tmp_path / "backup.toml"
    config.write_text('model = "keep-me"\n')
    backup.write_text("prior backup")
    with pytest.raises(FileExistsError):
        configure(config, backup, port=2456)
    assert config.read_text() == 'model = "keep-me"\n'
    assert backup.read_text() == "prior backup"


@pytest.mark.parametrize(
    "text",
    [
        f'"{VOICE_KEYS[0]}" = "quoted-key"\n',
        f'description = """\n{VOICE_KEYS[0]} = "inside-string"\n"""\n',
        f'{VOICE_KEYS[0]} = """\nmultiline\n"""\n',
    ],
)
def test_unsupported_layout_fails_before_writing(text: str) -> None:
    with pytest.raises(ValueError):
        update_voice_urls(text, dict.fromkeys(VOICE_KEYS, "http://127.0.0.1:2456/backend-api/codex"))


def test_absent_overrides_are_removed_on_rollback(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    backup = tmp_path / "backup.toml"
    original = '# Keep comment\nmodel_provider = "codex-lb"\n[table]\nvalue = 1\n'
    config.write_text(original)
    configure(config, backup, port=2456)
    configure(config, backup, port=None)
    assert config.read_text() == original

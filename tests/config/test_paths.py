from pathlib import Path

from nodus.config.paths import AppPaths


def test_env_var_overrides_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv(AppPaths.DATA_DIR_ENV_VAR, str(tmp_path))

    paths = AppPaths.from_environment()

    assert paths.data_dir == tmp_path
    assert paths.database_path == tmp_path / "nodus.db"


def test_ensure_data_dir_creates_nested_folders(tmp_path):
    paths = AppPaths(tmp_path / "a" / "b")

    paths.ensure_data_dir()

    assert Path(paths.data_dir).is_dir()

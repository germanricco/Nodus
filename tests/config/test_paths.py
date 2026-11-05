from pathlib import Path

from nodus.config.paths import AppPaths, visible_path


def test_env_var_overrides_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv(AppPaths.DATA_DIR_ENV_VAR, str(tmp_path))

    paths = AppPaths.from_environment()

    assert paths.data_dir == tmp_path
    assert paths.database_path == tmp_path / "nodus.db"


def test_ensure_data_dir_creates_nested_folders(tmp_path):
    paths = AppPaths(tmp_path / "a" / "b")

    paths.ensure_data_dir()

    assert Path(paths.data_dir).is_dir()


STORE_PREFIX = (
    r"C:\Program Files\WindowsApps"
    r"\PythonSoftwareFoundation.Python.3.11_3.11.2544.0_x64__qbz5n2kfra8p0"
)


def store_environ(tmp_path) -> dict[str, str]:
    return {"APPDATA": str(tmp_path / "Roaming"), "LOCALAPPDATA": str(tmp_path / "Local")}


def test_visible_path_points_into_store_package_folder(tmp_path):
    environ = store_environ(tmp_path)
    redirected = (
        tmp_path / "Local" / "Packages" / "PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0"
        / "LocalCache" / "Roaming" / "Nodus" / "nodus.db"
    )  # fmt: skip
    redirected.parent.mkdir(parents=True)
    redirected.touch()

    assert visible_path(tmp_path / "Roaming" / "Nodus" / "nodus.db", environ, STORE_PREFIX) == (
        redirected
    )


def test_visible_path_unchanged_outside_store_or_appdata(tmp_path):
    environ = store_environ(tmp_path)
    data_file = tmp_path / "Roaming" / "Nodus" / "nodus.db"
    elsewhere = tmp_path / "pruebas" / "nodus.db"

    assert visible_path(data_file, environ, r"C:\Python311") == data_file
    assert visible_path(elsewhere, environ, STORE_PREFIX) == elsewhere
    # Store Python, but nothing was redirected (e.g. the file was created by another Python).
    assert visible_path(data_file, environ, STORE_PREFIX) == data_file

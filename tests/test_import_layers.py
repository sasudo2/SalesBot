import subprocess


def test_import_layers():
    result = subprocess.run(["lint-imports"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr

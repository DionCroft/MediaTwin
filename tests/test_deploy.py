from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    sys.platform != "win32" or not shutil.which("powershell"),
    reason="Windows PowerShell",
)


def _function(script, name):
    path = str(ROOT / script).replace("'", "''")
    return f"""
    $tokens=$null; $errors=$null
    $ast=[System.Management.Automation.Language.Parser]::ParseFile('{path}', [ref]$tokens, [ref]$errors)
    if ($errors.Count) {{ throw 'PowerShell parse failure' }}
    $function=$ast.Find({{param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq '{name}'}}, $true)
    . ([scriptblock]::Create($function.Extent.Text))
    """


@pytest.mark.parametrize("script", ["build_windows.ps1", "deploy_windows.ps1"])
def test_build_stops_after_native_failure(script):
    python = sys.executable.replace("'", "''")
    code = (
        _function(script, "Invoke-Checked")
        + f"Invoke-Checked {{ & '{python}' -c 'raise SystemExit(7)' }} 'test'; Write-Output 'UNEXPECTED_SUCCESS'"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode != 0 and "exit code 7" in result.stderr
    assert "UNEXPECTED_SUCCESS" not in result.stdout


def test_deploy_refuses_sibling_prefix_cleanup(tmp_path):
    workspace, sibling = tmp_path / "workspace", tmp_path / "workspace-other"
    workspace.mkdir()
    sibling.mkdir()
    code = _function("deploy_windows.ps1", "Remove-WorkspaceItem")
    code += f"$ProjectRoot='{workspace}'; Remove-WorkspaceItem '{sibling}'"
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode != 0 and sibling.exists()
    assert "outside workspace" in result.stderr


def test_deploy_rejects_unsafe_version():
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "deploy_windows.ps1"),
            "-Version",
            "../outside",
            "-SkipInstall",
            "-SkipTests",
            "-SkipBuild",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode != 0 and "Version must" in result.stderr

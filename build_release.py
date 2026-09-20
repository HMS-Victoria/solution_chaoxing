"""Pinned one-file build; user assets in dist/, private build evidence in build/."""
import ast
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    os.chdir(ROOT)
    if sys.version_info[:3] != (3, 9, 13) or struct.calcsize("P") != 8 or sys.platform != "win32":
        raise SystemExit("Build requires CPython 3.9.13 on Windows x64.")
    packages = {}
    for line in (ROOT / "requirements-build.txt").read_text().splitlines():
        if line and not line.startswith("#"):
            name, version = line.split("==")
            actual = importlib.metadata.version(name)
            if actual != version:
                raise SystemExit("Dependency mismatch: " + name + "==" + actual)
            packages[name] = actual
    version = next(ast.literal_eval(n.value) for n in ast.parse(
        (ROOT / "type_at_cursor.pyw").read_text(encoding="utf-8")).body
        if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "APP_VERSION" for t in n.targets))
    output = ROOT / "dist" / ("v" + version)
    # Preserve prior release assets. Rename/archive them explicitly before rebuilding.
    if output.exists():
        raise SystemExit("Output already exists; preserve it before rebuilding: " + str(output))
    work = ROOT / "build" / ("v" + version + "-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    work.mkdir(parents=True)
    source_names = ["type_at_cursor.pyw", "build_exe.cmd", "build_release.py",
                    "requirements-build.txt", "test_release.py", "使用说明.txt"]
    sources = {name: sha256(ROOT / name) for name in source_names}
    numbers = tuple(int(n) for n in version.split(".")) + (0,)
    resource = work / "version.txt"
    resource.write_text(
        "VSVersionInfo(ffi=FixedFileInfo(filevers=" + repr(numbers) + ", prodvers=" + repr(numbers) +
        ", mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)), "
        "kids=[StringFileInfo([StringTable('080404b0', ["
        "StringStruct('FileDescription', '输入到光标'), "
        "StringStruct('ProductName', '输入到光标'), "
        "StringStruct('FileVersion', '" + version + "'), "
        "StringStruct('ProductVersion', '" + version + "')])]), "
        "VarFileInfo([VarStruct('Translation', [2052, 1200])])])", encoding="utf-8")
    env = dict(os.environ, PYTHONHASHSEED="0", SOURCE_DATE_EPOCH="1789639200", PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYINSTALLER_CONFIG_DIR=str(work / "cache"))
    commands = [[sys.executable, "type_at_cursor.pyw", "--selftest"],
                [sys.executable, "test_release.py"],
                [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--noupx",
                 "--onefile", "--windowed", "--name", "输入到光标-Windows-x64",
                 "--version-file", str(resource), "--distpath", str(output),
                 "--workpath", str(work / "pyinstaller"), "--specpath", str(work),
                 str(ROOT / "type_at_cursor.pyw")]]
    with (work / "build.log").open("w", encoding="utf-8") as log:
        for command in commands:
            result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
            log.flush()
            if result.returncode:
                raise SystemExit("Build/check failed. See " + str(work / "build.log"))
    for name, digest in sources.items():
        if sha256(ROOT / name) != digest:
            raise SystemExit("Source changed during build: " + name)
    shutil.copyfile(ROOT / "使用说明.txt", output / "使用说明.txt")
    assets = {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file()}
    (output / "SHA256SUMS").write_text(
        "".join(digest + "  " + name + "\n" for name, digest in assets.items()), encoding="utf-8")
    def git(*args):
        result = subprocess.run(["git", "-c", "safe.directory=" + str(ROOT), *args],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                encoding="utf-8", errors="replace")
        return result.stdout.strip() if result.returncode == 0 else "unavailable"
    record = dict(version=version, built_at=datetime.now(timezone.utc).isoformat(),
                  python=sys.version, platform=platform.platform(), architecture="x64",
                  packages=packages, git_head=git("rev-parse", "HEAD"),
                  git_status=git("status", "--short"), sources_sha256=sources,
                  assets_sha256=assets, source_date_epoch=env["SOURCE_DATE_EPOCH"],
                  commands=commands)
    (work / "build-record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Release assets: " + str(output))
    print("Build evidence: " + str(work))


if __name__ == "__main__":
    main()

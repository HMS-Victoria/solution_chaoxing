"""Non-interactive release verification; does not claim real desktop acceptance."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import pefile
from PyInstaller.archive.readers import CArchiveReader

root = Path(__file__).resolve().parents[3]
release = root / 'dist' / 'v1.0.0'
exe = release / 'TypeAtCursor-Windows-x64.exe'
pe = pefile.PE(str(exe))
assert pe.FILE_HEADER.Machine == 0x8664
assert pe.OPTIONAL_HEADER.Subsystem == 2
assert pe.VS_FIXEDFILEINFO[0].FileVersionMS == 0x00010000
assert pe.VS_FIXEDFILEINFO[0].FileVersionLS == 0
manifests = []
for kind in pe.DIRECTORY_ENTRY_RESOURCE.entries:
    if kind.id == 24:
        for item in kind.directory.entries:
            for lang in item.directory.entries:
                data = lang.data.struct
                manifests.append(pe.get_data(data.OffsetToData, data.Size).decode('utf-8'))
assert any('asInvoker' in manifest and 'requireAdministrator' not in manifest for manifest in manifests)
archive = CArchiveReader(str(exe))
names = sorted(name.replace("\\", "/") for name in archive.toc)
for required in ('python39.dll', '_tkinter.pyd', 'tcl86t.dll', 'tk86t.dll', '_tcl_data/init.tcl', '_tk_data/tk.tcl'):
    assert required in names, required
assert not any(name.endswith(('.pem', '.key', '.env', '.log')) for name in names)
checksums = {}
for line in (release / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
    digest, name = line.split('  ', 1)
    assert hashlib.sha256((release / name).read_bytes()).hexdigest() == digest
    checksums[name] = digest
with tempfile.TemporaryDirectory(prefix='runtime-', dir=root / 'build') as isolated:
    env = dict(os.environ)
    for key in ('PYTHONHOME', 'PYTHONPATH', 'TCL_LIBRARY', 'TK_LIBRARY'):
        env.pop(key, None)
    env.update(PATH=str(Path(os.environ['SystemRoot']) / 'System32'), TEMP=isolated, TMP=isolated,
               USERPROFILE=isolated, APPDATA=isolated, LOCALAPPDATA=isolated)
    process = subprocess.run([str(exe), '--selftest'], cwd=isolated, env=env, timeout=30)
    assert process.returncode == 0
result = dict(architecture='AMD64', subsystem='Windows GUI', file_version='1.0.0.0',
              requested_execution_level='asInvoker', archive_entries=len(names),
              bundled_python_and_tk=True, frozen_selftest_exit=process.returncode,
              frozen_selftest_environment='Python absent from PATH; isolated temp/profile variables; same development OS/account',
              assets_sha256=checksums, real_desktop_test=False, clean_windows_user_test=False)
(root / 'docs/release-readiness/2026-09-20/package-check.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))

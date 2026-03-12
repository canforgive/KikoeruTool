import os
import shutil
import subprocess
import sys

def build(console_mode=True):
    name = 'prekikoeru' if console_mode else 'prekikoeru-noconsole'
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('app', 'app'), ('../frontend/dist', 'frontend/dist')],
    hiddenimports=['uvicorn', 'fastapi', 'sqlalchemy', 'yaml', 'watchdog', 'filetype', 'requests', 'aiohttp', 'pystray', 'PIL'],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='{name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console={console_mode},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''
    
    spec_file = f'build_{name}.spec'
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"Building {name} (console={console_mode})...")
    
    result = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', spec_file, '--clean'],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"Build failed for {name}:")
        print(result.stderr)
        return False
    
    print(f"Build succeeded: dist/{name}.exe")
    return True

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("=" * 50)
    print("Building prekikoeru - two versions")
    print("=" * 50)
    
    success = True
    
    print("\n[1/2] Building console version...")
    if not build(console_mode=True):
        success = False
    
    print("\n[2/2] Building no-console version...")
    if not build(console_mode=False):
        success = False
    
    if success:
        print("\n" + "=" * 50)
        print("Build complete!")
        print("  - dist/prekikoeru.exe (with console)")
        print("  - dist/prekikoeru-noconsole.exe (without console)")
        print("=" * 50)
    else:
        print("\nBuild failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
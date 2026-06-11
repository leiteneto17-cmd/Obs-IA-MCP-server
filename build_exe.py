"""
build_exe.py — Gera o executável do OBS MCP Bridge para distribuição
=====================================================================
Uso:
    pip install pyinstaller
    python build_exe.py

Saída: dist/OBS_MCP_Bridge/OBS_MCP_Bridge.exe  (pasta completa)
       dist/OBS_MCP_Bridge.zip                  (pronto para distribuir)
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT      = Path(__file__).parent.resolve()
APP_DIR   = ROOT / "app"
MCP_DIR   = ROOT / "MCP_Server"
DIST_DIR  = ROOT / "dist"
BUILD_DIR = ROOT / "build"
APP_NAME  = "OBS_MCP_Bridge"

def check_pyinstaller():
    try:
        import PyInstaller  # noqa
    except ImportError:
        print("Instalando PyInstaller…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build():
    check_pyinstaller()

    # Garante que mcp_obs.py está junto do app
    mcp_src = MCP_DIR / "mcp_obs.py"
    mcp_dst = APP_DIR / "mcp_obs.py"
    if mcp_src.exists() and not mcp_dst.exists():
        shutil.copy2(mcp_src, mcp_dst)

    # Limpa builds anteriores
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name",          APP_NAME,
        "--onedir",                        # pasta: mais rápido pra iniciar
        "--windowed",                      # sem janela de console
        "--icon",          "NONE",         # troque por icon.ico se tiver
        "--add-data",      f"{APP_DIR / 'mcp_obs.py'}{os.pathsep}.",
        "--hidden-import", "obsws_python",
        "--hidden-import", "mcp",
        "--hidden-import", "pystray",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageDraw",
        "--hidden-import", "PIL.ImageFont",
        str(APP_DIR / "obs_tray.py"),
    ]

    print("▶ Compilando…")
    subprocess.check_call(cmd, cwd=ROOT)

    # Cria ZIP para distribuição
    zip_path = DIST_DIR / APP_NAME
    shutil.make_archive(str(zip_path), "zip", DIST_DIR, APP_NAME)
    print(f"\n✅ Pronto!")
    print(f"   Executável : dist/{APP_NAME}/{APP_NAME}.exe")
    print(f"   ZIP        : dist/{APP_NAME}.zip")

if __name__ == "__main__":
    build()

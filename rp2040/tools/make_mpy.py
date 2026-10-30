"""Precompile the project to .mpy files (run this on your PC, not on the board).

Why: importing a .py file makes the board compile it in RAM first, which needs a lot of
temporary memory. Precompiled .mpy files load directly: smaller, faster, and far less
heap fragmentation. Pixel Forge works with either.

Usage:
    pip install mpy-cross          (or use the mpy-cross from your MicroPython release)
    python tools/make_mpy.py
Then copy EVERYTHING inside build/ to the board (keep the folder layout). main.py stays a
.py file so the board runs it at boot; this script copies it unchanged. Delete the .py
copies of the other files on the board so the .mpy versions are the ones imported.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build")
KEEP_PY = ("main.py", "config.py")          # config.py stays readable so you can edit pins/settings


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    n = 0
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ("build", "tools", "__pycache__")]
        for f in files:
            src = os.path.join(folder, f)
            rel = os.path.relpath(src, ROOT)
            dst = os.path.join(OUT, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if f.endswith(".py") and f not in KEEP_PY:
                dst = dst[:-3] + ".mpy"
                # Add the -march=armv6m flag to both compiler fallback paths
                r = subprocess.run([sys.executable, "-m", "mpy_cross", "-march=armv6m", "-O2", "-o", dst, src])
                if r.returncode:
                    r = subprocess.run(["mpy-cross", "-march=armv6m", "-O2", "-o", dst, src])
                if r.returncode:
                    sys.exit("mpy-cross failed on " + rel)
                n += 1

                if r.returncode:
                    sys.exit("mpy-cross failed on " + rel)
                n += 1
            else:
                shutil.copy(src, dst)
    print("compiled %d files into %s" % (n, OUT))


if __name__ == "__main__":
    main()

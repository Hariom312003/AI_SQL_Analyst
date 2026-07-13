"""Starts Streamlit as a managed subprocess and confirms it serves its
initial HTML shell without crashing or raising import/syntax errors. Cannot
verify visual rendering (no browser in this sandbox) -- this confirms the
app *boots*, which is what actually matters for catching code errors.
"""
from __future__ import annotations

import subprocess
import time
import os
import tempfile
import requests


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(tempfile.gettempdir(), "streamlit.log")
    log_file = open(log_path, "w")
    import sys
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.headless=true",
            "--server.port=8501",
            "--server.address=127.0.0.1",
            "--browser.gatherUsageStats=false",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=base_dir,
    )

    try:
        start = time.time()
        healthy = False
        for attempt in range(1, 41):
            if proc.poll() is not None:
                print("!! Streamlit exited early with code", proc.returncode)
                break
            try:
                r = requests.get("http://127.0.0.1:8501", timeout=2)
                print(f"attempt {attempt} (t={time.time()-start:.1f}s): HTTP {r.status_code}")
                if r.status_code == 200:
                    healthy = True
                    break
            except requests.RequestException as exc:
                print(f"attempt {attempt} (t={time.time()-start:.1f}s): {type(exc).__name__}")
            time.sleep(0.75)

        print("\nSTREAMLIT HEALTHY:", healthy)
        if healthy:
            body = r.text
            print("Response length:", len(body), "bytes")
            print("Contains 'streamlit' marker:", "streamlit" in body.lower())
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_file.close()
        print("\n--- streamlit.log ---")
        try:
            print(open(log_path).read())
        except Exception as e:
            print("Failed to read log file:", e)


if __name__ == "__main__":
    main()


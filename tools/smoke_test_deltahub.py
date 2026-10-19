#!/usr/bin/env python3
"""Headless smoke test for DeltaHub.

    sudo apt install python3-pyqt6
    python3 tools/smoke_test_deltahub.py

Builds the real application object with Qt's offscreen platform plugin, walks
every page, and exercises the refresh path. Run it on Linux (WSL, a VM or the
build container) -- Windows blocks the Qt DLLs on some managed machines.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

ROOT = Path(__file__).resolve().parent.parent
DELTAHUB = ROOT / "config/includes.chroot/usr/bin/deltahub"

if not DELTAHUB.is_file():
    raise SystemExit(f"cannot find DeltaHub at {DELTAHUB}")

loader = importlib.machinery.SourceFileLoader("deltahub", str(DELTAHUB))
spec = importlib.util.spec_from_loader("deltahub", loader)
hub = importlib.util.module_from_spec(spec)
loader.exec_module(hub)

from PyQt6.QtWidgets import QApplication  # noqa: E402  (needs QT_QPA_PLATFORM first)

app = QApplication([])

window = hub.DeltaHub()
assert window.stack.count() == len(hub.DeltaHub.PAGES), "page count mismatch"
for index, name in enumerate(hub.DeltaHub.PAGES):
    window.show_page(index)
    assert window.page_title.text() == name, f"page title mismatch on {name}"
window.refresh_overview()
assert window.system_summary.text(), "overview did not render a summary"

welcome = hub.WelcomeDialog()
assert welcome.windowTitle() == "Welcome to DeltaOS"

# Pure helpers should not raise regardless of the host system.
assert isinstance(hub.deltaos_version(), str)
assert isinstance(hub.read_os_release(), dict)

window.close()
print(f"deltahub smoke test passed: {len(hub.DeltaHub.PAGES)} pages, "
      f"live={hub.IS_LIVE}")

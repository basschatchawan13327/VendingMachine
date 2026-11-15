#!/usr/bin/env python3
"""
Smart Vending Machine Application Entry Point.
Edge Hill University - Software Engineering Group Assignment.

Verifies required dependencies from requirements.txt before launching the GUI.
Installs any missing packages automatically.

Usage:
    python3 main.py
"""

import os
import sys
import re
import subprocess
import importlib.util
from typing import List

# Mapping from pip package name to importable Python module name
PACKAGE_MODULE_MAP = {
    "pillow": "PIL",
    "opencv-python": "cv2",
    "opencv-python-headless": "cv2",
    "pyzbar": "pyzbar",
    "numpy": "numpy",
    "stripe": "stripe",
}


def check_and_install_dependencies(requirements_path: str) -> None:
    """
    Check if libraries listed in requirements.txt are installed.
    If missing libraries are detected, attempt to install them via pip.
    """
    if not os.path.isfile(requirements_path):
        return

    missing_specs: List[str] = []

    try:
        from importlib.metadata import distribution, PackageNotFoundError
    except ImportError:
        distribution = None
        PackageNotFoundError = Exception  # type: ignore

    with open(requirements_path, "r", encoding="utf-8") as f:
        for line in f:
            clean_line = line.strip()
            if not clean_line or clean_line.startswith("#"):
                continue

            # Extract base package name (e.g. 'Pillow' from 'Pillow>=9.0.0')
            pkg_name = re.split(r"[<>=!~;]", clean_line)[0].strip()
            if not pkg_name:
                continue

            mod_name = PACKAGE_MODULE_MAP.get(pkg_name.lower(), pkg_name.replace("-", "_"))

            # Check if importable or installed via metadata
            is_installed = False
            if importlib.util.find_spec(mod_name) is not None:
                is_installed = True
            elif distribution is not None:
                try:
                    distribution(pkg_name)
                    is_installed = True
                except PackageNotFoundError:
                    is_installed = False

            if not is_installed:
                missing_specs.append(clean_line)

    if missing_specs:
        print("=" * 68)
        print("[Startup] Required Python dependencies missing:")
        for spec in missing_specs:
            print(f"  • {spec}")
        print("[Startup] Installing missing dependencies via pip...")
        print("=" * 68)

        cmd = [sys.executable, "-m", "pip", "install"] + missing_specs
        try:
            subprocess.check_call(cmd)
            print("[Startup] Dependencies installed successfully!")
        except Exception as e:
            print(f"[Startup] Warning: Could not auto-install dependencies: {e}")
            print("[Startup] Attempting to continue application launch...")
        print("=" * 68)
    else:
        print("[Startup] All dependencies verified. Starting application...")


def main() -> None:
    """Check dependencies and launch the Smart Vending Machine application."""
    # Ensure project root directory is in Python import path
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # 1. Verify and auto-install required dependencies
    requirements_file = os.path.join(project_root, "requirements.txt")
    check_and_install_dependencies(requirements_file)

    # 2. Import application components after dependency verification
    import tkinter as tk
    from src.views.customer_ui import CustomerVendingApp

    # 3. Launch Tkinter GUI application
    root = tk.Tk()
    root.title("Edge Hill University — Smart Vending Machine")

    app = CustomerVendingApp(root)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\n[Application] Shutting down Smart Vending Machine...")
        try:
            root.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    main()

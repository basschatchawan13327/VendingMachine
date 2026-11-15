#!/usr/bin/env python3
"""
Smart Vending Machine Application Entry Point.
Edge Hill University - Software Engineering Group Assignment.

Usage:
    python3 main.py
"""

import os
import sys
import tkinter as tk

# Ensure project root directory is in Python import path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.views.customer_ui import CustomerVendingApp


def main() -> None:
    """Initialize root Tk window and launch Smart Vending Machine application."""
    root = tk.Tk()
    root.title("Edge Hill University — Smart Vending Machine")
    
    # Instantiate primary Customer UI application
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

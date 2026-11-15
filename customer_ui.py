#!/usr/bin/env python3
"""
Legacy entry point compatibility shim.
Redirects to src.views.customer_ui.

Recommended usage:
    python3 main.py
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.views.customer_ui import CustomerVendingApp, main

if __name__ == "__main__":
    main()

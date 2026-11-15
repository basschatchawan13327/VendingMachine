"""
Views package for user interface and visual presentation.
"""

from .customer_ui import CustomerVendingApp
from .barcode_scanner import BarcodeCameraScanner

__all__ = [
    "CustomerVendingApp",
    "BarcodeCameraScanner",
]

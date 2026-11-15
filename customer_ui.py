"""
Customer-Facing Vending Machine User Interface (customer_ui.py)
--------------------------------------------------------------
Modern, touchscreen-optimised customer interface designed for end-users.
Styled STRICTLY using the official 5-color theme:
  1. #3A0C51 - Deep Aubergine Purple
  2. #BAEF2D - Electric Lime Green
  3. #FFFFFF - Pure White
  4. #D883FF - Bright Lavender Lilac
  5. #12372E - Deep Pine / Forest Green
"""

import os
import time
import json
import base64
import urllib.request
import urllib.parse
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional, Tuple

# Safe OpenCV (cv2) import with graceful error handling
try:
    import cv2  # type: ignore
    HAS_CV2 = True
except Exception:
    cv2 = None  # type: ignore
    HAS_CV2 = False

# Safe PIL (Pillow) support
try:
    from PIL import Image, ImageTk, ImageChops  # type: ignore
    HAS_PIL = True
except Exception:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore
    ImageChops = None  # type: ignore
    HAS_PIL = False

# Safe zxing-cpp for Code 128 linear barcode decoding
try:
    import zxingcpp  # type: ignore
    HAS_ZXING = True
except Exception:
    zxingcpp = None  # type: ignore
    HAS_ZXING = False

# Safe numpy support for OpenCV matrices
try:
    import numpy as np  # type: ignore
    HAS_NUMPY = True
except Exception:
    np = None  # type: ignore
    HAS_NUMPY = False


def generate_stripe_qr_image(url: str, size: int = 300) -> Optional[Any]:
    """
    Generates a large, crisp, high-contrast QR code PIL Image for the checkout URL.
    Preserves the full unmodified Stripe Checkout URL (including client-side token fragments)
    so Stripe's web interface opens seamlessly without 'incomplete link' errors.
    Uses cv2.QRCodeEncoder or qrcode module if available.
    """
    if not url:
        return None
    # Keep the full unmodified URL (including #fid... fragment) required by Stripe Checkout security
    unmodified_url = url.strip()

    try:
        # 1. Try qrcode package if installed
        try:
            import qrcode  # type: ignore
            qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(unmodified_url)
            qr.make(fit=True)
            pil_img = qr.make_image(fill_color="black", back_color="white")
            if hasattr(pil_img, "resize") and HAS_PIL and Image is not None:
                resample = getattr(Image, "Resampling", Image).NEAREST
                return pil_img.resize((size, size), resample)
            return pil_img
        except ImportError:
            pass

        # 2. Use cv2.QRCodeEncoder (standard in OpenCV 4.x+)
        if HAS_CV2 and cv2 is not None and hasattr(cv2, "QRCodeEncoder") and HAS_PIL and Image is not None and HAS_NUMPY and np is not None:
            encoder = cv2.QRCodeEncoder.create()
            qr_mat = encoder.encode(unmodified_url)
            if qr_mat is not None and qr_mat.size > 0:
                # Add quiet zone border (4 modules of white 255)
                pad_qr = np.pad(qr_mat, pad_width=4, mode="constant", constant_values=255)
                # Resize using crisp integer module scaling so phone cameras decode reliably
                mod_count = pad_qr.shape[0]
                scale = max(2, round(size / mod_count))
                out_w = int(pad_qr.shape[1] * scale)
                out_h = int(pad_qr.shape[0] * scale)
                resized = cv2.resize(pad_qr, (out_w, out_h), interpolation=cv2.INTER_NEAREST)
                pil_img = Image.fromarray(resized).convert("RGB")
                return pil_img
    except Exception as e:
        print(f"[QR] Error generating QR code: {e}")
    return None

# System Model Imports
import threading
import webbrowser
from controller import (
    VendingController,
    MachineState,
    load_products,
    save_products,
    load_members,
    save_members,
    load_cash_inventory,
    save_cash_inventory,
    load_payment_config,
    save_payment_config,
    load_transactions,
    save_transactions,
    log_activity,
    DATA_DIR,
    PRODUCTS_FILE,
    CASH_FILE,
    PAYMENT_CONFIG_FILE,
    TRANSACTIONS_FILE,
    MEMBERS_FILE,
)
from inventory import Drink, DrinkDispenser, LoyaltyScanner, LoyaltyAccount, StockSensor
from payment import (
    PaymentModule,
    CashReceiver,
    CardReader,
    PaymentResult,
    CashReceiverState,
    StripeBankService,
    PayPalBankService,
    CustomRestBankService,
    create_bank_service,
    DEFAULT_STRIPE_PUBLISHABLE_KEY,
)
from bank import MockBankService
from logger import Logger, TransactionRecord
from timer import TransactionTimer
from barcode_scanner import BarcodeCameraScanner


# ===========================================================================
# UI Color Palette (STRICT 5-COLOR THEME)
# ===========================================================================
CLR_DEEP_PURPLE = "#3A0C51"  # Deep Aubergine Purple
CLR_LIME        = "#BAEF2D"  # Electric Lime Green
CLR_WHITE       = "#FFFFFF"  # Pure White
CLR_LILAC       = "#D883FF"  # Bright Lavender Lilac
CLR_DARK_GREEN  = "#12372E"  # Deep Pine / Forest Green

# Semantic Theme Mappings
BG_APP         = CLR_DEEP_PURPLE  # Overall window background, header & footer (#3A0C51)
BG_MIDDLE      = CLR_LILAC        # Middle background area between top & bottom bar (#D883FF)
BG_CARD        = CLR_DEEP_PURPLE  # Product cards & right panel background (#3A0C51)
BG_SCREEN      = CLR_DARK_GREEN   # Digital display screen background (#12372E)
BTN_BG         = CLR_LIME         # Buttons background (#BAEF2D)
BTN_FG         = CLR_DEEP_PURPLE  # Buttons text color (#3A0C51)
ACCENT_PRIMARY = CLR_LIME         # Primary highlight / CTA (#BAEF2D)
ACCENT_SECOND  = CLR_LILAC        # Secondary highlight / accent (#D883FF)
TEXT_PRIMARY   = CLR_WHITE        # Main title & body text (#FFFFFF)
TEXT_ACCENT    = CLR_LIME         # Price & badge text (#BAEF2D)
TEXT_MUTED     = CLR_LILAC        # Subtitle & secondary text (#D883FF)
BTN_KEYPAD_BG  = CLR_DARK_GREEN   # Numpad button background (#12372E)
BTN_KEYPAD_FG  = CLR_WHITE        # Numpad button text (#FFFFFF)

# Assets Directory Path
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Default Product Photographic Assets Mapping (from assets/ directory)
DEFAULT_PRODUCT_IMAGES: Dict[str, str] = {
    "ESPRESSO": "Starbuck_Espresso.jpg",
    "LATTE": "Nescafe_Latte.avif",
    "HOT_CHOCOLATE": "milo_can.jpg",
    "WATER": "Aquafina_water.jpg",
    "CAPPUCCINO": "nescafe_cappucino.avif",
    "GREEN_TEA": "matcha_latte.png",
    "ICED_COLA": "coca_cola.jpg",
    "ORANGE_JUICE": "tropicana_orange_juice.png",
    "LEMON_TEA": "lemon_iced_tea.png",
}


# ===========================================================================
# Product Catalogue Dynamic Loader (Loaded from data/products.json)
# ===========================================================================
def load_catalogue_data(file_path: str = PRODUCTS_FILE) -> List[Dict]:
    """
    Loads product metadata and catalogue directly from data/products.json.
    Ensures item boxes strictly match the products configured in products.json.
    Provides graceful fallbacks for slot numbers, descriptions, icon types, and images.
    """
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []

            # 1. Track existing slot numbers to prevent duplicate slot IDs
            assigned_slots = set()
            for item in data:
                s = item.get("slot_num")
                if s is not None and str(s).strip():
                    try:
                        normalized = f"{int(str(s).strip()):02d}"
                    except (ValueError, TypeError):
                        normalized = str(s).strip()
                    item["slot_num"] = normalized
                    assigned_slots.add(normalized)

            # 2. Fill defaults and auto-assign missing slot numbers
            next_num = 1
            for item in data:
                if not item.get("slot_num"):
                    while f"{next_num:02d}" in assigned_slots:
                        next_num += 1
                    auto_slot = f"{next_num:02d}"
                    item["slot_num"] = auto_slot
                    assigned_slots.add(auto_slot)
                    next_num += 1

                # Icon type inference
                if "icon_type" not in item or not item["icon_type"]:
                    did = (item.get("drink_id", "") + " " + item.get("name", "")).lower()
                    if "water" in did:
                        item["icon_type"] = "water"
                    elif "latte" in did or "cappuccino" in did:
                        item["icon_type"] = "latte"
                    elif "espresso" in did:
                        item["icon_type"] = "espresso"
                    elif "choc" in did:
                        item["icon_type"] = "chocolate"
                    elif "tea" in did or "matcha" in did:
                        item["icon_type"] = "tea"
                    else:
                        item["icon_type"] = "can"

                # Image asset mapping fallback
                if "image" not in item or not item["image"]:
                    did_clean = item.get("drink_id", "").upper()
                    if did_clean in DEFAULT_PRODUCT_IMAGES:
                        item["image"] = DEFAULT_PRODUCT_IMAGES[did_clean]
                    else:
                        name_lower = (item.get("name", "") + " " + did_clean).lower()
                        if "espresso" in name_lower:
                            item["image"] = "Starbuck_Espresso.jpg"
                        elif "latte" in name_lower and "green" not in name_lower and "matcha" not in name_lower:
                            item["image"] = "Nescafe_Latte.avif"
                        elif "cappuccino" in name_lower:
                            item["image"] = "nescafe_cappucino.avif"
                        elif "choc" in name_lower or "milo" in name_lower:
                            item["image"] = "milo_can.jpg"
                        elif "water" in name_lower or "aqua" in name_lower:
                            item["image"] = "Aquafina_water.jpg"
                        elif "matcha" in name_lower or "green" in name_lower or "tea" in name_lower:
                            item["image"] = "matcha_latte.png"
                        elif "cola" in name_lower or "coke" in name_lower:
                            item["image"] = "coca_cola.jpg"
                        elif "orange" in name_lower or "juice" in name_lower:
                            item["image"] = "tropicana_orange_juice.png"

                # Description fallback
                if "desc" not in item or item["desc"] is None:
                    item["desc"] = ""

                # Stock & Price fallbacks
                if "stock" not in item or item["stock"] is None:
                    item["stock"] = 10
                if "price" not in item or item["price"] is None:
                    item["price"] = 100
                if "name" not in item or not item["name"]:
                    item["name"] = item.get("drink_id", "Drink")
                if "category" not in item or not item["category"]:
                    item["category"] = "Drinks"
                if "unit_weight" not in item or item["unit_weight"] is None:
                    item["unit_weight"] = 250.0
                if "tare_weight" not in item or item["tare_weight"] is None:
                    item["tare_weight"] = 50.0

            return data
    except Exception as e:
        print(f"[customer_ui] Error reading products from {file_path}: {e}")
        return []


def save_catalogue_data(catalogue: List[Dict], file_path: str = PRODUCTS_FILE) -> bool:
    """Saves updated product catalogue data back to data/products.json."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(catalogue, f, indent=2)
        return True
    except Exception as e:
        print(f"[customer_ui] Error saving products to {file_path}: {e}")
        return False


# ===========================================================================
# Vector Graphic Drink Icon Painter (Using ONLY Theme Colors)
# ===========================================================================
def draw_drink_artwork(canvas: tk.Canvas, icon_type: str, width: int = 140, height: int = 100) -> None:
    """Draws a clean, modern vector beverage graphic inside a canvas using ONLY the 5 theme colors."""
    canvas.delete("all")
    cx, cy = width // 2, height // 2

    if icon_type in ("espresso", "latte"):
        # Ceramic Coffee Cup & Saucer
        canvas.create_oval(cx - 36, cy + 24, cx + 36, cy + 34, fill=CLR_DARK_GREEN, outline=CLR_LILAC, width=2)
        # Cup body
        canvas.create_rectangle(cx - 28, cy - 8, cx + 28, cy + 26, fill=CLR_WHITE, outline=CLR_LILAC, width=2)
        canvas.create_arc(cx - 28, cy + 10, cx + 28, cy + 32, start=180, extent=180, fill=CLR_WHITE, outline=CLR_LILAC, width=2)
        # Liquid surface
        canvas.create_oval(cx - 26, cy - 14, cx + 26, cy - 2, fill=CLR_DARK_GREEN if icon_type == "espresso" else CLR_DEEP_PURPLE, outline=CLR_LIME, width=1)
        # Cup Handle
        canvas.create_arc(cx + 18, cy - 2, cx + 42, cy + 20, start=270, extent=180, style=tk.ARC, outline=CLR_WHITE, width=4)
        # Steam trails
        canvas.create_line(cx - 10, cy - 18, cx - 14, cy - 30, cx - 8, cy - 42, smooth=True, fill=CLR_LIME, width=2)
        canvas.create_line(cx + 8, cy - 18, cx + 12, cy - 30, cx + 6, cy - 42, smooth=True, fill=CLR_LILAC, width=2)

    elif icon_type in ("chocolate", "tea"):
        # Tall Ceramic Mug
        canvas.create_oval(cx - 30, cy + 26, cx + 30, cy + 34, fill=CLR_DARK_GREEN, outline=CLR_LILAC, width=1)
        canvas.create_rectangle(cx - 26, cy - 14, cx + 26, cy + 28, fill=CLR_WHITE, outline=CLR_LILAC, width=2)
        canvas.create_arc(cx - 26, cy + 16, cx + 26, cy + 34, start=180, extent=180, fill=CLR_WHITE, outline=CLR_LILAC, width=2)
        # Drink top
        canvas.create_oval(cx - 24, cy - 20, cx + 24, cy - 8, fill=CLR_DEEP_PURPLE if icon_type == "chocolate" else CLR_DARK_GREEN, outline=CLR_LIME, width=1)
        # Handle
        canvas.create_arc(cx + 16, cy - 6, cx + 38, cy + 22, start=270, extent=180, style=tk.ARC, outline=CLR_WHITE, width=4)
        # Marshmallows or foam
        canvas.create_oval(cx - 12, cy - 18, cx - 2, cy - 10, fill=CLR_LIME, outline=CLR_DEEP_PURPLE, width=1)
        canvas.create_oval(cx + 2, cy - 18, cx + 12, cy - 10, fill=CLR_LILAC, outline=CLR_DEEP_PURPLE, width=1)

    elif icon_type == "water":
        # Sleek Water Bottle
        canvas.create_oval(cx - 18, cy + 26, cx + 18, cy + 34, fill=CLR_DARK_GREEN, outline=CLR_LIME, width=1)
        # Bottle body
        canvas.create_rectangle(cx - 16, cy - 16, cx + 16, cy + 28, fill=CLR_LILAC, outline=CLR_WHITE, width=2)
        # Cap & neck
        canvas.create_rectangle(cx - 8, cy - 26, cx + 8, cy - 16, fill=CLR_LIME, outline=CLR_DARK_GREEN, width=1)
        canvas.create_rectangle(cx - 9, cy - 32, cx + 9, cy - 26, fill=CLR_WHITE, outline=CLR_DARK_GREEN, width=1)
        # Water drop badge
        canvas.create_oval(cx - 6, cy - 4, cx + 6, cy + 8, fill=CLR_WHITE, outline="")
        canvas.create_polygon(cx, cy - 10, cx - 6, cy, cx + 6, cy, fill=CLR_WHITE)

    else:
        # Chilled Beverage Can
        canvas.create_oval(cx - 20, cy + 24, cx + 20, cy + 32, fill=CLR_DARK_GREEN, outline=CLR_LILAC, width=1)
        canvas.create_rectangle(cx - 18, cy - 18, cx + 18, cy + 26, fill=CLR_LIME if icon_type == "can" else CLR_LILAC, outline=CLR_WHITE, width=2)
        canvas.create_oval(cx - 18, cy - 26, cx + 18, cy - 14, fill=CLR_WHITE, outline=CLR_DARK_GREEN, width=2)
        canvas.create_oval(cx - 8, cy - 22, cx + 8, cy - 18, fill=CLR_DEEP_PURPLE, outline="")


# ===========================================================================
# Photographic Product Image Renderer (With Vector Fallback)
# ===========================================================================
_TRIMMED_IMAGE_CACHE: Dict[str, Any] = {}


def _trim_artwork_margins(im: Any) -> Any:
    """Trims surrounding uniform white/transparent padding so product bottle/can fills the showcase frame."""
    if not HAS_PIL or im is None:
        return im
    try:
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in getattr(im, "info", {})):
            comp = Image.new("RGBA", im.size, (255, 255, 255, 255))
            comp.paste(im, (0, 0), im)
            rgb_comp = comp.convert("RGB")
        else:
            rgb_comp = im.convert("RGB")

        if ImageChops is not None:
            bg_rgb = Image.new("RGB", rgb_comp.size, (255, 255, 255))
            diff = ImageChops.difference(rgb_comp, bg_rgb)
            diff = ImageChops.add(diff, diff, 2.0, -10)
            bbox = diff.getbbox()
            if bbox:
                w, h = im.size
                pad = 4
                x1 = max(0, bbox[0] - pad)
                y1 = max(0, bbox[1] - pad)
                x2 = min(w, bbox[2] + pad)
                y2 = min(h, bbox[3] + pad)
                return im.crop((x1, y1, x2, y2))
    except Exception:
        pass
    return im


def render_product_artwork(
    canvas: tk.Canvas,
    prod: Dict,
    width: int = 160,
    height: int = 116,
    photo_cache: Optional[Dict] = None,
    default_bg: str = CLR_WHITE,
    fallback_bg: str = BG_CARD,
) -> bool:
    """
    Renders the official product photograph from assets/ inside a canvas.
    If image exists and PIL is available:
      - Resizes preserving aspect ratio with Lanczos resampling.
      - Smoothly composites alpha channels over pure white.
      - Centers the photo on the canvas and sets background to default_bg (Pure White).
      - Retains PhotoImage reference on the canvas to prevent garbage collection.
    If image is unavailable or loading fails:
      - Falls back gracefully to vector graphic (draw_drink_artwork).
      - Sets canvas background to fallback_bg.
    Returns True if photo rendered, False if vector artwork fallback was used.
    """
    try:
        canvas.delete("all")
    except Exception:
        return False

    photo = None
    image_name = prod.get("image")
    if not image_name and prod.get("drink_id"):
        image_name = DEFAULT_PRODUCT_IMAGES.get(prod["drink_id"].upper())

    if HAS_PIL and image_name:
        cache_key = (str(image_name), width, height)
        if photo_cache is not None and cache_key in photo_cache:
            photo = photo_cache[cache_key]
        else:
            file_path = os.path.join(ASSETS_DIR, str(image_name))
            if not os.path.exists(file_path) and os.path.isdir(ASSETS_DIR):
                target_lower = str(image_name).lower()
                for fn in os.listdir(ASSETS_DIR):
                    if fn.lower() == target_lower:
                        file_path = os.path.join(ASSETS_DIR, fn)
                        break
            if os.path.exists(file_path):
                try:
                    if file_path not in _TRIMMED_IMAGE_CACHE:
                        with Image.open(file_path) as raw_im:
                            _TRIMMED_IMAGE_CACHE[file_path] = _trim_artwork_margins(raw_im.copy())
                    base_im = _TRIMMED_IMAGE_CACHE[file_path]
                    im_copy = base_im.copy()
                    max_w = max(10, width - 4)
                    max_h = max(10, height - 4)
                    im_copy.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
                    if im_copy.mode in ("RGBA", "LA") or (im_copy.mode == "P" and "transparency" in im_copy.info):
                        comp = Image.new("RGBA", im_copy.size, (255, 255, 255, 255))
                        comp.paste(im_copy, (0, 0), im_copy)
                        final_im = comp.convert("RGB")
                    else:
                        final_im = im_copy.convert("RGB")
                    photo = ImageTk.PhotoImage(final_im)
                    if photo_cache is not None:
                        photo_cache[cache_key] = photo
                except Exception as e:
                    print(f"[render_product_artwork] Failed to load image '{image_name}': {e}")
                    photo = None

    if photo is not None:
        try:
            canvas.config(bg=default_bg)
        except Exception:
            pass
        cx = width // 2
        cy = height // 2
        canvas.create_image(cx, cy, image=photo, anchor="center")
        canvas.image = photo  # Keep reference so GC does not destroy it!
        return True
    else:
        try:
            canvas.config(bg=fallback_bg)
        except Exception:
            pass
        draw_drink_artwork(canvas, prod.get("icon_type", "can"), width=width, height=height)
        return False


# ===========================================================================
# Main Application Class
# ===========================================================================
class CustomerVendingApp:
    """
    User-Centric Touchscreen Vending Machine Application.
    Provides a modular page architecture for seamless multi-page transitions.
    Styled strictly with the 5-color theme.
    """

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Edge Hill University - Touchscreen Drink Vending Machine")

        # Responsive window sizing based on current display resolution
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # Target 80-84% of screen size, comfortably bounded so it never clips title bar or dock
        target_w = min(1120, max(940, int(screen_w * 0.84)))
        target_h = min(720, max(620, int(screen_h * 0.82)))

        # Center the window on the user's screen
        pos_x = max(0, (screen_w - target_w) // 2)
        pos_y = max(0, (screen_h - target_h) // 2 - 25)

        self.root.geometry(f"{target_w}x{target_h}+{pos_x}+{pos_y}")
        self.root.minsize(860, 560)
        self.root.configure(bg=BG_APP)

        # Initialize Backend Components
        self._init_backend()

        # State Variables
        self.entered_slot = tk.StringVar(value="--")
        self.selected_product: Optional[Dict] = None
        self.current_page: str = "catalogue"

        # Photographic Product Image Cache: (image_name, width, height) -> PhotoImage
        self._product_images: Dict[Tuple[str, int, int], ImageTk.PhotoImage] = {}

        # Animation & Interactive Widget References
        self.card_widgets: Dict[str, tk.Frame] = {}
        self.card_pills: Dict[str, tk.Label] = {}
        self.keypad_buttons: Dict[str, tk.Button] = {}
        self._pending_card_after_ids: List[str] = []
        self._typing_blink_state: bool = True

        # File watcher state for dynamic live synchronization with data/products.json
        self._products_file_mtime: float = 0.0
        self._products_file_fingerprint: str = ""
        self._watcher_after_id: Optional[str] = None
        self._init_file_watcher_fingerprint()

        # Build Main Frame Container (Supports switching to Page 2, Page 3, etc.)
        self.container = tk.Frame(self.root, bg=BG_MIDDLE)
        self.container.pack(fill=tk.BOTH, expand=True)

        # Dictionary to store different pages
        self.pages: Dict[str, tk.Frame] = {}
        self._is_transitioning: bool = False

        # Build Page 1: Product Selection Catalogue
        self._build_page1_catalogue()

        # Build Page 2: Payment & Loyalty Selection
        self._build_page2_payment()

        # Build Page 3: Order Success & Dispense Confirmation
        self._build_page3_success()

        # Build Page 4: Order Cancelled & Refund Confirmation
        self._build_page_cancelled()

        # Bind Physical Keyboard Events (No on-screen keyboard)
        self._bind_keyboard_events()

        # Show Page 1 initially
        self.show_page("catalogue")

        # Start Living Kiosk Heartbeat Animation
        self._start_typing_heartbeat()

        # Start File Watcher Loop for live products.json changes
        self._start_products_file_watcher()

        # Handle window close gracefully
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        """Gracefully cancels recurring timers and tears down the UI."""
        for attr in (
            "_watcher_after_id",
            "_heartbeat_after_id",
            "_clock_after_id",
            "_dispense_restore_after_id",
            "_success_countdown_after_id",
        ):
            after_id = getattr(self, attr, None)
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
                setattr(self, attr, None)
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.destroy()

    def _init_backend(self) -> None:
        """Sets up dispenser, drinks catalogue, and controller backend dynamically from products.json."""
        # 1. Load product catalogue from products.json
        self.catalogue: List[Dict] = load_catalogue_data()

        # 2. Build dispenser slots strictly matching products.json
        loaded_drinks = [
            Drink(
                drink_id=d["drink_id"],
                name=d["name"],
                price=d["price"],
                stock=d.get("stock", 10),
                slot_num=d.get("slot_num"),
                desc=d.get("desc", ""),
                icon_type=d.get("icon_type", "can"),
                category=d.get("category", "Drinks"),
                image=d.get("image"),
                unit_weight=d.get("unit_weight", 250.0),
                tare_weight=d.get("tare_weight", 50.0),
            )
            for d in self.catalogue
        ]

        self.dispenser = DrinkDispenser(loaded_drinks)
        self.stock_sensor = StockSensor(self.dispenser, low_stock_level=3)

        # 3. Loyalty Programme
        loaded_accounts = load_members()
        self.loyalty_scanner = LoyaltyScanner(loaded_accounts)

        # 4. Payments & Dynamic Gateway Engine
        self.payment_config = load_payment_config()
        self.cash_enabled: bool = bool(self.payment_config.get("cash_enabled", True))
        self.card_enabled: bool = bool(self.payment_config.get("card_enabled", True))
        self.active_gateway_name: str = self.payment_config.get("active_gateway", "stripe")
        self.session_timeout_seconds: int = int(self.payment_config.get("timeout_seconds", 60))

        gw_config = self.payment_config.get("gateways", {}).get(self.active_gateway_name, {})
        self.active_bank = create_bank_service(self.active_gateway_name, gw_config)
        self.stripe_bank = self.active_bank
        self.mock_bank = MockBankService()
        self.cash_receiver = CashReceiver()
        self.card_reader = CardReader(self.active_bank)
        self.payment_module = PaymentModule([self.cash_receiver, self.card_reader])

        # 5. Logger & Timer
        self.logger = Logger()
        loaded_txs = load_transactions()
        self.logger._records = list(loaded_txs)
        self.timer = TransactionTimer(timeout_seconds=self.session_timeout_seconds)

        # 6. Core Vending Controller
        self.controller = VendingController(
            dispenser=self.dispenser,
            loyalty_scanner=self.loyalty_scanner,
            payment_module=self.payment_module,
            logger=self.logger,
            timer=self.timer,
            stock_sensor=self.stock_sensor,
        )

        # Quick lookup map: slot_num -> product metadata
        self.slot_map: Dict[str, Dict] = {item["slot_num"]: item for item in self.catalogue}

    def _init_file_watcher_fingerprint(self) -> None:
        """Records initial products.json modification stamp and size."""
        if os.path.exists(PRODUCTS_FILE):
            try:
                mtime = os.path.getmtime(PRODUCTS_FILE)
                size = os.path.getsize(PRODUCTS_FILE)
                self._products_file_mtime = mtime
                self._products_file_fingerprint = f"{mtime}_{size}"
            except Exception:
                pass

    def _start_products_file_watcher(self) -> None:
        """Starts background loop watching data/products.json for file additions/deletions."""
        self._check_products_file_updates()

    def _check_products_file_updates(self) -> None:
        """Polls products.json modification time; if changed, hot-reloads catalogue and UI immediately."""
        try:
            if os.path.exists(PRODUCTS_FILE):
                mtime = os.path.getmtime(PRODUCTS_FILE)
                size = os.path.getsize(PRODUCTS_FILE)
                fingerprint = f"{mtime}_{size}"
                if fingerprint != self._products_file_fingerprint:
                    self._products_file_mtime = mtime
                    self._products_file_fingerprint = fingerprint
                    # Re-sync catalogue, dispenser, and product card boxes
                    self.sync_products_from_json(animate=False)
        except Exception:
            pass
        finally:
            try:
                if hasattr(self, "root") and self.root.winfo_exists():
                    self._watcher_after_id = self.root.after(500, self._check_products_file_updates)
            except Exception:
                pass

    def sync_products_from_json(self, animate: bool = False) -> None:
        """
        Synchronizes app state with data/products.json:
        1. Reloads catalogue list (reflecting any added/removed products).
        2. Synchronizes DrinkDispenser slots (add, update, remove).
        3. Rebuilds slot lookup map.
        4. Recreates UI product boxes matching the updated catalogue.
        5. Validates current slot selection (clears if deleted).
        """
        self.catalogue = load_catalogue_data()
        self.slot_map = {item["slot_num"]: item for item in self.catalogue}

        # Synchronize dispenser slots with catalogue
        if hasattr(self, "dispenser"):
            existing_drinks = {d.drink_id.upper(): d for d in self.dispenser.getAllDrinks()}
            new_slots: List[Drink] = []
            for item in self.catalogue:
                did = item["drink_id"].upper()
                if did in existing_drinks:
                    d = existing_drinks[did]
                    d._name = item["name"]
                    d._price = item["price"]
                    d._stock = item.get("stock", d.stock)
                    d.slot_num = item.get("slot_num")
                    d.desc = item.get("desc", "")
                    d.icon_type = item.get("icon_type", "can")
                    d.category = item.get("category", "Drinks")
                    d.image = item.get("image")
                    d.unit_weight = item.get("unit_weight", getattr(d, "unit_weight", 250.0))
                    d.tare_weight = item.get("tare_weight", getattr(d, "tare_weight", 50.0))
                    new_slots.append(d)
                else:
                    new_slots.append(
                        Drink(
                            drink_id=item["drink_id"],
                            name=item["name"],
                            price=item["price"],
                            stock=item.get("stock", 10),
                            slot_num=item.get("slot_num"),
                            desc=item.get("desc", ""),
                            icon_type=item.get("icon_type", "can"),
                            category=item.get("category", "Drinks"),
                            image=item.get("image"),
                            unit_weight=item.get("unit_weight", 250.0),
                            tare_weight=item.get("tare_weight", 50.0),
                        )
                    )
            self.dispenser._slots = new_slots
            if hasattr(self, "stock_sensor") and self.stock_sensor is not None:
                self.stock_sensor.calibrateSensors()

        # Validate currently entered slot
        curr = self.entered_slot.get().replace("-", "").strip()
        if len(curr) >= 2:
            if curr not in self.slot_map:
                self.entered_slot.set("--")
                self.selected_product = None
                self._update_preview(None)
            else:
                self.selected_product = self.slot_map[curr]
                self._update_preview(curr)
        else:
            self.selected_product = None
            if not getattr(self, "_dispense_banner_active", False):
                self._update_preview(curr if curr else None)

        # Refresh cards on screen
        if hasattr(self, "cards_inner_frame") and self.cards_inner_frame.winfo_exists():
            self._refresh_product_cards(animated=animate)

    def show_page(self, page_name: str) -> None:
        """Switch view to a specific page frame immediately without animation or screen flicker."""
        self.current_page = page_name
        target = self.pages.get(page_name)
        if target:
            target.place(relx=0, rely=0, relwidth=1, relheight=1, width="", height="")
            target.lift()
        for name, frame in self.pages.items():
            if name != page_name:
                frame.place_forget()
        if page_name == "catalogue":
            self.root.focus_set()
            self.sync_products_from_json(animate=False)
        elif page_name == "payment":
            self._refresh_payment_page()
        elif page_name == "success":
            self._refresh_success_page()
            self._start_success_countdown()

    def transition_to_page(
        self,
        target_page: str,
        direction: str = "left",
        duration_ms: int = 240,
        steps: int = 16,
    ) -> None:
        """
        Smooth sliding transition between pages using relative positioning without screen flicker.
        - direction='left': current page slides all the way to the left (-1.0 relx), new page enters from right (1.0 -> 0.0 relx).
        - direction='right': current page slides to the right (1.0 relx), new page enters from left (-1.0 -> 0.0 relx).
        """
        if getattr(self, "_is_transitioning", False):
            return
        if target_page not in self.pages or target_page == self.current_page:
            return

        current_frame = self.pages.get(self.current_page)
        target_frame = self.pages[target_page]
        if not current_frame:
            self.show_page(target_page)
            return

        self._is_transitioning = True
        self.target_page = target_page

        # Pre-render target page content before sliding
        if target_page == "payment":
            self._refresh_payment_page()
        elif target_page == "catalogue":
            self.sync_products_from_json(animate=False)
            self.root.focus_force()
            self.root.focus_set()
        elif target_page == "success":
            self._refresh_success_page()
        elif target_page == "cancelled":
            self._refresh_cancelled_page()

        if direction == "left":
            start_cur = 0.0
            end_cur = -1.0
            start_tgt = 1.0
            end_tgt = 0.0
        else:
            start_cur = 0.0
            end_cur = 1.0
            start_tgt = -1.0
            end_tgt = 0.0

        # Seamless setup without unmapping:
        # current_frame is already active at (0, 0); place target_frame at its starting position and lift it
        current_frame.place(relx=start_cur, rely=0, relwidth=1, relheight=1, width="", height="")
        target_frame.place(relx=start_tgt, rely=0, relwidth=1, relheight=1, width="", height="")
        target_frame.lift()

        step_delay = max(10, duration_ms // steps)

        def step_anim(step: int) -> None:
            if step >= steps:
                # Snap target frame cleanly to (0, 0) without unmapping/place_forget!
                target_frame.place_configure(relx=0.0, rely=0, relwidth=1, relheight=1, width="", height="")
                target_frame.lift()
                # Only unmap the old current_frame now that target_frame fully covers the viewport
                current_frame.place_forget()
                self.current_page = target_page
                self._is_transitioning = False
                if target_page == "catalogue":
                    self.root.focus_force()
                    self.root.focus_set()
                    self.root.after(60, lambda: (self.root.focus_force(), self.root.focus_set()))
                elif target_page == "success":
                    self.root.focus_force()
                    self.root.focus_set()
                    self._start_success_countdown()
                elif target_page == "cancelled":
                    self.root.focus_force()
                    self.root.focus_set()
                    self._start_cancelled_countdown()
                return

            t = (step + 1) / steps
            # Smooth cubic easeInOut curve: 3t^2 - 2t^3
            ease = t * t * (3.0 - 2.0 * t)

            cur_relx = start_cur + (end_cur - start_cur) * ease
            tgt_relx = start_tgt + (end_tgt - start_tgt) * ease

            if current_frame.winfo_exists():
                current_frame.place_configure(relx=cur_relx)
            if target_frame.winfo_exists():
                target_frame.place_configure(relx=tgt_relx)

            self.root.after(step_delay, lambda: step_anim(step + 1))

        self.root.after(step_delay, lambda: step_anim(0))

    # =======================================================================
    # Micro-Animations & Tactile Interactive Effects
    # =======================================================================
    def _safe_config(self, widget: Optional[tk.Widget], **kwargs) -> None:
        """Safely configures widget only if it currently exists on screen."""
        if widget is not None:
            try:
                if widget.winfo_exists():
                    widget.config(**kwargs)
            except Exception:
                pass

    def _attach_button_animation(
        self,
        btn: tk.Button,
        normal_bg: str = BTN_BG,
        normal_fg: str = BTN_FG,
        hover_bg: str = CLR_WHITE,
        hover_fg: str = CLR_DEEP_PURPLE,
        press_bg: str = CLR_WHITE,
    ) -> None:
        """Attaches buttery-smooth hover illumination and tactile press feedback."""
        def on_enter(e):
            if btn.cget("state") != tk.DISABLED:
                btn.config(bg=hover_bg, fg=hover_fg)

        def on_leave(e):
            if btn.cget("state") != tk.DISABLED:
                btn.config(bg=normal_bg, fg=normal_fg)

        def on_press(e):
            if btn.cget("state") != tk.DISABLED:
                btn.config(bg=press_bg, relief=tk.SUNKEN)

        def on_release(e):
            if btn.cget("state") != tk.DISABLED:
                self.root.after(100, lambda: self._safe_config(btn, bg=normal_bg, fg=normal_fg, relief=tk.FLAT))

        btn.bind("<Enter>", on_enter, add="+")
        btn.bind("<Leave>", on_leave, add="+")
        btn.bind("<ButtonPress-1>", on_press, add="+")
        btn.bind("<ButtonRelease-1>", on_release, add="+")

    def _animate_lcd_pulse(self) -> None:
        """Flashes the LCD number display text and border on digit entry."""
        if hasattr(self, "lcd_display"):
            self.lcd_display.config(fg=CLR_WHITE)
            self.root.after(110, lambda: self._safe_config(self.lcd_display, fg=CLR_LIME))
        if hasattr(self, "lcd_frame"):
            self.lcd_frame.config(highlightbackground=CLR_LIME, highlightthickness=2)
            self.root.after(160, lambda: self._safe_config(self.lcd_frame, highlightthickness=0))

    def _guide_to_keypad(self, slot_num: str) -> None:
        """Visual guidance highlighting the keypad prompt when a user attempts to click a product card."""
        self._animate_lcd_pulse()
        if hasattr(self, "typing_badge") and self.typing_badge.winfo_exists():
            self.typing_badge.config(fg=CLR_WHITE)
            self.root.after(200, lambda: self._safe_config(self.typing_badge, fg=CLR_LIME))

    def _highlight_active_card(self, active_slot: Optional[str]) -> None:
        """Smoothly shifts active glowing border to the currently typed slot card (Only when full 2 digits typed)."""
        normalized = active_slot if (active_slot and len(active_slot) >= 2) else ""
        for slot, card in list(self.card_widgets.items()):
            if slot == normalized:
                # Active flash pulse on card
                self._safe_config(card, highlightbackground=CLR_WHITE, highlightthickness=3)
                self.root.after(90, lambda c=card: self._safe_config(c, highlightbackground=CLR_LIME, highlightthickness=3))
            else:
                self._safe_config(card, highlightbackground=CLR_DEEP_PURPLE, highlightthickness=2)

    def _start_typing_heartbeat(self) -> None:
        """Subtle blinking heartbeat on the TYPING ACTIVE label for a living kiosk feel."""
        try:
            if not hasattr(self, "root") or not self.root.winfo_exists():
                return
            if hasattr(self, "typing_badge") and self.typing_badge.winfo_exists():
                self._typing_blink_state = not getattr(self, "_typing_blink_state", False)
                self._safe_config(
                    self.typing_badge,
                    fg=CLR_LIME if self._typing_blink_state else CLR_DARK_GREEN,
                )
            self._heartbeat_after_id = self.root.after(650, self._start_typing_heartbeat)
        except Exception:
            pass

    # =======================================================================
    # PAGE 1: Product Selection Catalogue (Box Grid & Keyboard Input)
    # =======================================================================
    def _build_page1_catalogue(self) -> None:
        """Constructs the full Page 1 layout."""
        page = tk.Frame(self.container, bg=BG_APP)
        self.pages["catalogue"] = page

        # 1. Top Header Bar (Color #3A0C51)
        self._build_header(page)

        # 2. Middle Background Area (Between Top and Bottom Bars: Color #D883FF)
        middle_area = tk.Frame(page, bg=BG_MIDDLE)
        middle_area.pack(fill=tk.BOTH, expand=True)

        content_split = tk.Frame(middle_area, bg=BG_MIDDLE)
        content_split.pack(fill=tk.BOTH, expand=True, padx=12, pady=6)

        # Left Column: Scrollable Product Card Showcase Boxes
        left_box = tk.Frame(content_split, bg=BG_MIDDLE)
        left_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

        self._build_product_grid(left_box)

        # Right Column: Selection Console Panel (Physical Keyboard Input)
        right_panel = tk.Frame(content_split, bg=BG_CARD, width=340, padx=14, pady=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)

        self._build_selection_panel(right_panel)

        # 3. Bottom Status Bar (Footer: Color #3A0C51)
        self._build_footer(page)

    def _build_header(self, parent: tk.Frame) -> None:
        """Top banner with university logo, tagline and step badge (Background: #3A0C51)."""
        header = tk.Frame(parent, bg=BG_APP, height=65, padx=20)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # Brand Logo (Edge Hill University)
        brand_frame = tk.Frame(header, bg=BG_APP)
        brand_frame.pack(side=tk.LEFT, fill=tk.Y)

        logo_path = os.path.join(os.path.dirname(__file__), "assets", "edge_hill_logo.png")
        if os.path.exists(logo_path):
            self.header_logo = tk.PhotoImage(file=logo_path)
            logo_lbl = tk.Label(
                brand_frame,
                image=self.header_logo,
                bg=BG_APP,
            )
            logo_lbl.pack(side=tk.LEFT, pady=10)
        else:
            # Fallback text if logo file is missing
            tk.Label(
                brand_frame,
                text="Edge Hill University",
                font=("Helvetica", 18, "bold"),
                fg=CLR_WHITE,
                bg=BG_APP,
            ).pack(side=tk.LEFT, pady=16)

        tk.Label(
            brand_frame,
            text="• Campus Vending Machine",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LILAC,
            bg=BG_APP,
        ).pack(side=tk.LEFT, padx=14, pady=16)

        # Step Indicator Badge (Button style: #BAEF2D)
        step_badge = tk.Label(
            header,
            text="STEP 1: SELECT DRINK",
            font=("Helvetica", 10, "bold"),
            fg=BTN_FG,
            bg=BTN_BG,
            padx=12,
            pady=4,
        )
        step_badge.pack(side=tk.RIGHT, pady=16)

    def _build_product_grid(self, parent: tk.Frame) -> None:
        """Container hosting product card boxes in a 3x3 responsive grid without scrollbar (Background: #D883FF)."""
        self.cards_inner_frame = tk.Frame(parent, bg=BG_MIDDLE)
        self.cards_inner_frame.pack(fill=tk.BOTH, expand=True)
        self.grid_canvas = None

        self.cards_inner_frame.bind("<Button-1>", lambda e: self.root.focus_set(), add="+")
        self._refresh_product_cards(animated=False)

    def _refresh_product_cards(self, animated: bool = True) -> None:
        """Populates the grid with all drink showcase boxes loaded from products.json."""
        # Cancel any queued card generation callbacks to prevent duplicate cards
        for after_id in getattr(self, "_pending_card_after_ids", []):
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        self._pending_card_after_ids = []

        fresh_catalogue = load_catalogue_data()
        if fresh_catalogue is not None:
            self.catalogue = fresh_catalogue
            self.slot_map = {item["slot_num"]: item for item in self.catalogue}

        for widget in self.cards_inner_frame.winfo_children():
            widget.destroy()

        self.card_widgets.clear()
        self.card_pills.clear()

        # Handle empty catalogue edge case gracefully
        if not self.catalogue:
            empty_box = tk.Frame(
                self.cards_inner_frame,
                bg=BG_CARD,
                padx=24,
                pady=30,
                highlightthickness=2,
                highlightbackground=CLR_LILAC,
            )
            empty_box.grid(row=0, column=0, columnspan=3, padx=20, pady=40, sticky="ew")
            tk.Label(
                empty_box,
                text="⚠️ No Products Currently Available",
                font=("Helvetica", 14, "bold"),
                fg=CLR_LIME,
                bg=BG_CARD,
            ).pack(pady=(0, 6))
            tk.Label(
                empty_box,
                text="Please add beverage items to data/products.json to stock the machine.",
                font=("Helvetica", 11),
                fg=CLR_WHITE,
                bg=BG_CARD,
            ).pack()
            self.cards_inner_frame.update_idletasks()
            return

        columns = 3
        rows = (len(self.catalogue) + columns - 1) // columns
        for index, prod in enumerate(self.catalogue):
            r = index // columns
            c = index % columns
            if animated:
                # Staggered entrance: reveals each card with 20ms delay for a fluid cascade
                after_id = self.root.after(
                    index * 20,
                    lambda p=prod, row=r, col=c: self._safe_create_card(p, row, col)
                )
                self._pending_card_after_ids.append(after_id)
            else:
                self._create_product_card(self.cards_inner_frame, prod, r, c)

        for col in range(columns):
            self.cards_inner_frame.columnconfigure(col, weight=1, uniform="card_col")
        for row in range(max(1, rows)):
            self.cards_inner_frame.rowconfigure(row, weight=1, uniform="card_row")

        self.cards_inner_frame.update_idletasks()

    def _safe_create_card(self, prod: Dict, row: int, col: int) -> None:
        """Safely creates card only if container frame exists."""
        try:
            if hasattr(self, "cards_inner_frame") and self.cards_inner_frame.winfo_exists():
                self._create_product_card(self.cards_inner_frame, prod, row, col)
        except Exception:
            pass

    def _create_product_card(self, parent: tk.Frame, prod: Dict, row: int, col: int) -> None:
        """Builds a display showcase box for a beverage (Selection via physical keyboard only)."""
        stock = 0
        drink_obj = self.dispenser.getDrink(prod["drink_id"])
        if drink_obj:
            stock = drink_obj.stock

        in_stock = stock > 0
        slot_num = prod["slot_num"]
        curr_entered = self.entered_slot.get().replace("-", "").strip()
        is_selected = (len(curr_entered) >= 2 and curr_entered == slot_num)

        # Outer card frame (Display showcase box - Background: #3A0C51)
        card = tk.Frame(
            parent,
            bg=BG_CARD,
            padx=8,
            pady=4,
            relief=tk.FLAT,
            highlightthickness=3 if is_selected else 2,
            highlightbackground=CLR_LIME if is_selected else CLR_DEEP_PURPLE,
        )
        card.grid(row=row, column=col, padx=4, pady=3, sticky="nsew")
        self.card_widgets[slot_num] = card

        # Top row: Slot Number Badge + Stock Pill
        top_row = tk.Frame(card, bg=BG_CARD)
        top_row.pack(side=tk.TOP, fill=tk.X, pady=(2, 3))

        # Prominent Product Number Badge (Button color: #BAEF2D)
        slot_badge = tk.Label(
            top_row,
            text=f"No. {prod['slot_num']}",
            font=("Menlo", 13, "bold"),
            fg=BTN_FG,
            bg=BTN_BG,
            padx=8,
            pady=2,
        )
        slot_badge.pack(side=tk.LEFT)

        # Stock indicator pill
        stock_text = f"Stock: {stock}" if in_stock else "SOLD OUT"
        stock_color = CLR_LIME if in_stock else CLR_LILAC
        stock_pill = tk.Label(
            top_row,
            text=stock_text,
            font=("Helvetica", 11, "bold"),
            fg=stock_color,
            bg=BG_CARD,
        )
        stock_pill.pack(side=tk.RIGHT)

        # Price Display (Anchored at card bottom)
        price_pounds = f"£{prod['price'] / 100:.2f}"
        price_lbl = tk.Label(
            card,
            text=f"{price_pounds}  ({prod['price']}p)",
            font=("Helvetica", 13, "bold"),
            fg=CLR_LIME if in_stock else CLR_LILAC,
            bg=BG_CARD,
        )
        price_lbl.pack(side=tk.BOTTOM, pady=(0, 4))

        # Product Name (Anchored right above price)
        name_lbl = tk.Label(
            card,
            text=prod["name"],
            font=("Helvetica", 15, "bold"),
            fg=CLR_WHITE if in_stock else CLR_LILAC,
            bg=BG_CARD,
            anchor="center",
        )
        name_lbl.pack(side=tk.BOTTOM, fill=tk.X, pady=(2, 0))

        # Center Product Showcase Canvas (Photograph from assets/ with responsive fill)
        canvas = tk.Canvas(
            card,
            width=140,
            height=76,
            bg=CLR_WHITE,
            highlightthickness=1,
            highlightbackground=CLR_LILAC,
        )
        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=3)
        render_product_artwork(
            canvas=canvas,
            prod=prod,
            width=140,
            height=76,
            photo_cache=self._product_images,
            default_bg=CLR_WHITE,
            fallback_bg=BG_CARD,
        )

        canvas._last_render_dims = (0, 0)
        canvas._resize_after_id = None

        def on_canvas_configure(event):
            cw = event.width
            ch = event.height
            if cw < 20 or ch < 20:
                return
            last_w, last_h = getattr(canvas, "_last_render_dims", (0, 0))
            if abs(cw - last_w) < 6 and abs(ch - last_h) < 6:
                return

            def do_render():
                if not canvas.winfo_exists():
                    return
                act_w = canvas.winfo_width()
                act_h = canvas.winfo_height()
                if act_w < 20 or act_h < 20:
                    return
                canvas._last_render_dims = (act_w, act_h)
                render_product_artwork(
                    canvas=canvas,
                    prod=prod,
                    width=act_w,
                    height=act_h,
                    photo_cache=self._product_images,
                    default_bg=CLR_WHITE,
                    fallback_bg=BG_CARD,
                )

            if last_w == 0 and last_h == 0:
                do_render()
            else:
                if getattr(canvas, "_resize_after_id", None):
                    try:
                        self.root.after_cancel(canvas._resize_after_id)
                    except Exception:
                        pass
                canvas._resize_after_id = self.root.after(35, do_render)

        canvas.bind("<Configure>", on_canvas_configure)

        # Clicking on display card reminds user to use keypad (Keypad-only control)
        def on_card_click(event=None):
            self.root.focus_set()
            self._guide_to_keypad(slot_num)

        for w in (card, canvas, name_lbl, price_lbl, slot_badge, stock_pill):
            w.bind("<Button-1>", on_card_click)

    # =======================================================================
    # =======================================================================
    # Right Column: Selection Console (Touch Keypad & Physical Keyboard Input)
    # =======================================================================
    def _build_selection_panel(self, parent: tk.Frame) -> None:
        """Right-hand panel featuring digital LCD display and enlarged item preview."""
        # Panel Title
        tk.Label(
            parent,
            text="SELECTION CONSOLE",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LILAC,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 6))

        # Digital LCD Number Box
        self.lcd_frame = tk.Frame(parent, bg=BG_SCREEN, padx=10, pady=3, relief=tk.SUNKEN, bd=2)
        self.lcd_frame.pack(fill=tk.X, pady=(0, 6))

        top_lcd = tk.Frame(self.lcd_frame, bg=BG_SCREEN)
        top_lcd.pack(fill=tk.X)

        tk.Label(
            top_lcd,
            text="ENTERED SLOT",
            font=("Helvetica", 9, "bold"),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
        ).pack(side=tk.LEFT)

        self.typing_badge = tk.Label(
            top_lcd,
            text="⌨️ ACTIVE",
            font=("Helvetica", 9, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        self.typing_badge.pack(side=tk.RIGHT)

        self.lcd_display = tk.Label(
            self.lcd_frame,
            textvariable=self.entered_slot,
            font=("Menlo", 24, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
            anchor="center",
        )
        self.lcd_display.pack(fill=tk.X, pady=2)

        # Live Selected Preview Box (Showcase)
        self.preview_box = tk.Frame(
            parent,
            bg=BG_SCREEN,
            padx=10,
            pady=8,
            relief=tk.RIDGE,
            bd=2,
            highlightbackground=CLR_LILAC,
        )
        self.preview_box.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            self.preview_box,
            text="🔍 ITEM PREVIEW",
            font=("Helvetica", 10, "bold"),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
        ).pack(anchor="w", pady=(0, 2))

        # Artwork Canvas inside preview (Enlarged)
        self.preview_canvas = tk.Canvas(
            self.preview_box,
            width=165,
            height=110,
            bg=BG_SCREEN,
            highlightthickness=0,
        )
        self.preview_canvas.pack(anchor="center", pady=3)

        self.preview_name_lbl = tk.Label(
            self.preview_box,
            text="No Drink Selected",
            font=("Helvetica", 13, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
            anchor="center",
        )
        self.preview_name_lbl.pack(fill=tk.X, pady=(2, 0))

        self.preview_price_lbl = tk.Label(
            self.preview_box,
            text="Enter slot number to order",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
            anchor="center",
        )
        self.preview_price_lbl.pack(fill=tk.X, pady=(1, 0))

        self.preview_stock_lbl = tk.Label(
            self.preview_box,
            text="",
            font=("Helvetica", 10, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
            anchor="center",
        )
        self.preview_stock_lbl.pack(fill=tk.X)

        # Big Confirm Purchase Button (Button color: #BAEF2D)
        self.confirm_btn = tk.Button(
            parent,
            text="✅ CONFIRM SELECTION (Enter)",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            activebackground=CLR_WHITE,
            activeforeground=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            pady=8,
            cursor="hand2",
            command=self._on_confirm_selection,
        )
        self.confirm_btn.pack(fill=tk.X, pady=(0, 4))
        self._attach_button_animation(self.confirm_btn)

        # Clear Button (Button color: #BAEF2D)
        self.clear_btn = tk.Button(
            parent,
            text="🗑️ CLEAR SELECTION (Esc)",
            font=("Helvetica", 12, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            activebackground=CLR_WHITE,
            activeforeground=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            pady=7,
            cursor="hand2",
            command=self._handle_clear,
        )
        self.clear_btn.pack(fill=tk.X)
        self._attach_button_animation(self.clear_btn)

    # =======================================================================
    # Keyboard Event Binding & Handlers
    # =======================================================================
    def _bind_keyboard_events(self) -> None:
        """Binds global physical keyboard listeners."""
        self.root.bind("<Key>", self._on_physical_key)
        self.root.focus_force()
        self.root.focus_set()

    def _on_physical_key(self, event: tk.Event) -> None:
        """Handles physical keyboard keypresses."""
        # If an Entry widget is currently active (e.g. typing member ID), let it receive typing
        if isinstance(getattr(event, "widget", None), (tk.Entry, ttk.Entry)):
            return

        # If a modal dialog is currently active, let the modal handle its own keys
        if getattr(self, "_active_modal", None) is not None:
            try:
                if self._active_modal.winfo_exists():
                    return
                else:
                    self._active_modal = None
            except Exception:
                self._active_modal = None

        key = event.keysym
        char = event.char

        # Active page resolution (if sliding back to catalogue, accept catalogue inputs immediately)
        active_page = getattr(self, "target_page", "catalogue") if getattr(self, "_is_transitioning", False) else getattr(self, "current_page", "catalogue")

        # Keypad Control on Page 2 (Payment Page)
        if active_page == "payment":
            if key in ("Escape", "KP_4") or char in ("4", "c", "C"):
                if hasattr(self, "back_btn") and self.back_btn.winfo_exists():
                    self.back_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    self.root.after(120, lambda: self._safe_config(self.back_btn, bg=BTN_BG, relief=tk.FLAT))
                self.root.after(130, self._on_cancel_payment)
                return
            elif char == "1" or key in ("KP_1", "1"):
                if hasattr(self, "scan_loyalty_btn") and self.scan_loyalty_btn.winfo_exists():
                    self.scan_loyalty_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    self.root.after(120, lambda: self._safe_config(self.scan_loyalty_btn, bg=BTN_BG, relief=tk.FLAT))
                self.root.after(130, self._open_loyalty_scan_dialog)
                return
            elif char == "2" or key in ("KP_2", "2"):
                if not getattr(self, "cash_enabled", True):
                    return
                if hasattr(self, "cash_btn") and self.cash_btn.winfo_exists():
                    self.cash_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    self.root.after(120, lambda: self._safe_config(self.cash_btn, bg=BTN_BG, relief=tk.FLAT))
                self.root.after(130, self._on_choose_cash)
                return
            elif char == "3" or key in ("KP_3", "3"):
                if not getattr(self, "card_enabled", True):
                    return
                if hasattr(self, "card_btn") and self.card_btn.winfo_exists():
                    self.card_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    self.root.after(120, lambda: self._safe_config(self.card_btn, bg=BTN_BG, relief=tk.FLAT))
                self.root.after(130, self._on_choose_card)
                return
            return

        # Keypad Control on Page 3 (Order Success & Dispense Page)
        if active_page == "success":
            if key in ("Return", "KP_Enter", "Escape", "space", "KP_1", "1") or char in ("1", "c", "C"):
                if hasattr(self, "return_home_btn") and self.return_home_btn.winfo_exists():
                    self.return_home_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    self.root.after(120, lambda: self._safe_config(self.return_home_btn, bg=BTN_BG, relief=tk.FLAT))
                self.root.after(130, self._return_to_catalogue)
                return
            elif (char in "0123456789" and len(char) == 1) or key in (
                "KP_0", "KP_1", "KP_2", "KP_3", "KP_4", "KP_5", "KP_6", "KP_7", "KP_8", "KP_9"
            ):
                digit = char if (char in "0123456789" and len(char) == 1) else key.replace("KP_", "")
                self._return_to_catalogue()
                self._handle_digit_input(digit)
                return
            return

        # Keypad Control on Page 4 (Order Cancelled & Refund Page)
        if active_page == "cancelled":
            if key in ("Return", "KP_Enter", "Escape", "space") or char in ("c", "C"):
                if hasattr(self, "cancelled_home_btn") and self.cancelled_home_btn.winfo_exists():
                    self.cancelled_home_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    self.root.after(120, lambda: self._safe_config(self.cancelled_home_btn, bg=BTN_BG, relief=tk.FLAT))
                self.root.after(130, self._return_to_catalogue_from_cancelled)
                return
            return

        # Keypad Control on Page 1 (Catalogue Page)
        # Numbers 0-9 (standard keys or numeric keypad)
        if char in "0123456789" and len(char) == 1:
            self._handle_digit_input(char)
        elif key in ("KP_0", "KP_1", "KP_2", "KP_3", "KP_4", "KP_5", "KP_6", "KP_7", "KP_8", "KP_9"):
            digit = key.replace("KP_", "")
            self._handle_digit_input(digit)
        elif key in ("BackSpace", "Delete"):
            self._handle_backspace()
        elif key == "Escape":
            self._handle_clear()
        elif key in ("Return", "KP_Enter"):
            # Animate confirm button on Enter keypress
            if hasattr(self, "confirm_btn"):
                self.confirm_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                self.root.after(120, lambda: self._safe_config(self.confirm_btn, bg=BTN_BG, relief=tk.FLAT))
            self.root.after(130, self._on_confirm_selection)
        elif char in ("o", "O"):
            if hasattr(self, "option_btn") and self.option_btn.winfo_exists():
                self.option_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                self.root.after(120, lambda: self._safe_config(self.option_btn, bg=BTN_BG, relief=tk.FLAT))
            self.root.after(130, self._open_options_dialog)

    def _handle_digit_input(self, digit: str) -> None:
        """Processes digit typed from physical keyboard with tactile visual feedback."""
        self._dispense_banner_active = False
        # Cancel any pending idle dispense message restore
        if getattr(self, "_dispense_restore_after_id", None):
            try:
                self.root.after_cancel(self._dispense_restore_after_id)
            except Exception:
                pass
            self._dispense_restore_after_id = None

        curr = self.entered_slot.get().replace("-", "").strip()
        # If already 2 digits or empty, start fresh with new digit
        if len(curr) >= 2 or not curr:
            new_val = digit
        else:
            new_val = curr + digit

        self.entered_slot.set(new_val)
        self._highlight_active_card(new_val)
        self._animate_lcd_pulse()
        self._update_preview(new_val)

    def _handle_backspace(self) -> None:
        """Removes the last digit on BackSpace with tactile feedback."""
        curr = self.entered_slot.get().replace("-", "").strip()
        if len(curr) > 1:
            new_val = curr[:-1]
            self.entered_slot.set(new_val)
            self._highlight_active_card(new_val)
            self._animate_lcd_pulse()
            self._update_preview(new_val)
        else:
            self._handle_clear()

    def _handle_clear(self) -> None:
        """Clears slot selection back to default on Esc key with button animation."""
        self._dispense_banner_active = False
        if hasattr(self, "clear_btn") and self.clear_btn.winfo_exists():
            self.clear_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
            self.root.after(120, lambda: self._safe_config(self.clear_btn, bg=BTN_BG, relief=tk.FLAT))
        self.entered_slot.set("--")
        self._highlight_active_card(None)
        self._animate_lcd_pulse()
        self._update_preview(None)

    def _update_preview(self, slot_num: Optional[str]) -> None:
        """Updates the preview display with animated feedback (Requires full 2-digit slot)."""
        if not slot_num or slot_num == "--":
            self.selected_product = None
            if hasattr(self, "preview_canvas"):
                self.preview_canvas.delete("all")
                self.preview_canvas.config(bg=BG_SCREEN, highlightthickness=0)
            self.preview_name_lbl.config(text="No Drink Selected", fg=CLR_WHITE)
            self.preview_price_lbl.config(text="Enter slot number to order", fg=CLR_LILAC)
            self.preview_stock_lbl.config(text="")
            return

        # If user has only typed 1 digit so far, do NOT display the product yet
        if len(slot_num) < 2:
            self.selected_product = None
            if hasattr(self, "preview_canvas"):
                self.preview_canvas.delete("all")
                self.preview_canvas.config(bg=BG_SCREEN, highlightthickness=0)
            self.preview_name_lbl.config(text="Typing Slot Number...", fg=CLR_WHITE)
            self.preview_price_lbl.config(text="Type 2nd digit to complete (e.g. 01)", fg=CLR_LILAC)
            self.preview_stock_lbl.config(text="")
            return

        if slot_num in self.slot_map:
            prod = self.slot_map[slot_num]
            self.selected_product = prod
            drink_obj = self.dispenser.getDrink(prod["drink_id"])
            stock = drink_obj.stock if drink_obj else 0

            # Subtle glow feedback on preview box
            if hasattr(self, "preview_box"):
                self.preview_box.config(highlightbackground=CLR_LIME, highlightthickness=2)
                self.root.after(180, lambda: self._safe_config(self.preview_box, highlightbackground=CLR_LILAC, highlightthickness=1))

            # Draw drink photo or fallback artwork in preview canvas
            if hasattr(self, "preview_canvas"):
                render_product_artwork(
                    canvas=self.preview_canvas,
                    prod=prod,
                    width=165,
                    height=110,
                    photo_cache=self._product_images,
                    default_bg=CLR_WHITE,
                    fallback_bg=BG_SCREEN,
                )

            if stock > 0:
                self.preview_name_lbl.config(
                    text=f"✅ {prod['name']} (No. {prod['slot_num']})",
                    fg=CLR_LIME,
                )
                self.preview_price_lbl.config(
                    text=f"Price: £{prod['price'] / 100:.2f}  ({prod['price']}p)",
                    fg=CLR_WHITE,
                )
                self.preview_stock_lbl.config(
                    text=f"In Stock ({stock} available)",
                    fg=CLR_LIME,
                )
            else:
                self.preview_name_lbl.config(
                    text=f"❌ {prod['name']} (SOLD OUT)",
                    fg=CLR_LILAC,
                )
                self.preview_price_lbl.config(
                    text="Temporarily Out of Stock",
                    fg=CLR_LILAC,
                )
                self.preview_stock_lbl.config(
                    text="❌ Ordering Unavailable",
                    fg=CLR_LILAC,
                )
        else:
            self.selected_product = None
            if hasattr(self, "preview_canvas"):
                self.preview_canvas.delete("all")
                self.preview_canvas.config(bg=BG_SCREEN, highlightthickness=0)
            self.preview_name_lbl.config(text=f"❌ Slot '{slot_num}' Not Found", fg=CLR_LILAC)
            self.preview_price_lbl.config(text="Please check slot number on product card", fg=CLR_WHITE)
            self.preview_stock_lbl.config(text="")

    def _flash_input_notice(self, msg: str) -> None:
        """Shows non-blocking notice without stealing keyboard focus or popping up OS dialogs."""
        self._animate_lcd_pulse()
        if hasattr(self, "preview_price_lbl") and self.preview_price_lbl.winfo_exists():
            orig_text = self.preview_price_lbl.cget("text")
            orig_fg = self.preview_price_lbl.cget("fg")
            self.preview_price_lbl.config(text=f"⚠️ {msg}", fg=CLR_LILAC)
            self.root.after(2600, lambda: self._safe_config(self.preview_price_lbl, text=orig_text, fg=orig_fg))
        if hasattr(self, "footer_tip_lbl") and self.footer_tip_lbl.winfo_exists():
            orig_tip = self.footer_tip_lbl.cget("text")
            orig_tfg = self.footer_tip_lbl.cget("fg")
            self.footer_tip_lbl.config(text=f"⚠️ {msg}", fg=CLR_LILAC)
            self.root.after(2600, lambda: self._safe_config(self.footer_tip_lbl, text=orig_tip, fg=orig_tfg))
        self.root.focus_force()
        self.root.focus_set()

    def _on_confirm_selection(self) -> None:
        """Validates selection and proceeds to payment with button press animation."""
        if hasattr(self, "confirm_btn"):
            self.confirm_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
            self.root.after(120, lambda: self._safe_config(self.confirm_btn, bg=BTN_BG, relief=tk.FLAT))
        slot_text = self.entered_slot.get().replace("-", "").strip()
        if not slot_text:
            max_slot = f"{len(self.catalogue):02d}" if self.catalogue else "09"
            self._flash_input_notice(f"Please type a slot number (01-{max_slot}) first.")
            return

        if len(slot_text) < 2:
            max_slot = f"{len(self.catalogue):02d}" if self.catalogue else "09"
            self._flash_input_notice(f"Please type full 2-digit slot number (01-{max_slot}).")
            return

        if slot_text not in self.slot_map:
            self._flash_input_notice(f"Slot '{slot_text}' not found. Check product card.")
            return

        prod = self.slot_map[slot_text]
        drink_id = prod["drink_id"]

        if not self.dispenser.isAvailable(drink_id):
            self._flash_input_notice(f"Sorry, '{prod['name']}' is temporarily sold out.")
            return

        self.controller.selectDrink(drink_id)
        self.selected_product = prod
        self.scanned_member = None
        if hasattr(self, "loyalty_scanner"):
            self.loyalty_scanner._last_scanned = None

        # Trigger smooth slide to left transition to Page 2 (old page slides left until out of screen)
        self.transition_to_page("payment", direction="left")

    def _build_footer(self, parent: tk.Frame) -> None:
        """Bottom status and instruction bar (Background: #3A0C51)."""
        footer = tk.Frame(parent, bg=BG_APP, height=40, padx=16)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        # Option button at bottom-left, on the same bar as the tip text
        self.option_btn = tk.Button(
            footer,
            text="⚙️ Option",
            font=("Helvetica", 10, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            activebackground=CLR_WHITE,
            activeforeground=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=2,
            cursor="hand2",
            command=self._open_options_dialog,
        )
        self.option_btn.pack(side=tk.LEFT, pady=6)
        self._attach_button_animation(self.option_btn)

        self.footer_tip_lbl = tk.Label(
            footer,
            text="💡 Tip: Check the slot number on any drink box and type it on your keyboard to order.",
            font=("Helvetica", 10),
            fg=CLR_WHITE,
            bg=BG_APP,
        )
        self.footer_tip_lbl.pack(side=tk.LEFT, padx=(12, 0), pady=10)

        # Current Time label
        self.time_lbl = tk.Label(
            footer,
            text=time.strftime("%H:%M:%S"),
            font=("Menlo", 10, "bold"),
            fg=CLR_LIME,
            bg=BG_APP,
        )
        self.time_lbl.pack(side=tk.RIGHT, pady=10)

        def update_clock():
            try:
                if hasattr(self, "root") and self.root.winfo_exists() and hasattr(self, "time_lbl") and self.time_lbl.winfo_exists():
                    self.time_lbl.config(text=time.strftime("%Y-%m-%d  %H:%M:%S"))
                    self._clock_after_id = self.root.after(1000, update_clock)
            except Exception:
                pass

        update_clock()

    def _open_options_dialog(self) -> None:
        """Opens the full Management & Options Dashboard with 4 vertical tabs."""
        if getattr(self, "_active_modal", None) is not None:
            try:
                if self._active_modal.winfo_exists():
                    self._active_modal.lift()
                    self._active_modal.focus_force()
                    return
            except Exception:
                pass

        dialog = tk.Toplevel(self.root)
        self._active_modal = dialog
        dialog.title("Vending Machine Management & Options")

        # Responsive window dimensions - enlarged for optimal readability & dashboard layout
        sw = max(1100, self.root.winfo_screenwidth())
        sh = max(750, self.root.winfo_screenheight())
        dw = min(1220, max(1040, sw - 40))
        dh = min(820, max(720, sh - 60))
        dialog.geometry(f"{dw}x{dh}")
        dialog.minsize(1000, 680)
        dialog.configure(bg=BG_APP)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center on parent window
        dialog.update_idletasks()
        x = max(10, self.root.winfo_x() + (self.root.winfo_width() - dw) // 2)
        y = max(10, self.root.winfo_y() + (self.root.winfo_height() - dh) // 2)
        dialog.geometry(f"+{x}+{y}")

        def on_close():
            try:
                dialog.grab_release()
                dialog.destroy()
            except Exception:
                pass
            self._active_modal = None
            self.root.focus_force()
            self.root.focus_set()
            self.root.after(50, lambda: (self.root.focus_force(), self.root.focus_set()))

        dialog.protocol("WM_DELETE_WINDOW", on_close)
        def on_options_key(event: tk.Event):
            if event.keysym in ("Escape",):
                on_close()

        dialog.bind("<Escape>", lambda e: on_close())
        dialog.bind("<Key>", on_options_key)

        # -----------------------------------------------------------------
        # Treeview Theme Configuration - Scaled Up for Readability
        # -----------------------------------------------------------------
        style = ttk.Style(dialog)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(
            "Opt.Treeview",
            background=BG_SCREEN,
            foreground=CLR_WHITE,
            fieldbackground=BG_SCREEN,
            rowheight=34,
            font=("Helvetica", 12),
        )
        style.configure(
            "Opt.Treeview.Heading",
            background=BG_APP,
            foreground=CLR_LIME,
            font=("Helvetica", 12, "bold"),
        )
        style.map(
            "Opt.Treeview",
            background=[("selected", CLR_LIME)],
            foreground=[("selected", CLR_DEEP_PURPLE)],
        )

        # -----------------------------------------------------------------
        # Header (Top Banner) - Scaled Up
        # -----------------------------------------------------------------
        hdr = tk.Frame(dialog, bg=BG_APP, padx=20, pady=12, height=68)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        hdr_left = tk.Frame(hdr, bg=BG_APP)
        hdr_left.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(
            hdr_left,
            text="⚙️ SYSTEM OPTIONS & MANAGEMENT DASHBOARD",
            font=("Helvetica", 16, "bold"),
            fg=CLR_LIME,
            bg=BG_APP,
        ).pack(anchor="w")

        tk.Label(
            hdr_left,
            text="Edge Hill University Smart Vending — Administration & Hardware Diagnostics",
            font=("Helvetica", 12),
            fg=CLR_LILAC,
            bg=BG_APP,
        ).pack(anchor="w")

        close_btn = tk.Button(
            hdr,
            text="✕ Close (Esc)",
            font=("Helvetica", 12, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            activebackground=CLR_WHITE,
            activeforeground=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=18,
            pady=8,
            cursor="hand2",
            command=on_close,
        )
        close_btn.pack(side=tk.RIGHT, pady=4)
        self._attach_button_animation(close_btn)

        # -----------------------------------------------------------------
        # Main Split: Left Vertical Tabs + Right Content Pane
        # -----------------------------------------------------------------
        main_split = tk.Frame(dialog, bg=BG_MIDDLE)
        main_split.pack(fill=tk.BOTH, expand=True)

        # Left Sidebar (Vertical Navigation Tabs) - Wider & Larger Text
        sidebar = tk.Frame(main_split, bg=BG_APP, width=270, padx=12, pady=14)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="MANAGEMENT TABS",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LILAC,
            bg=BG_APP,
        ).pack(anchor="w", pady=(0, 10))

        # Right Content Area
        content_area = tk.Frame(main_split, bg=BG_MIDDLE, padx=12, pady=12)
        content_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tabs: Dict[str, tk.Frame] = {}
        tab_buttons: Dict[str, tk.Button] = {}

        def select_tab(name: str):
            for tname, frame in tabs.items():
                if tname == name:
                    frame.pack(fill=tk.BOTH, expand=True)
                else:
                    frame.pack_forget()

            for tname, btn in tab_buttons.items():
                if tname == name:
                    btn.config(
                        fg=BTN_FG,
                        font=("Helvetica", 13, "bold"),
                        relief=tk.SOLID,
                        bd=1,
                        highlightthickness=2,
                        highlightbackground=CLR_LIME,
                    )
                else:
                    btn.config(
                        fg=BTN_FG,
                        font=("Helvetica", 13),
                        relief=tk.FLAT,
                        bd=0,
                        highlightthickness=0,
                        highlightbackground=CLR_DEEP_PURPLE,
                    )

            if name == "products":
                refresh_products_view()
            elif name == "cash":
                refresh_cash_view()
            elif name == "payments":
                refresh_payments_view()
            elif name == "transactions":
                refresh_transactions_view()
            elif name == "members":
                refresh_members_view()
            elif name == "logs":
                refresh_logs_view()

        nav_tabs = [
            ("products", "📦 Products & Stock"),
            ("cash", "💵 Cash & Coins"),
            ("payments", "💳 Payment Methods"),
            ("transactions", "🧾 Transaction Records"),
            ("members", "🎖️ Loyalty Members"),
            ("logs", "📋 System & Logs"),
        ]

        for tab_id, tab_label in nav_tabs:
            btn = tk.Button(
                sidebar,
                text=tab_label,
                font=("Helvetica", 13),
                bg=BTN_BG,
                fg=BTN_FG,
                activebackground=CLR_WHITE,
                activeforeground=BTN_FG,
                relief=tk.FLAT,
                bd=0,
                padx=14,
                pady=12,
                anchor="w",
                cursor="hand2",
                command=lambda tid=tab_id: select_tab(tid),
            )
            btn.pack(fill=tk.X, pady=4)
            tab_buttons[tab_id] = btn

        # Sidebar Bottom Info Card
        side_info = tk.Frame(sidebar, bg=BG_SCREEN, padx=12, pady=12)
        side_info.pack(side=tk.BOTTOM, fill=tk.X)

        tk.Label(
            side_info,
            text="SYSTEM SUMMARY",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        ).pack(anchor="w")

        side_summary_lbl = tk.Label(
            side_info,
            text="• State: READY (IDLE)\n• Currency: GBP (£)\n• Timeout: 60s Policy\n• Stripe: Connected",
            font=("Menlo", 10),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
            justify=tk.LEFT,
        )
        side_summary_lbl.pack(anchor="w", pady=(4, 0))

        # =================================================================
        # TAB 1: 📦 Product & Stock Management
        # =================================================================
        tab_products_frame = tk.Frame(content_area, bg=BG_MIDDLE)
        tabs["products"] = tab_products_frame

        # Top Card
        prod_hdr = tk.Frame(tab_products_frame, bg=BG_CARD, padx=14, pady=10)
        prod_hdr.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            prod_hdr,
            text="📦 PRODUCT CATALOGUE & DISPENSER INVENTORY",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            prod_hdr,
            text="Live stock sensor telemetry from data/products.json and dispenser hardware",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_CARD,
        ).pack(anchor="w")

        # Treeview Frame
        prod_tree_frame = tk.Frame(tab_products_frame, bg=BG_CARD, padx=8, pady=8)
        prod_tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        prod_tree = ttk.Treeview(
            prod_tree_frame,
            style="Opt.Treeview",
            columns=("slot", "name", "price", "stock", "weight", "sensor"),
            show="headings",
            height=9,
        )
        prod_tree.heading("slot", text="Slot")
        prod_tree.heading("name", text="Product Name")
        prod_tree.heading("price", text="Price")
        prod_tree.heading("stock", text="Stock")
        prod_tree.heading("weight", text="Row Weight (g)")
        prod_tree.heading("sensor", text="Dual-Sensor Status")

        prod_tree.column("slot", width=65, anchor="center")
        prod_tree.column("name", width=220, anchor="w")
        prod_tree.column("price", width=105, anchor="center")
        prod_tree.column("stock", width=115, anchor="center")
        prod_tree.column("weight", width=160, anchor="center")
        prod_tree.column("sensor", width=195, anchor="center")

        prod_scroll = ttk.Scrollbar(prod_tree_frame, orient=tk.VERTICAL, command=prod_tree.yview)
        prod_tree.configure(yscrollcommand=prod_scroll.set)
        prod_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        prod_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom Edit & Actions Frame
        prod_ctrl = tk.Frame(tab_products_frame, bg=BG_CARD, padx=14, pady=12)
        prod_ctrl.pack(fill=tk.X)

        # Quick Actions Row
        prod_act_row = tk.Frame(prod_ctrl, bg=BG_CARD)
        prod_act_row.pack(fill=tk.X, pady=(0, 8))

        def refresh_products_view():
            prod_tree.delete(*prod_tree.get_children())
            catalogue = load_catalogue_data()
            sensor = getattr(self, "stock_sensor", None)
            for item in catalogue:
                did = item.get("drink_id", "")
                slot = item.get("slot_num", "--")
                name = item.get("name", "Unknown")
                price = item.get("price", 0)
                price_str = f"{price}p"

                if sensor:
                    telem = sensor.verifyStock(did)
                    stock = telem.get("verified_stock", item.get("stock", 0))
                    w_g = telem.get("measured_weight_g", 0.0)
                    w_str = f"{w_g:.0f}g ({telem.get('stock_by_weight')} cans)"
                    sensor_cnt = telem.get("stock_by_sensor")
                    if not telem.get("is_consistent"):
                        st_text = f"⚠️ Mismatch (Beam: {sensor_cnt})"
                    elif stock == 0:
                        st_text = "❌ Empty"
                    elif stock <= 3:
                        st_text = f"⚠️ Low ({stock} cans)"
                    else:
                        st_text = f"✅ Verified ({stock} cans)"
                else:
                    stock = item.get("stock", 0)
                    w_str = f"{stock * 250 + 50:.0f}g"
                    st_text = "✅ In Stock" if stock >= 5 else ("⚠️ Low" if stock > 0 else "❌ Out of Stock")

                stock_str = f"{stock} cans"
                prod_tree.insert("", tk.END, values=(slot, name, price_str, stock_str, w_str, st_text))

        def do_reload_products():
            self._sync_products_from_file(animate=True)
            sensor = getattr(self, "stock_sensor", None)
            if sensor:
                sensor.calibrateSensors()
            refresh_products_view()
            prod_msg_lbl.config(text="✅ Catalogue reloaded successfully from products.json", fg=CLR_LIME)

        def do_restock_all():
            catalogue = load_catalogue_data()
            for item in catalogue:
                item["stock"] = 10
            save_catalogue_data(catalogue)
            # Update dispenser slots
            if hasattr(self, "dispenser") and hasattr(self.dispenser, "_slots"):
                for d in self.dispenser._slots:
                    d.stock = 10
            sensor = getattr(self, "stock_sensor", None)
            if sensor:
                sensor.calibrateSensors()
            self._sync_products_from_file(animate=True)
            refresh_products_view()
            prod_msg_lbl.config(text="✅ All beverage slots replenished to 10 cans", fg=CLR_LIME)

        def do_scan_dual_sensors():
            sensor = getattr(self, "stock_sensor", None)
            if sensor:
                sensor.refresh()
            refresh_products_view()
            prod_msg_lbl.config(text="✅ Scanned row load cells and optical detection sensors", fg=CLR_LIME)

        btn_reload_prod = tk.Button(
            prod_act_row,
            text="🔄 Reload Catalogue",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=do_reload_products,
        )
        btn_reload_prod.pack(side=tk.LEFT, padx=(0, 8))
        self._attach_button_animation(btn_reload_prod)

        btn_restock_all = tk.Button(
            prod_act_row,
            text="➕ Restock All Slots (+10 Cans)",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=do_restock_all,
        )
        btn_restock_all.pack(side=tk.LEFT, padx=(0, 8))
        self._attach_button_animation(btn_restock_all)

        btn_scan_sensors = tk.Button(
            prod_act_row,
            text="⚖️ Scan Weight & Sensors",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=do_scan_dual_sensors,
        )
        btn_scan_sensors.pack(side=tk.LEFT, padx=(0, 8))
        self._attach_button_animation(btn_scan_sensors)

        # Edit Form Row
        edit_row = tk.Frame(prod_ctrl, bg=BG_CARD)
        edit_row.pack(fill=tk.X, pady=(4, 0))

        tk.Label(edit_row, text="Edit Slot:", font=("Helvetica", 11, "bold"), fg=CLR_WHITE, bg=BG_CARD).pack(side=tk.LEFT, padx=(0, 4))
        edit_slot_var = tk.StringVar(value="01")
        ent_slot = tk.Entry(edit_row, textvariable=edit_slot_var, width=4, font=("Helvetica", 11))
        ent_slot.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(edit_row, text="Price (p):", font=("Helvetica", 11, "bold"), fg=CLR_WHITE, bg=BG_CARD).pack(side=tk.LEFT, padx=(0, 4))
        edit_price_var = tk.StringVar(value="150")
        ent_price = tk.Entry(edit_row, textvariable=edit_price_var, width=6, font=("Helvetica", 11))
        ent_price.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(edit_row, text="Stock:", font=("Helvetica", 11, "bold"), fg=CLR_WHITE, bg=BG_CARD).pack(side=tk.LEFT, padx=(0, 4))
        edit_stock_var = tk.StringVar(value="10")
        ent_stock = tk.Entry(edit_row, textvariable=edit_stock_var, width=5, font=("Helvetica", 11))
        ent_stock.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(edit_row, text="Unit Wt (g):", font=("Helvetica", 11, "bold"), fg=CLR_WHITE, bg=BG_CARD).pack(side=tk.LEFT, padx=(0, 4))
        edit_weight_var = tk.StringVar(value="160")
        ent_weight = tk.Entry(edit_row, textvariable=edit_weight_var, width=6, font=("Helvetica", 11))
        ent_weight.pack(side=tk.LEFT, padx=(0, 8))

        def save_product_changes():
            slot_target = edit_slot_var.get().strip()
            try:
                new_p = int(edit_price_var.get().strip())
                new_s = int(edit_stock_var.get().strip())
                new_w = float(edit_weight_var.get().strip())
            except ValueError:
                prod_msg_lbl.config(text="❌ Error: Price/Stock must be ints, Weight float", fg="#FF6B6B")
                return

            catalogue = load_catalogue_data()
            matched = False
            for item in catalogue:
                if str(item.get("slot_num", "")).strip() == slot_target:
                    item["price"] = new_p
                    item["stock"] = new_s
                    item["unit_weight"] = new_w
                    matched = True
                    break

            if matched:
                save_catalogue_data(catalogue)
                if hasattr(self, "dispenser") and hasattr(self.dispenser, "_slots"):
                    for d in self.dispenser._slots:
                        if getattr(d, "slot_num", "") == slot_target:
                            d.price = new_p
                            d.stock = new_s
                            d.unit_weight = new_w
                sensor = getattr(self, "stock_sensor", None)
                if sensor:
                    sensor.calibrateSensors()
                self._sync_products_from_file(animate=True)
                refresh_products_view()
                prod_msg_lbl.config(text=f"✅ Slot {slot_target} updated: {new_p}p, {new_s} cans, {new_w}g", fg=CLR_LIME)
            else:
                prod_msg_lbl.config(text=f"❌ Slot {slot_target} not found", fg="#FF6B6B")

        btn_save_prod = tk.Button(
            edit_row,
            text="💾 Save Item",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=5,
            cursor="hand2",
            command=save_product_changes,
        )
        btn_save_prod.pack(side=tk.LEFT, padx=(4, 0))
        self._attach_button_animation(btn_save_prod)

        prod_msg_lbl = tk.Label(prod_ctrl, text="💡 Tip: Click any row in the table to load it into the editor.", font=("Helvetica", 11), fg=CLR_LILAC, bg=BG_CARD)
        prod_msg_lbl.pack(anchor="w", pady=(6, 0))
        prod_msg_lbl.pack(anchor="w", pady=(6, 0))

        def on_tree_select(e):
            sel = prod_tree.selection()
            if sel:
                vals = prod_tree.item(sel[0], "values")
                edit_slot_var.set(vals[0])
                p_clean = vals[2].split("p")[0].strip()
                edit_price_var.set(p_clean)
                s_clean = vals[3].split()[0].strip()
                edit_stock_var.set(s_clean)
                catalogue = load_catalogue_data()
                for it in catalogue:
                    if str(it.get("slot_num", "")).strip() == vals[0]:
                        edit_weight_var.set(str(it.get("unit_weight", 250.0)))
                        break
                prod_msg_lbl.config(text=f"Loaded Slot {vals[0]}: {vals[1]} into editor", fg=CLR_WHITE)

        prod_tree.bind("<ButtonRelease-1>", on_tree_select)

        # =================================================================
        # TAB 2: 💵 Cash & Coins Management
        # =================================================================
        tab_cash_frame = tk.Frame(content_area, bg=BG_MIDDLE)
        tabs["cash"] = tab_cash_frame

        cash_hdr = tk.Frame(tab_cash_frame, bg=BG_CARD, padx=14, pady=10)
        cash_hdr.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            cash_hdr,
            text="💵 CASH RECEIVER & CHANGE DISPENSER FLOAT",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            cash_hdr,
            text="Change hopper coin inventory, balance calculation, and cash validator checks",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_CARD,
        ).pack(anchor="w")

        # Total Balance Card
        cash_bal_card = tk.Frame(tab_cash_frame, bg=BG_SCREEN, padx=16, pady=12)
        cash_bal_card.pack(fill=tk.X, pady=(0, 8))

        cash_tot_lbl = tk.Label(
            cash_bal_card,
            text="💰 TOTAL COIN FLOAT: £0.00",
            font=("Helvetica", 16, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        cash_tot_lbl.pack(anchor="w")

        tk.Label(
            cash_bal_card,
            text="Accepted Denominations (10p - £10.00): 10p, 20p, 50p, £1, £2, £5 Note, £10 Note\nPolicy: Banknotes £20 and £50 are not accepted by the machine and will be returned.",
            font=("Menlo", 11),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(2, 0))

        # Coin Table Frame
        cash_tree_frame = tk.Frame(tab_cash_frame, bg=BG_CARD, padx=8, pady=8)
        cash_tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cash_tree = ttk.Treeview(
            cash_tree_frame,
            style="Opt.Treeview",
            columns=("type", "coin", "qty", "subtotal", "status"),
            show="headings",
            height=8,
        )
        cash_tree.heading("type", text="Type")
        cash_tree.heading("coin", text="Denomination")
        cash_tree.heading("qty", text="Quantity in Machine")
        cash_tree.heading("subtotal", text="Subtotal Value")
        cash_tree.heading("status", text="Storage Status")

        cash_tree.column("type", width=110, anchor="center")
        cash_tree.column("coin", width=180, anchor="center")
        cash_tree.column("qty", width=180, anchor="center")
        cash_tree.column("subtotal", width=150, anchor="center")
        cash_tree.column("status", width=160, anchor="center")

        cash_tree.pack(fill=tk.BOTH, expand=True)

        def refresh_cash_view():
            cash_tree.delete(*cash_tree.get_children())
            cash_data = load_cash_inventory()
            coins = cash_data.get("coins", [])
            notes = cash_data.get("banknotes", [])
            total_pence = 0

            # Render Coins (Hopper)
            for c in coins:
                d = c.get("denomination", 0)
                qty = c.get("quantity", 0)
                sub = d * qty
                total_pence += sub
                st = "✅ Plentiful" if qty >= 10 else ("⚠️ Low (<10)" if qty > 0 else "❌ Empty")
                cash_tree.insert("", tk.END, values=("🪙 Coin", c.get("label", f"{d}p"), f"{qty} in hopper", f"£{sub/100:.2f}", st))

            # Render Banknotes (Stacker Cassette)
            for n in notes:
                d = n.get("denomination", 0)
                qty = n.get("quantity", 0)
                sub = d * qty
                total_pence += sub
                st = "✅ Stored" if qty >= 5 else ("⚠️ Low (<5)" if qty > 0 else "❌ Empty")
                cash_tree.insert("", tk.END, values=("💵 Note", n.get("label", f"£{d//100}"), f"{qty} in cassette", f"£{sub/100:.2f}", st))

            cash_tot_lbl.config(text=f"💰 TOTAL CASH IN MACHINE: £{total_pence/100:.2f} ({total_pence}p)")

        # Controls & Validator Test Frame
        cash_ctrl = tk.Frame(tab_cash_frame, bg=BG_CARD, padx=14, pady=12)
        cash_ctrl.pack(fill=tk.X)

        def do_refill_cash():
            cash_data = load_cash_inventory()
            coins = cash_data.get("coins", [])
            dispenser = getattr(self.cash_receiver, "_dispenser", None)
            for c in coins:
                c["quantity"] = c.get("quantity", 0) + 20
                c["subtotal_pence"] = c["denomination"] * c["quantity"]
                if dispenser and hasattr(dispenser, "_coin_stock"):
                    d = c["denomination"]
                    dispenser._coin_stock[d] = dispenser._coin_stock.get(d, 0) + 20

            tot_coins = sum(c["subtotal_pence"] for c in coins)
            tot_notes = sum(n.get("subtotal_pence", 0) for n in cash_data.get("banknotes", []))
            tot_all = tot_coins + tot_notes
            cash_data["summary"] = {
                "total_coins_pence": tot_coins,
                "total_banknotes_pence": tot_notes,
                "total_cash_pence": tot_all,
                "total_cash_formatted": f"£{tot_all/100:.2f}",
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            save_cash_inventory(cash_data)
            refresh_cash_view()
            cash_val_res_lbl.config(text="✅ Refilled +20 coins & updated cash_inventory.json", fg=CLR_LIME)

        btn_refill_cash = tk.Button(
            cash_ctrl,
            text="💰 Refill Coin Float (+20 of Each Coin)",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=do_refill_cash,
        )
        btn_refill_cash.pack(side=tk.LEFT, padx=(0, 12))
        self._attach_button_animation(btn_refill_cash)

        # Validator testing widget
        val_test_frame = tk.Frame(cash_ctrl, bg=BG_CARD)
        val_test_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(val_test_frame, text="Test Coin (p):", font=("Helvetica", 11, "bold"), fg=CLR_WHITE, bg=BG_CARD).pack(side=tk.LEFT, padx=(0, 4))
        test_coin_var = tk.StringVar(value="50")
        ent_coin = tk.Entry(val_test_frame, textvariable=test_coin_var, width=6, font=("Helvetica", 11))
        ent_coin.pack(side=tk.LEFT, padx=(0, 6))

        def test_coin_validation():
            try:
                amt = int(test_coin_var.get().strip())
                validator = getattr(self.cash_receiver, "_validator", None)
                ok = validator.validate(amt) if validator else (amt in [10, 20, 50, 100, 200, 500, 1000])
                if ok:
                    cash_val_res_lbl.config(text=f"✅ {amt}p is VALID & ACCEPTED (Range: 10p - £10.00)", fg=CLR_LIME)
                else:
                    if amt in (2000, 5000):
                        cash_val_res_lbl.config(text=f"❌ £{amt//100}.00 Note REJECTED & RETURNED (Max £10 accepted)", fg="#FF6B6B")
                    elif amt < 10:
                        cash_val_res_lbl.config(text=f"❌ {amt}p REJECTED & RETURNED (Min 10p accepted)", fg="#FF6B6B")
                    else:
                        cash_val_res_lbl.config(text=f"❌ {amt}p REJECTED & RETURNED (Accepted: 10p to £10.00 only)", fg="#FF6B6B")
            except ValueError:
                cash_val_res_lbl.config(text="❌ Error: Please enter valid integer pence", fg="#FF6B6B")

        btn_val = tk.Button(
            val_test_frame,
            text="Validate",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=5,
            cursor="hand2",
            command=test_coin_validation,
        )
        btn_val.pack(side=tk.LEFT, padx=(0, 8))
        self._attach_button_animation(btn_val)

        cash_val_res_lbl = tk.Label(cash_ctrl, text="CashValidator ready (Accepted: 10p to £10.00).", font=("Helvetica", 11), fg=CLR_LILAC, bg=BG_CARD)
        cash_val_res_lbl.pack(side=tk.RIGHT)

        # =================================================================
        # TAB 3: 💳 Payment Methods & Gateway Management
        # =================================================================
        tab_pay_frame = tk.Frame(content_area, bg=BG_MIDDLE)
        tabs["payments"] = tab_pay_frame

        pay_hdr = tk.Frame(tab_pay_frame, bg=BG_CARD, padx=14, pady=10)
        pay_hdr.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            pay_hdr,
            text="💳 PAYMENT METHODS & GATEWAY MANAGEMENT",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            pay_hdr,
            text="Control Cash / Card payment availability and configure connection to banking gateways",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_CARD,
        ).pack(anchor="w")

        # Scrollable container for Tab 3 content
        pay_canvas = tk.Canvas(tab_pay_frame, bg=BG_MIDDLE, highlightthickness=0)
        pay_scroll = ttk.Scrollbar(tab_pay_frame, orient=tk.VERTICAL, command=pay_canvas.yview)
        pay_inner = tk.Frame(pay_canvas, bg=BG_MIDDLE)

        pay_scroll_window = pay_canvas.create_window((0, 0), window=pay_inner, anchor="nw")

        def _on_pay_canvas_configure(event):
            pay_canvas.itemconfig(pay_scroll_window, width=event.width)

        pay_canvas.bind("<Configure>", _on_pay_canvas_configure)
        pay_inner.bind("<Configure>", lambda e: pay_canvas.configure(scrollregion=pay_canvas.bbox("all")))
        pay_canvas.configure(yscrollcommand=pay_scroll.set)

        pay_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pay_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # -------------------------------------------------------------
        # 1. Payment Channels Availability (Cash & Card Toggles)
        # -------------------------------------------------------------
        avail_card = tk.Frame(pay_inner, bg=BG_CARD, padx=14, pady=12)
        avail_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            avail_card,
            text="PAYMENT CHANNELS AVAILABILITY (CUSTOMER-FACING)",
            font=("Helvetica", 13, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 8))

        channels_box = tk.Frame(avail_card, bg=BG_CARD)
        channels_box.pack(fill=tk.X)
        channels_box.columnconfigure(0, weight=1, uniform="chan")
        channels_box.columnconfigure(1, weight=1, uniform="chan")

        # Cash Channel Frame
        cash_chan_frame = tk.Frame(channels_box, bg=BG_SCREEN, padx=12, pady=10, highlightbackground=CLR_LILAC, highlightthickness=1)
        cash_chan_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        tk.Label(
            cash_chan_frame,
            text="💵 Cash Payment Channel",
            font=("Helvetica", 12, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(anchor="w")

        cash_status_lbl = tk.Label(
            cash_chan_frame,
            text="STATUS: [ ENABLED ]",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        cash_status_lbl.pack(anchor="w", pady=(3, 4))

        tk.Label(
            cash_chan_frame,
            text="Hardware coin validator (£2, £1, 50p, 20p, 10p)\nand automatic change return hopper.",
            font=("Helvetica", 10),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 8))

        def update_channels_ui():
            if self.cash_enabled:
                cash_status_lbl.config(text="STATUS: [ ENABLED ]", fg=CLR_LIME)
                btn_toggle_cash.config(text="⛔ Disable Cash Payment", bg=CLR_DEEP_PURPLE, fg=CLR_WHITE)
                cash_chan_frame.config(highlightbackground=CLR_LIME)
            else:
                cash_status_lbl.config(text="STATUS: [ DISABLED ]", fg="#FF6B6B")
                btn_toggle_cash.config(text="✅ Enable Cash Payment", bg=BTN_BG, fg=BTN_FG)
                cash_chan_frame.config(highlightbackground="#FF6B6B")

            if self.card_enabled:
                card_status_lbl.config(text="STATUS: [ ENABLED ]", fg=CLR_LIME)
                btn_toggle_card.config(text="⛔ Disable Card Payment", bg=CLR_DEEP_PURPLE, fg=CLR_WHITE)
                card_chan_frame.config(highlightbackground=CLR_LIME)
            else:
                card_status_lbl.config(text="STATUS: [ DISABLED ]", fg="#FF6B6B")
                btn_toggle_card.config(text="✅ Enable Card Payment", bg=BTN_BG, fg=BTN_FG)
                card_chan_frame.config(highlightbackground="#FF6B6B")

        def toggle_cash_channel():
            self.cash_enabled = not self.cash_enabled
            self.payment_config["cash_enabled"] = self.cash_enabled
            save_payment_config(self.payment_config)
            st_text = "ENABLED" if self.cash_enabled else "DISABLED"
            log_activity("PAYMENT_METHOD_TOGGLE", f"Cash payment channel set to {st_text}")
            update_channels_ui()
            if hasattr(self, "current_page") and self.current_page == "payment":
                self._refresh_payment_page()

        btn_toggle_cash = tk.Button(
            cash_chan_frame,
            text="⛔ Disable Cash Payment",
            font=("Helvetica", 11, "bold"),
            bg=CLR_DEEP_PURPLE,
            fg=CLR_WHITE,
            activebackground=CLR_WHITE,
            activeforeground=CLR_DEEP_PURPLE,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=toggle_cash_channel,
        )
        btn_toggle_cash.pack(anchor="w")
        self._attach_button_animation(btn_toggle_cash)

        # Card Channel Frame
        card_chan_frame = tk.Frame(channels_box, bg=BG_SCREEN, padx=12, pady=10, highlightbackground=CLR_LILAC, highlightthickness=1)
        card_chan_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        tk.Label(
            card_chan_frame,
            text="💳 Card & Digital Payment Channel",
            font=("Helvetica", 12, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(anchor="w")

        card_status_lbl = tk.Label(
            card_chan_frame,
            text="STATUS: [ ENABLED ]",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        card_status_lbl.pack(anchor="w", pady=(3, 4))

        tk.Label(
            card_chan_frame,
            text="Contactless card reader, dynamic QR checkout,\nand online payment gateway processing.",
            font=("Helvetica", 10),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 8))

        def toggle_card_channel():
            self.card_enabled = not self.card_enabled
            self.payment_config["card_enabled"] = self.card_enabled
            save_payment_config(self.payment_config)
            st_text = "ENABLED" if self.card_enabled else "DISABLED"
            log_activity("PAYMENT_METHOD_TOGGLE", f"Card payment channel set to {st_text}")
            update_channels_ui()
            if hasattr(self, "current_page") and self.current_page == "payment":
                self._refresh_payment_page()

        btn_toggle_card = tk.Button(
            card_chan_frame,
            text="⛔ Disable Card Payment",
            font=("Helvetica", 11, "bold"),
            bg=CLR_DEEP_PURPLE,
            fg=CLR_WHITE,
            activebackground=CLR_WHITE,
            activeforeground=CLR_DEEP_PURPLE,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=toggle_card_channel,
        )
        btn_toggle_card.pack(anchor="w")
        self._attach_button_animation(btn_toggle_card)

        # -------------------------------------------------------------
        # 2. Payment Gateway Configuration & Connection Manager
        # -------------------------------------------------------------
        gw_card = tk.Frame(pay_inner, bg=BG_CARD, padx=14, pady=12)
        gw_card.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            gw_card,
            text="PAYMENT GATEWAY INTEGRATION & CONNECTION MANAGER",
            font=("Helvetica", 13, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            gw_card,
            text="Select active payment provider or update connection endpoints and API keys",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 8))

        # Active Gateway Selection Row
        gw_select_row = tk.Frame(gw_card, bg=BG_SCREEN, padx=12, pady=10)
        gw_select_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            gw_select_row,
            text="Gateway Provider:",
            font=("Helvetica", 12, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(side=tk.LEFT, padx=(0, 8))

        gw_options = [
            ("stripe", "Stripe Checkout (Dynamic QR)"),
            ("paypal", "PayPal REST Gateway"),
            ("custom_rest", "Custom REST Payment Gateway"),
            ("mock", "Offline Mock Bank (Simulator)"),
        ]
        gw_var = tk.StringVar(value=self.active_gateway_name)

        gw_combo = ttk.Combobox(
            gw_select_row,
            textvariable=gw_var,
            values=[opt[0] for opt in gw_options],
            state="readonly",
            width=18,
            font=("Helvetica", 11),
        )
        gw_combo.pack(side=tk.LEFT, padx=(0, 10))

        active_badge_lbl = tk.Label(
            gw_select_row,
            text=f"Active: {self.active_gateway_name.upper()}",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        active_badge_lbl.pack(side=tk.LEFT)

        # Connection Parameter Inputs Form Frame
        form_frame = tk.Frame(gw_card, bg=BG_CARD)
        form_frame.pack(fill=tk.X, pady=(0, 8))

        # Row 1: Name and Currency
        r1 = tk.Frame(form_frame, bg=BG_CARD)
        r1.pack(fill=tk.X, pady=3)
        r1.columnconfigure(0, weight=2)
        r1.columnconfigure(1, weight=1)

        f_name_box = tk.Frame(r1, bg=BG_CARD)
        f_name_box.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        tk.Label(f_name_box, text="Gateway Display Name:", font=("Helvetica", 11, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        ent_gw_name = tk.Entry(f_name_box, font=("Helvetica", 11), bg=BG_SCREEN, fg=CLR_WHITE, insertbackground=CLR_WHITE, relief=tk.FLAT)
        ent_gw_name.pack(fill=tk.X, ipady=4)

        f_curr_box = tk.Frame(r1, bg=BG_CARD)
        f_curr_box.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tk.Label(f_curr_box, text="Currency Code:", font=("Helvetica", 11, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        ent_gw_curr = tk.Entry(f_curr_box, font=("Helvetica", 11), bg=BG_SCREEN, fg=CLR_WHITE, insertbackground=CLR_WHITE, relief=tk.FLAT)
        ent_gw_curr.pack(fill=tk.X, ipady=4)

        # Row 2: API Endpoint URL
        r2 = tk.Frame(form_frame, bg=BG_CARD)
        r2.pack(fill=tk.X, pady=3)
        tk.Label(r2, text="API Endpoint / Base URL:", font=("Helvetica", 11, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        ent_gw_url = tk.Entry(r2, font=("Helvetica", 11), bg=BG_SCREEN, fg=CLR_WHITE, insertbackground=CLR_WHITE, relief=tk.FLAT)
        ent_gw_url.pack(fill=tk.X, ipady=4)

        # Row 3: API Key / Client ID / Publishable Key
        r3 = tk.Frame(form_frame, bg=BG_CARD)
        r3.pack(fill=tk.X, pady=3)
        lbl_key1 = tk.Label(r3, text="Publishable Key / Client ID:", font=("Helvetica", 11, "bold"), fg=CLR_LILAC, bg=BG_CARD)
        lbl_key1.pack(anchor="w")
        ent_gw_key1 = tk.Entry(r3, font=("Helvetica", 11), bg=BG_SCREEN, fg=CLR_WHITE, insertbackground=CLR_WHITE, relief=tk.FLAT)
        ent_gw_key1.pack(fill=tk.X, ipady=4)

        # Row 4: Secret Key / Token (with Show/Hide)
        r4 = tk.Frame(form_frame, bg=BG_CARD)
        r4.pack(fill=tk.X, pady=3)
        lbl_key2 = tk.Label(r4, text="Secret Key / Merchant Token:", font=("Helvetica", 11, "bold"), fg=CLR_LILAC, bg=BG_CARD)
        lbl_key2.pack(anchor="w")

        sec_box = tk.Frame(r4, bg=BG_CARD)
        sec_box.pack(fill=tk.X)
        ent_gw_key2 = tk.Entry(sec_box, font=("Helvetica", 11), bg=BG_SCREEN, fg=CLR_WHITE, insertbackground=CLR_WHITE, relief=tk.FLAT, show="*")
        ent_gw_key2.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

        show_secret_var = tk.BooleanVar(value=False)
        def toggle_show_secret():
            if show_secret_var.get():
                ent_gw_key2.config(show="*")
                show_secret_var.set(False)
                btn_toggle_sec.config(text="👁️ Show")
            else:
                ent_gw_key2.config(show="")
                show_secret_var.set(True)
                btn_toggle_sec.config(text="🙈 Hide")

        btn_toggle_sec = tk.Button(
            sec_box,
            text="👁️ Show",
            font=("Helvetica", 10, "bold"),
            bg=CLR_DEEP_PURPLE,
            fg=CLR_WHITE,
            activebackground=CLR_WHITE,
            activeforeground=CLR_DEEP_PURPLE,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=toggle_show_secret,
        )
        btn_toggle_sec.pack(side=tk.RIGHT, padx=(6, 0))

        # Helper to load form values from current gateway selection
        def load_gateway_form(selected_gw: str):
            gateways = self.payment_config.get("gateways", {})
            gw_data = gateways.get(selected_gw, {})

            ent_gw_name.delete(0, tk.END)
            ent_gw_name.insert(0, gw_data.get("name", ""))

            ent_gw_curr.delete(0, tk.END)
            ent_gw_curr.insert(0, gw_data.get("currency", "GBP"))

            ent_gw_url.delete(0, tk.END)
            ent_gw_url.insert(0, gw_data.get("api_url", ""))

            ent_gw_key1.delete(0, tk.END)
            ent_gw_key2.delete(0, tk.END)

            if selected_gw == "stripe":
                lbl_key1.config(text="Publishable Key (pk_test_...):")
                lbl_key2.config(text="Secret Key (sk_test_...):")
                ent_gw_key1.insert(0, gw_data.get("publishable_key", ""))
                ent_gw_key2.insert(0, gw_data.get("secret_key", ""))
            elif selected_gw == "paypal":
                lbl_key1.config(text="Client ID (OAuth):")
                lbl_key2.config(text="Secret Key (OAuth):")
                ent_gw_key1.insert(0, gw_data.get("client_id", ""))
                ent_gw_key2.insert(0, gw_data.get("secret_key", ""))
            elif selected_gw == "custom_rest":
                lbl_key1.config(text="API Key / Auth Header Token:")
                lbl_key2.config(text="Webhook Signing Secret:")
                ent_gw_key1.insert(0, gw_data.get("api_key", ""))
                ent_gw_key2.insert(0, gw_data.get("webhook_secret", ""))
            elif selected_gw == "mock":
                lbl_key1.config(text="Simulation Mode:")
                lbl_key2.config(text="Test Response Status:")
                ent_gw_key1.insert(0, "LOCAL_SIMULATOR")
                ent_gw_key2.insert(0, "ALWAYS_APPROVE")

        gw_combo.bind("<<ComboboxSelected>>", lambda e: load_gateway_form(gw_var.get()))

        # Form Buttons (Save and Test Connection)
        gw_btn_row = tk.Frame(gw_card, bg=BG_CARD)
        gw_btn_row.pack(fill=tk.X, pady=(8, 0))

        def save_gateway_configuration():
            selected_gw = gw_var.get().strip()
            if not selected_gw:
                return

            if "gateways" not in self.payment_config:
                self.payment_config["gateways"] = {}
            if selected_gw not in self.payment_config["gateways"]:
                self.payment_config["gateways"][selected_gw] = {}

            gw_entry = self.payment_config["gateways"][selected_gw]
            gw_entry["name"] = ent_gw_name.get().strip()
            gw_entry["currency"] = ent_gw_curr.get().strip().upper()
            gw_entry["api_url"] = ent_gw_url.get().strip()

            if selected_gw == "stripe":
                gw_entry["publishable_key"] = ent_gw_key1.get().strip()
                gw_entry["secret_key"] = ent_gw_key2.get().strip()
            elif selected_gw == "paypal":
                gw_entry["client_id"] = ent_gw_key1.get().strip()
                gw_entry["secret_key"] = ent_gw_key2.get().strip()
            elif selected_gw == "custom_rest":
                gw_entry["api_key"] = ent_gw_key1.get().strip()
                gw_entry["webhook_secret"] = ent_gw_key2.get().strip()

            self.payment_config["active_gateway"] = selected_gw
            self.active_gateway_name = selected_gw
            save_payment_config(self.payment_config)

            # Dynamically instantiate and switch bank service
            new_bank = create_bank_service(selected_gw, gw_entry)
            self.active_bank = new_bank
            self.stripe_bank = new_bank
            self.card_reader._bank = new_bank

            active_badge_lbl.config(text=f"Active: {selected_gw.upper()}", fg=CLR_LIME)
            diag_status_lbl.config(text=f"🟢 Activated: {gw_entry.get('name', selected_gw)}", fg=CLR_LIME)
            log_activity("PAYMENT_GATEWAY_CONFIGURED", f"Switched active gateway to '{selected_gw}' ({gw_entry.get('name')})")

            if hasattr(self, "current_page") and self.current_page == "payment":
                self._refresh_payment_page()

        btn_save_gw = tk.Button(
            gw_btn_row,
            text="💾 Save & Activate Gateway",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=save_gateway_configuration,
        )
        btn_save_gw.pack(side=tk.LEFT, padx=(0, 10))
        self._attach_button_animation(btn_save_gw)

        def test_gateway_connection():
            selected_gw = gw_var.get().strip()
            diag_status_lbl.config(text=f"Testing connection to {selected_gw.upper()}...", fg=CLR_WHITE)

            def worker():
                try:
                    temp_config = {
                        "name": ent_gw_name.get().strip(),
                        "currency": ent_gw_curr.get().strip(),
                        "api_url": ent_gw_url.get().strip(),
                    }
                    if selected_gw == "stripe":
                        temp_config["publishable_key"] = ent_gw_key1.get().strip()
                        temp_config["secret_key"] = ent_gw_key2.get().strip()
                    elif selected_gw == "paypal":
                        temp_config["client_id"] = ent_gw_key1.get().strip()
                        temp_config["secret_key"] = ent_gw_key2.get().strip()
                    elif selected_gw == "custom_rest":
                        temp_config["api_key"] = ent_gw_key1.get().strip()

                    test_bank = create_bank_service(selected_gw, temp_config)
                    ok, msg = test_bank.testConnection()
                    if ok:
                        dialog.after(0, lambda: diag_status_lbl.config(text=f"🟢 {msg}", fg=CLR_LIME))
                    else:
                        dialog.after(0, lambda: diag_status_lbl.config(text=f"⚠️ {msg}", fg="#FF6B6B"))
                except Exception as ex:
                    dialog.after(0, lambda: diag_status_lbl.config(text=f"⚠️ Test Error: {str(ex)[:50]}", fg=CLR_LILAC))

            threading.Thread(target=worker, daemon=True).start()

        btn_test_gw = tk.Button(
            gw_btn_row,
            text="🧪 Test Connection",
            font=("Helvetica", 11, "bold"),
            bg=CLR_DEEP_PURPLE,
            fg=CLR_WHITE,
            activebackground=CLR_WHITE,
            activeforeground=CLR_DEEP_PURPLE,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=test_gateway_connection,
        )
        btn_test_gw.pack(side=tk.LEFT, padx=(0, 10))
        self._attach_button_animation(btn_test_gw)

        diag_status_lbl = tk.Label(
            gw_btn_row,
            text="Ready to test connection.",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_CARD,
        )
        diag_status_lbl.pack(side=tk.LEFT)

        # -------------------------------------------------------------
        # 3. Session Timeout & Transaction Safety Configuration
        # -------------------------------------------------------------
        policy_card = tk.Frame(pay_inner, bg=BG_CARD, padx=14, pady=12)
        policy_card.pack(fill=tk.X)

        tk.Label(
            policy_card,
            text="⏱️ PAYMENT SESSION TIMEOUT & SAFETY POLICIES",
            font=("Helvetica", 13, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            policy_card,
            text="Configure payment countdown duration (seconds) before session is automatically cancelled",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 8))

        # Timeout Duration Editor Row
        timeout_row = tk.Frame(policy_card, bg=BG_SCREEN, padx=12, pady=10)
        timeout_row.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            timeout_row,
            text="Session Timeout:",
            font=("Helvetica", 12, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(side=tk.LEFT, padx=(0, 8))

        ent_timeout = tk.Entry(
            timeout_row,
            font=("Helvetica", 12, "bold"),
            bg=BG_CARD,
            fg=CLR_LIME,
            insertbackground=CLR_WHITE,
            relief=tk.FLAT,
            width=5,
            justify="center",
        )
        ent_timeout.pack(side=tk.LEFT, padx=(0, 4), ipady=4)
        ent_timeout.insert(0, str(getattr(self, "session_timeout_seconds", 60)))

        tk.Label(
            timeout_row,
            text="Seconds",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
        ).pack(side=tk.LEFT, padx=(0, 14))

        # Preset Buttons
        tk.Label(
            timeout_row,
            text="Quick Presets:",
            font=("Helvetica", 11, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(side=tk.LEFT, padx=(0, 6))

        def set_preset_timeout(seconds: int):
            ent_timeout.delete(0, tk.END)
            ent_timeout.insert(0, str(seconds))

        for sec in (30, 45, 60, 90, 120):
            p_btn = tk.Button(
                timeout_row,
                text=f"{sec}s",
                font=("Helvetica", 10, "bold"),
                bg=BTN_BG,
                fg=BTN_FG,
                relief=tk.FLAT,
                bd=0,
                padx=8,
                pady=3,
                cursor="hand2",
                command=lambda s=sec: set_preset_timeout(s),
            )
            p_btn.pack(side=tk.LEFT, padx=3)
            self._attach_button_animation(p_btn)

        # Save Timeout Button Row
        timeout_save_row = tk.Frame(policy_card, bg=BG_CARD)
        timeout_save_row.pack(fill=tk.X, pady=(4, 6))

        def save_session_timeout():
            raw_val = ent_timeout.get().strip()
            try:
                val = int(raw_val)
                if val < 10 or val > 600:
                    messagebox.showwarning(
                        "Invalid Timeout Value",
                        "Please enter a session timeout between 10 and 600 seconds.",
                        parent=dialog,
                    )
                    return
            except ValueError:
                messagebox.showerror(
                    "Invalid Number",
                    "Please enter a valid numeric value for session timeout seconds.",
                    parent=dialog,
                )
                return

            self.session_timeout_seconds = val
            self.payment_config["timeout_seconds"] = val
            save_payment_config(self.payment_config)
            self.timer.timeoutSeconds = val
            log_activity("TIMEOUT_CONFIG_UPDATED", f"Payment session timeout set to {val}s")
            timeout_status_lbl.config(text=f"🟢 Saved: Session timeout set to {val} seconds", fg=CLR_LIME)
            update_policy_text()

        btn_save_timeout = tk.Button(
            timeout_save_row,
            text="💾 Save Timeout Setting",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=save_session_timeout,
        )
        btn_save_timeout.pack(side=tk.LEFT, padx=(0, 10))
        self._attach_button_animation(btn_save_timeout)

        timeout_status_lbl = tk.Label(
            timeout_save_row,
            text=f"Current Timeout: {getattr(self, 'session_timeout_seconds', 60)}s",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_CARD,
        )
        timeout_status_lbl.pack(side=tk.LEFT)

        # Safety Rules Description
        policy_lbl = tk.Label(
            policy_card,
            text="",
            font=("Menlo", 10),
            fg=CLR_WHITE,
            bg=BG_CARD,
            justify=tk.LEFT,
        )
        policy_lbl.pack(anchor="w", pady=(6, 0))

        def update_policy_text():
            cur_sec = getattr(self, "session_timeout_seconds", 60)
            p_text = (
                f"• Active Limit: {cur_sec} Seconds countdown timer active on Cash and Card modal dialogs\n"
                f"• Cash Payment Policy: At {cur_sec}s timeout, automatically cancels order and refunds 100% of inserted coins\n"
                f"• Card Payment Policy: At {cur_sec}s timeout, automatically cancels order and expires remote session\n"
                f"• UML Contract: TransactionTimer.hasExpired() monitored once per second during processing"
            )
            policy_lbl.config(text=p_text)

        update_policy_text()

        def refresh_payments_view():
            self.payment_config = load_payment_config()
            self.cash_enabled = bool(self.payment_config.get("cash_enabled", True))
            self.card_enabled = bool(self.payment_config.get("card_enabled", True))
            self.active_gateway_name = self.payment_config.get("active_gateway", "stripe")
            self.session_timeout_seconds = int(self.payment_config.get("timeout_seconds", 60))
            self.timer.timeoutSeconds = self.session_timeout_seconds
            update_channels_ui()
            gw_var.set(self.active_gateway_name)
            load_gateway_form(self.active_gateway_name)
            active_badge_lbl.config(text=f"Active: {self.active_gateway_name.upper()}", fg=CLR_LIME)
            diag_status_lbl.config(text="Ready to test connection.", fg=CLR_LILAC)
            ent_timeout.delete(0, tk.END)
            ent_timeout.insert(0, str(self.session_timeout_seconds))
            timeout_status_lbl.config(text=f"Current Timeout: {self.session_timeout_seconds}s", fg=CLR_LILAC)
            update_policy_text()

        # =================================================================
        # TAB 4: 🧾 Transaction Records & Sales History
        # =================================================================
        tab_trans_frame = tk.Frame(content_area, bg=BG_MIDDLE)
        tabs["transactions"] = tab_trans_frame

        # Top Header
        trans_hdr = tk.Frame(tab_trans_frame, bg=BG_CARD, padx=14, pady=10)
        trans_hdr.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            trans_hdr,
            text="🧾 TRANSACTION RECORDS & SALES AUDIT",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            trans_hdr,
            text="Persistent drink sales history, customer charges, and payment outcomes loaded from data/transactions.json",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_CARD,
        ).pack(anchor="w")

        # KPI Summary Cards Row (Revenue, Completed Sales, Cancelled, Timeouts)
        kpi_row = tk.Frame(tab_trans_frame, bg=BG_MIDDLE)
        kpi_row.pack(fill=tk.X, pady=(0, 8))
        kpi_row.columnconfigure(0, weight=1, uniform="kpi")
        kpi_row.columnconfigure(1, weight=1, uniform="kpi")
        kpi_row.columnconfigure(2, weight=1, uniform="kpi")
        kpi_row.columnconfigure(3, weight=1, uniform="kpi")

        # 1. Total Revenue Card
        c1 = tk.Frame(kpi_row, bg=BG_CARD, padx=12, pady=10, highlightbackground=CLR_LIME, highlightthickness=1)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        tk.Label(c1, text="TOTAL REVENUE", font=("Helvetica", 10, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        kpi_rev_lbl = tk.Label(c1, text="£0.00", font=("Helvetica", 18, "bold"), fg=CLR_LIME, bg=BG_CARD)
        kpi_rev_lbl.pack(anchor="w", pady=(2, 0))
        tk.Label(c1, text="Settled Sales Revenue", font=("Helvetica", 10), fg=CLR_WHITE, bg=BG_CARD).pack(anchor="w")

        # 2. Successful Orders Card
        c2 = tk.Frame(kpi_row, bg=BG_CARD, padx=12, pady=10, highlightbackground=CLR_LILAC, highlightthickness=1)
        c2.grid(row=0, column=1, sticky="nsew", padx=2)
        tk.Label(c2, text="COMPLETED ORDERS", font=("Helvetica", 10, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        kpi_succ_lbl = tk.Label(c2, text="0 Drinks", font=("Helvetica", 18, "bold"), fg=CLR_WHITE, bg=BG_CARD)
        kpi_succ_lbl.pack(anchor="w", pady=(2, 0))
        tk.Label(c2, text="Dispensed Successfully", font=("Helvetica", 10), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")

        # 3. Cancelled Orders Card
        c3 = tk.Frame(kpi_row, bg=BG_CARD, padx=12, pady=10, highlightbackground=CLR_LILAC, highlightthickness=1)
        c3.grid(row=0, column=2, sticky="nsew", padx=2)
        tk.Label(c3, text="CANCELLED ORDERS", font=("Helvetica", 10, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        kpi_canc_lbl = tk.Label(c3, text="0 Orders", font=("Helvetica", 18, "bold"), fg=CLR_LILAC, bg=BG_CARD)
        kpi_canc_lbl.pack(anchor="w", pady=(2, 0))
        tk.Label(c3, text="User Refunded 100%", font=("Helvetica", 10), fg=CLR_WHITE, bg=BG_CARD).pack(anchor="w")

        # 4. Timed Out / Failed Card
        c4 = tk.Frame(kpi_row, bg=BG_CARD, padx=12, pady=10, highlightbackground=CLR_LILAC, highlightthickness=1)
        c4.grid(row=0, column=3, sticky="nsew", padx=(4, 0))
        tk.Label(c4, text="TIMEOUTS / DECLINED", font=("Helvetica", 10, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        kpi_fail_lbl = tk.Label(c4, text="0 Orders", font=("Helvetica", 18, "bold"), fg="#FF6B6B", bg=BG_CARD)
        kpi_fail_lbl.pack(anchor="w", pady=(2, 0))
        tk.Label(c4, text="60s Timeout Auto-Aborts", font=("Helvetica", 10), fg=CLR_WHITE, bg=BG_CARD).pack(anchor="w")

        # Filter & Search Bar
        trans_filter_bar = tk.Frame(tab_trans_frame, bg=BG_CARD, padx=12, pady=8)
        trans_filter_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            trans_filter_bar,
            text="Filter Status:",
            font=("Helvetica", 11, "bold"),
            fg=CLR_WHITE,
            bg=BG_CARD,
        ).pack(side=tk.LEFT, padx=(0, 6))

        tx_status_var = tk.StringVar(value="ALL")
        tx_status_combo = ttk.Combobox(
            trans_filter_bar,
            textvariable=tx_status_var,
            values=["ALL", "SUCCESS", "CANCELLED", "TIMEOUT", "FAILED"],
            state="readonly",
            width=14,
            font=("Helvetica", 11),
        )
        tx_status_combo.pack(side=tk.LEFT, padx=(0, 14))

        tk.Label(
            trans_filter_bar,
            text="Search Drink:",
            font=("Helvetica", 11, "bold"),
            fg=CLR_WHITE,
            bg=BG_CARD,
        ).pack(side=tk.LEFT, padx=(0, 6))

        tx_search_ent = tk.Entry(
            trans_filter_bar,
            font=("Helvetica", 11),
            bg=BG_SCREEN,
            fg=CLR_WHITE,
            insertbackground=CLR_WHITE,
            relief=tk.FLAT,
            width=18,
        )
        tx_search_ent.pack(side=tk.LEFT, padx=(0, 10), ipady=3)

        def on_tx_filter_change(*args):
            refresh_transactions_view()

        tx_status_combo.bind("<<ComboboxSelected>>", on_tx_filter_change)
        tx_search_ent.bind("<KeyRelease>", on_tx_filter_change)

        btn_tx_clear_filter = tk.Button(
            trans_filter_bar,
            text="Reset Filter",
            font=("Helvetica", 11),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: (tx_status_var.set("ALL"), tx_search_ent.delete(0, tk.END), refresh_transactions_view()),
        )
        btn_tx_clear_filter.pack(side=tk.LEFT)
        self._attach_button_animation(btn_tx_clear_filter)

        # Transactions Treeview
        trans_tree_frame = tk.Frame(tab_trans_frame, bg=BG_CARD, padx=8, pady=8)
        trans_tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        trans_tree = ttk.Treeview(
            trans_tree_frame,
            style="Opt.Treeview",
            columns=("id", "time", "drink", "amount", "status"),
            show="headings",
            height=9,
        )
        trans_tree.heading("id", text="#")
        trans_tree.heading("time", text="Timestamp")
        trans_tree.heading("drink", text="Beverage Name")
        trans_tree.heading("amount", text="Amount Paid")
        trans_tree.heading("status", text="Outcome Status")

        trans_tree.column("id", width=60, anchor="center")
        trans_tree.column("time", width=190, anchor="center")
        trans_tree.column("drink", width=260, anchor="w")
        trans_tree.column("amount", width=150, anchor="center")
        trans_tree.column("status", width=170, anchor="center")

        trans_scroll = ttk.Scrollbar(trans_tree_frame, orient=tk.VERTICAL, command=trans_tree.yview)
        trans_tree.configure(yscrollcommand=trans_scroll.set)
        trans_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        trans_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        trans_tree.tag_configure("tag_success", foreground=CLR_LIME)
        trans_tree.tag_configure("tag_cancelled", foreground=CLR_LILAC)
        trans_tree.tag_configure("tag_failed", foreground="#FF6B6B")

        # Control Panel Frame
        trans_ctrl = tk.Frame(tab_trans_frame, bg=BG_CARD, padx=14, pady=12)
        trans_ctrl.pack(fill=tk.X)

        btn_refresh_trans = tk.Button(
            trans_ctrl,
            text="🔄 Refresh Records",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=lambda: refresh_transactions_view(),
        )
        btn_refresh_trans.pack(side=tk.LEFT, padx=(0, 10))
        self._attach_button_animation(btn_refresh_trans)

        def clear_transactions_history():
            if messagebox.askyesno(
                "Clear Transaction History",
                "Are you sure you want to clear all transaction records?\nThis operation will empty data/transactions.json.",
            ):
                save_transactions([])
                if hasattr(self, "logger") and self.logger is not None:
                    self.logger._records = []
                log_activity("TRANSACTIONS_CLEARED", "All transaction history records cleared by admin")
                refresh_transactions_view()

        btn_clear_trans = tk.Button(
            trans_ctrl,
            text="🗑️ Clear Transaction History",
            font=("Helvetica", 11, "bold"),
            bg=CLR_DEEP_PURPLE,
            fg=CLR_WHITE,
            activebackground=CLR_WHITE,
            activeforeground=CLR_DEEP_PURPLE,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=clear_transactions_history,
        )
        btn_clear_trans.pack(side=tk.LEFT, padx=(0, 10))
        self._attach_button_animation(btn_clear_trans)

        trans_count_lbl = tk.Label(trans_ctrl, text="0 records found.", font=("Helvetica", 11), fg=CLR_LILAC, bg=BG_CARD)
        trans_count_lbl.pack(side=tk.RIGHT)

        def refresh_transactions_view():
            trans_tree.delete(*trans_tree.get_children())
            records = load_transactions()
            if hasattr(self, "logger") and self.logger is not None:
                mem_records = self.logger.getHistory()
                if len(mem_records) > len(records):
                    records = mem_records
                    save_transactions(records)

            total_rev_pence = 0
            succ_count = 0
            canc_count = 0
            fail_count = 0

            for r in records:
                st = r.status.upper()
                if st == "SUCCESS":
                    total_rev_pence += r.amountPaid
                    succ_count += 1
                elif "CANCEL" in st:
                    canc_count += 1
                else:
                    fail_count += 1

            kpi_rev_lbl.config(text=f"£{total_rev_pence / 100:.2f}")
            kpi_succ_lbl.config(text=f"{succ_count} Drinks")
            kpi_canc_lbl.config(text=f"{canc_count} Orders")
            kpi_fail_lbl.config(text=f"{fail_count} Orders")

            status_filter = tx_status_var.get().upper()
            search_query = tx_search_ent.get().strip().lower()

            displayed_count = 0
            for idx, r in enumerate(reversed(records), 1):
                st = r.status.upper()
                if status_filter != "ALL" and status_filter not in st:
                    continue
                if search_query and search_query not in r.drinkName.lower():
                    continue

                ts_str = r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                amt_str = f"£{r.amountPaid / 100:.2f} ({r.amountPaid}p)"

                tag = "tag_success" if st == "SUCCESS" else ("tag_cancelled" if "CANCEL" in st else "tag_failed")
                status_display = f"✅ {st}" if st == "SUCCESS" else (f"⚠️ {st}" if "CANCEL" in st else f"⏱️ {st}")

                trans_tree.insert(
                    "",
                    tk.END,
                    values=(len(records) - idx + 1, ts_str, r.drinkName, amt_str, status_display),
                    tags=(tag,),
                )
                displayed_count += 1

            trans_count_lbl.config(text=f"Displaying {displayed_count} of {len(records)} transactions.")

        # =================================================================
        # TAB 5: 🎖️ Loyalty Membership Management
        # =================================================================
        tab_members_frame = tk.Frame(content_area, bg=BG_MIDDLE)
        tabs["members"] = tab_members_frame

        # Top Header
        members_hdr = tk.Frame(tab_members_frame, bg=BG_CARD, padx=14, pady=10)
        members_hdr.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            members_hdr,
            text="🎖️ LOYALTY PROGRAMME MEMBERSHIP MANAGEMENT",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            members_hdr,
            text="Manage registered loyalty cardholders, toggle account status, delete, or register new member accounts",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_CARD,
        ).pack(anchor="w")

        # KPI Summary Cards Row
        mem_kpi_row = tk.Frame(tab_members_frame, bg=BG_MIDDLE)
        mem_kpi_row.pack(fill=tk.X, pady=(0, 8))
        mem_kpi_row.columnconfigure(0, weight=1, uniform="memkpi")
        mem_kpi_row.columnconfigure(1, weight=1, uniform="memkpi")
        mem_kpi_row.columnconfigure(2, weight=1, uniform="memkpi")
        mem_kpi_row.columnconfigure(3, weight=1, uniform="memkpi")

        # 1. Total Members
        mc1 = tk.Frame(mem_kpi_row, bg=BG_CARD, padx=12, pady=10, highlightbackground=CLR_LIME, highlightthickness=1)
        mc1.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        tk.Label(mc1, text="TOTAL MEMBERS", font=("Helvetica", 10, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        mem_kpi_total_lbl = tk.Label(mc1, text="0 Members", font=("Helvetica", 18, "bold"), fg=CLR_WHITE, bg=BG_CARD)
        mem_kpi_total_lbl.pack(anchor="w", pady=(2, 0))
        tk.Label(mc1, text="Registered Accounts", font=("Helvetica", 10), fg=CLR_WHITE, bg=BG_CARD).pack(anchor="w")

        # 2. Active Members
        mc2 = tk.Frame(mem_kpi_row, bg=BG_CARD, padx=12, pady=10, highlightbackground=CLR_LIME, highlightthickness=1)
        mc2.grid(row=0, column=1, sticky="nsew", padx=2)
        tk.Label(mc2, text="ACTIVE STATUS", font=("Helvetica", 10, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        mem_kpi_active_lbl = tk.Label(mc2, text="0 Active", font=("Helvetica", 18, "bold"), fg=CLR_LIME, bg=BG_CARD)
        mem_kpi_active_lbl.pack(anchor="w", pady=(2, 0))
        tk.Label(mc2, text="Eligible for Discounts", font=("Helvetica", 10), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")

        # 3. Inactive Members
        mc3 = tk.Frame(mem_kpi_row, bg=BG_CARD, padx=12, pady=10, highlightbackground=CLR_LILAC, highlightthickness=1)
        mc3.grid(row=0, column=2, sticky="nsew", padx=2)
        tk.Label(mc3, text="SUSPENDED / INACTIVE", font=("Helvetica", 10, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        mem_kpi_inact_lbl = tk.Label(mc3, text="0 Inactive", font=("Helvetica", 18, "bold"), fg="#FF6B6B", bg=BG_CARD)
        mem_kpi_inact_lbl.pack(anchor="w", pady=(2, 0))
        tk.Label(mc3, text="Discount Blocked", font=("Helvetica", 10), fg=CLR_WHITE, bg=BG_CARD).pack(anchor="w")

        # 4. Loyalty Benefit
        mc4 = tk.Frame(mem_kpi_row, bg=BG_CARD, padx=12, pady=10, highlightbackground=CLR_LILAC, highlightthickness=1)
        mc4.grid(row=0, column=3, sticky="nsew", padx=(4, 0))
        tk.Label(mc4, text="MEMBER BENEFIT", font=("Helvetica", 10, "bold"), fg=CLR_LILAC, bg=BG_CARD).pack(anchor="w")
        mem_kpi_rate_lbl = tk.Label(mc4, text="10% OFF", font=("Helvetica", 18, "bold"), fg=CLR_LILAC, bg=BG_CARD)
        mem_kpi_rate_lbl.pack(anchor="w", pady=(2, 0))
        tk.Label(mc4, text="All Beverage Purchases", font=("Helvetica", 10), fg=CLR_WHITE, bg=BG_CARD).pack(anchor="w")

        # Filter & Search Bar
        mem_filter_bar = tk.Frame(tab_members_frame, bg=BG_CARD, padx=12, pady=8)
        mem_filter_bar.pack(fill=tk.X, pady=(0, 6))

        tk.Label(
            mem_filter_bar,
            text="Filter Status:",
            font=("Helvetica", 11, "bold"),
            fg=CLR_WHITE,
            bg=BG_CARD,
        ).pack(side=tk.LEFT, padx=(0, 6))

        mem_status_var = tk.StringVar(value="ALL")
        mem_status_combo = ttk.Combobox(
            mem_filter_bar,
            textvariable=mem_status_var,
            values=["ALL", "ACTIVE ONLY", "INACTIVE ONLY"],
            state="readonly",
            width=16,
            font=("Helvetica", 11),
        )
        mem_status_combo.pack(side=tk.LEFT, padx=(0, 14))

        tk.Label(
            mem_filter_bar,
            text="Search Member / Card ID:",
            font=("Helvetica", 11, "bold"),
            fg=CLR_WHITE,
            bg=BG_CARD,
        ).pack(side=tk.LEFT, padx=(0, 6))

        mem_search_ent = tk.Entry(
            mem_filter_bar,
            font=("Helvetica", 11),
            bg=BG_SCREEN,
            fg=CLR_WHITE,
            insertbackground=CLR_WHITE,
            relief=tk.FLAT,
            width=18,
        )
        mem_search_ent.pack(side=tk.LEFT, padx=(0, 10), ipady=3)

        def on_mem_filter_change(*args):
            refresh_members_view()

        mem_status_combo.bind("<<ComboboxSelected>>", on_mem_filter_change)
        mem_search_ent.bind("<KeyRelease>", on_mem_filter_change)

        btn_mem_reset = tk.Button(
            mem_filter_bar,
            text="Reset Filter",
            font=("Helvetica", 11),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: (mem_status_var.set("ALL"), mem_search_ent.delete(0, tk.END), refresh_members_view()),
        )
        btn_mem_reset.pack(side=tk.LEFT)
        self._attach_button_animation(btn_mem_reset)

        # Members Treeview Frame
        members_tree_frame = tk.Frame(tab_members_frame, bg=BG_CARD, padx=8, pady=8)
        members_tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        members_tree = ttk.Treeview(
            members_tree_frame,
            style="Opt.Treeview",
            columns=("id", "card_id", "name", "status", "discount"),
            show="headings",
            height=9,
        )
        members_tree.heading("id", text="#")
        members_tree.heading("card_id", text="Loyalty Card ID / Barcode")
        members_tree.heading("name", text="Member Full Name")
        members_tree.heading("status", text="Account Status")
        members_tree.heading("discount", text="Discount Benefit")

        members_tree.column("id", width=60, anchor="center")
        members_tree.column("card_id", width=230, anchor="center")
        members_tree.column("name", width=280, anchor="w")
        members_tree.column("status", width=170, anchor="center")
        members_tree.column("discount", width=150, anchor="center")

        members_scroll = ttk.Scrollbar(members_tree_frame, orient=tk.VERTICAL, command=members_tree.yview)
        members_tree.configure(yscrollcommand=members_scroll.set)
        members_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        members_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        members_tree.tag_configure("tag_active", foreground=CLR_LIME)
        members_tree.tag_configure("tag_inactive", foreground="#FF6B6B")

        # Members Action Control Panel
        members_ctrl = tk.Frame(tab_members_frame, bg=BG_CARD, padx=14, pady=12)
        members_ctrl.pack(fill=tk.X)

        # Action 1: Add New Member
        def open_add_member_dialog():
            add_win = tk.Toplevel(dialog)
            add_win.title("Register New Loyalty Member")
            add_win.geometry("520x350")
            add_win.resizable(False, False)
            add_win.configure(bg=BG_APP)
            add_win.transient(dialog)
            add_win.grab_set()

            # Center on dialog
            add_win.update_idletasks()
            ax = dialog.winfo_x() + (dialog.winfo_width() - 520) // 2
            ay = dialog.winfo_y() + (dialog.winfo_height() - 350) // 2
            add_win.geometry(f"+{ax}+{ay}")

            top_f = tk.Frame(add_win, bg=BG_APP, padx=18, pady=12)
            top_f.pack(fill=tk.X)
            tk.Label(top_f, text="➕ REGISTER NEW LOYALTY MEMBER", font=("Helvetica", 14, "bold"), fg=CLR_LIME, bg=BG_APP).pack(anchor="w")
            tk.Label(top_f, text="Add a new cardholder to Edge Hill Loyalty Programme", font=("Helvetica", 11), fg=CLR_LILAC, bg=BG_APP).pack(anchor="w")

            form_f = tk.Frame(add_win, bg=BG_CARD, padx=18, pady=14)
            form_f.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 10))

            tk.Label(form_f, text="Member Full Name:", font=("Helvetica", 11, "bold"), fg=CLR_WHITE, bg=BG_CARD).pack(anchor="w")
            ent_new_name = tk.Entry(form_f, font=("Helvetica", 11), bg=BG_SCREEN, fg=CLR_WHITE, insertbackground=CLR_WHITE, relief=tk.FLAT)
            ent_new_name.pack(fill=tk.X, pady=(3, 10), ipady=4)

            tk.Label(form_f, text="Loyalty Card ID / Barcode:", font=("Helvetica", 11, "bold"), fg=CLR_WHITE, bg=BG_CARD).pack(anchor="w")
            cid_row = tk.Frame(form_f, bg=BG_CARD)
            cid_row.pack(fill=tk.X, pady=(3, 10))
            ent_new_cid = tk.Entry(cid_row, font=("Helvetica", 11), bg=BG_SCREEN, fg=CLR_WHITE, insertbackground=CLR_WHITE, relief=tk.FLAT)
            ent_new_cid.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)

            def generate_random_cid():
                import random
                rnd_num = random.randint(100, 999)
                ent_new_cid.delete(0, tk.END)
                ent_new_cid.insert(0, f"247480103B{rnd_num}")

            btn_gen_cid = tk.Button(
                cid_row,
                text="🎲 Auto ID",
                font=("Helvetica", 10, "bold"),
                bg=CLR_DEEP_PURPLE,
                fg=CLR_WHITE,
                activebackground=CLR_WHITE,
                activeforeground=CLR_DEEP_PURPLE,
                relief=tk.FLAT,
                bd=0,
                padx=10,
                pady=3,
                cursor="hand2",
                command=generate_random_cid,
            )
            btn_gen_cid.pack(side=tk.RIGHT, padx=(8, 0))

            is_act_var = tk.BooleanVar(value=True)
            chk_act = tk.Checkbutton(
                form_f,
                text="Account Active (Eligible for 10% Discount immediately)",
                variable=is_act_var,
                font=("Helvetica", 11),
                fg=CLR_LIME,
                bg=BG_CARD,
                selectcolor=BG_SCREEN,
                activebackground=BG_CARD,
                activeforeground=CLR_LIME,
            )
            chk_act.pack(anchor="w", pady=(4, 0))

            btn_box = tk.Frame(add_win, bg=BG_APP, padx=18, pady=12)
            btn_box.pack(fill=tk.X)

            def do_save_new_member():
                m_name = ent_new_name.get().strip()
                m_cid = ent_new_cid.get().strip()
                if not m_name:
                    messagebox.showwarning("Incomplete Information", "Please enter the member's full name.", parent=add_win)
                    ent_new_name.focus_set()
                    return
                if not m_cid:
                    messagebox.showwarning("Incomplete Information", "Please enter or generate a Card ID.", parent=add_win)
                    ent_new_cid.focus_set()
                    return

                # Check duplicate card id
                curr_members = load_members()
                for existing in curr_members:
                    if existing.card_id.upper() == m_cid.upper():
                        messagebox.showerror("Duplicate Card ID", f"Card ID '{m_cid}' is already assigned to {existing.member_name}!", parent=add_win)
                        return

                new_acc = LoyaltyAccount(card_id=m_cid, member_name=m_name, active=is_act_var.get())
                curr_members.append(new_acc)
                save_members(curr_members)
                if hasattr(self, "loyalty_scanner") and self.loyalty_scanner is not None:
                    self.loyalty_scanner._accounts = list(curr_members)

                log_activity("MEMBER_REGISTERED", f"Registered new member '{m_name}' (Card: {m_cid}, Active: {is_act_var.get()})")
                refresh_members_view()
                add_win.destroy()

            btn_submit = tk.Button(
                btn_box,
                text="💾 Save Member",
                font=("Helvetica", 11, "bold"),
                bg=BTN_BG,
                fg=BTN_FG,
                relief=tk.FLAT,
                bd=0,
                padx=16,
                pady=6,
                cursor="hand2",
                command=do_save_new_member,
            )
            btn_submit.pack(side=tk.RIGHT, padx=(8, 0))
            self._attach_button_animation(btn_submit)

            btn_cancel = tk.Button(
                btn_box,
                text="Cancel",
                font=("Helvetica", 11),
                bg=CLR_DEEP_PURPLE,
                fg=CLR_WHITE,
                relief=tk.FLAT,
                bd=0,
                padx=14,
                pady=6,
                cursor="hand2",
                command=add_win.destroy,
            )
            btn_cancel.pack(side=tk.RIGHT)
            self._attach_button_animation(btn_cancel)

        btn_add_mem = tk.Button(
            members_ctrl,
            text="➕ Add New Member",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=open_add_member_dialog,
        )
        btn_add_mem.pack(side=tk.LEFT, padx=(0, 8))
        self._attach_button_animation(btn_add_mem)

        # Action 2: Toggle Active Status
        def toggle_selected_member():
            sel = members_tree.selection()
            if not sel:
                messagebox.showinfo("Selection Required", "Please select a member row from the table to toggle active/inactive status.", parent=dialog)
                return

            item_vals = members_tree.item(sel[0], "values")
            card_id = item_vals[1]

            curr_members = load_members()
            found = False
            new_st = False
            for m in curr_members:
                if m.card_id == card_id:
                    m.active = not m.active
                    new_st = m.active
                    found = True
                    break

            if found:
                save_members(curr_members)
                if hasattr(self, "loyalty_scanner") and self.loyalty_scanner is not None:
                    self.loyalty_scanner._accounts = list(curr_members)
                st_text = "ACTIVE" if new_st else "INACTIVE"
                log_activity("MEMBER_STATUS_TOGGLED", f"Member {card_id} status changed to {st_text}")
                refresh_members_view()

        btn_toggle_mem = tk.Button(
            members_ctrl,
            text="🔄 Toggle Active / Inactive",
            font=("Helvetica", 11, "bold"),
            bg=CLR_DEEP_PURPLE,
            fg=CLR_WHITE,
            activebackground=CLR_WHITE,
            activeforeground=CLR_DEEP_PURPLE,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=toggle_selected_member,
        )
        btn_toggle_mem.pack(side=tk.LEFT, padx=(0, 8))
        self._attach_button_animation(btn_toggle_mem)

        # Action 3: Delete Member
        def delete_selected_member():
            sel = members_tree.selection()
            if not sel:
                messagebox.showinfo("Selection Required", "Please select a member row from the table to delete.", parent=dialog)
                return

            item_vals = members_tree.item(sel[0], "values")
            card_id = item_vals[1]
            m_name = item_vals[2]

            if messagebox.askyesno(
                "Confirm Member Deletion",
                f"Are you sure you want to delete member:\n\n• Name: {m_name}\n• Card ID: {card_id}\n\nThis action cannot be undone.",
                parent=dialog,
            ):
                curr_members = load_members()
                curr_members = [m for m in curr_members if m.card_id != card_id]
                save_members(curr_members)
                if hasattr(self, "loyalty_scanner") and self.loyalty_scanner is not None:
                    self.loyalty_scanner._accounts = list(curr_members)
                log_activity("MEMBER_DELETED", f"Member '{m_name}' ({card_id}) deleted by administrator")
                refresh_members_view()

        btn_del_mem = tk.Button(
            members_ctrl,
            text="🗑️ Delete Member",
            font=("Helvetica", 11, "bold"),
            bg=CLR_DEEP_PURPLE,
            fg=CLR_WHITE,
            activebackground=CLR_WHITE,
            activeforeground=CLR_DEEP_PURPLE,
            relief=tk.FLAT,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=delete_selected_member,
        )
        btn_del_mem.pack(side=tk.LEFT, padx=(0, 8))
        self._attach_button_animation(btn_del_mem)

        # Action 4: Refresh List
        btn_ref_mem = tk.Button(
            members_ctrl,
            text="🔄 Refresh",
            font=("Helvetica", 11),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=lambda: refresh_members_view(),
        )
        btn_ref_mem.pack(side=tk.LEFT, padx=(0, 8))
        self._attach_button_animation(btn_ref_mem)

        mem_count_lbl = tk.Label(members_ctrl, text="0 members found.", font=("Helvetica", 11), fg=CLR_LILAC, bg=BG_CARD)
        mem_count_lbl.pack(side=tk.RIGHT)

        def refresh_members_view():
            members_tree.delete(*members_tree.get_children())
            members_list = load_members()
            if hasattr(self, "loyalty_scanner") and self.loyalty_scanner is not None:
                self.loyalty_scanner._accounts = list(members_list)

            total_count = len(members_list)
            active_count = sum(1 for m in members_list if m.active)
            inactive_count = total_count - active_count

            mem_kpi_total_lbl.config(text=f"{total_count} Members")
            mem_kpi_active_lbl.config(text=f"{active_count} Active")
            mem_kpi_inact_lbl.config(text=f"{inactive_count} Inactive")

            status_f = mem_status_var.get().upper()
            search_q = mem_search_ent.get().strip().lower()

            displayed = 0
            for idx, m in enumerate(members_list, 1):
                if status_f == "ACTIVE ONLY" and not m.active:
                    continue
                if status_f == "INACTIVE ONLY" and m.active:
                    continue
                if search_q and (search_q not in m.member_name.lower() and search_q not in m.card_id.lower()):
                    continue

                st_tag = "tag_active" if m.active else "tag_inactive"
                st_text = "✅ ACTIVE" if m.active else "⛔ INACTIVE"
                disc_text = "10% OFF" if m.active else "None (Blocked)"

                members_tree.insert(
                    "",
                    tk.END,
                    values=(idx, m.card_id, m.member_name, st_text, disc_text),
                    tags=(st_tag,),
                )
                displayed += 1

            mem_count_lbl.config(text=f"Displaying {displayed} of {total_count} members.")

        # =================================================================
        # TAB 6: 📋 Activity & Audit Logs
        # =================================================================
        tab_logs_frame = tk.Frame(content_area, bg=BG_MIDDLE)
        tabs["logs"] = tab_logs_frame

        logs_hdr = tk.Frame(tab_logs_frame, bg=BG_CARD, padx=14, pady=10)
        logs_hdr.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            logs_hdr,
            text="📋 ACTIVITY & AUDIT TRAIL LOGS",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            logs_hdr,
            text="Persistent audit log events loaded from data/activity_log.json",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_CARD,
        ).pack(anchor="w")

        # Logs Treeview
        logs_tree_frame = tk.Frame(tab_logs_frame, bg=BG_CARD, padx=8, pady=8)
        logs_tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        logs_tree = ttk.Treeview(
            logs_tree_frame,
            style="Opt.Treeview",
            columns=("time", "event", "details"),
            show="headings",
            height=11,
        )
        logs_tree.heading("time", text="Timestamp")
        logs_tree.heading("event", text="Event Type")
        logs_tree.heading("details", text="Event Details")

        logs_tree.column("time", width=190, anchor="center")
        logs_tree.column("event", width=200, anchor="center")
        logs_tree.column("details", width=420, anchor="w")

        logs_scroll = ttk.Scrollbar(logs_tree_frame, orient=tk.VERTICAL, command=logs_tree.yview)
        logs_tree.configure(yscrollcommand=logs_scroll.set)
        logs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        logs_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def refresh_logs_view():
            logs_tree.delete(*logs_tree.get_children())
            log_file = os.path.join(DATA_DIR, "activity_log.json")
            if os.path.exists(log_file):
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for entry in reversed(data):
                            ts = entry.get("timestamp", "--")
                            ev = entry.get("event", "--")
                            dt = entry.get("details", "")
                            logs_tree.insert("", tk.END, values=(ts, ev, dt))
                except Exception as ex:
                    print(f"[Options] Error reading activity logs: {ex}")

        # Logs Control Frame
        logs_ctrl = tk.Frame(tab_logs_frame, bg=BG_CARD, padx=14, pady=12)
        logs_ctrl.pack(fill=tk.X)

        btn_refresh_logs = tk.Button(
            logs_ctrl,
            text="🔄 Refresh Event Logs",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=refresh_logs_view,
        )
        btn_refresh_logs.pack(side=tk.LEFT, padx=(0, 10))
        self._attach_button_animation(btn_refresh_logs)

        def clear_logs():
            log_file = os.path.join(DATA_DIR, "activity_log.json")
            try:
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write("[]\n")
                refresh_logs_view()
            except Exception as ex:
                print(f"[Options] Error clearing activity logs: {ex}")

        btn_clear_logs = tk.Button(
            logs_ctrl,
            text="🗑️ Clear Activity Logs",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=clear_logs,
        )
        btn_clear_logs.pack(side=tk.LEFT)
        self._attach_button_animation(btn_clear_logs)
        self._attach_button_animation(btn_clear_logs)

        # Default select Tab 1: Products
        select_tab("products")

    # =======================================================================
    # Page 2: Payment Method & Loyalty Membership Selection
    # =======================================================================
    def _build_page2_payment(self) -> None:
        """Page 2: Payment Method & Loyalty Membership Selection Screen."""
        page = tk.Frame(self.container, bg=BG_APP)
        self.pages["payment"] = page

        # 1. Header (Color #3A0C51)
        self._build_payment_header(page)

        # 2. Middle Content Area (Between Top & Bottom Bars: Color #D883FF)
        middle_area = tk.Frame(page, bg=BG_MIDDLE)
        middle_area.pack(fill=tk.BOTH, expand=True)

        content_split = tk.Frame(middle_area, bg=BG_MIDDLE)
        content_split.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        # Left Column: Order Summary Card (Width: ~350px)
        left_summary = tk.Frame(content_split, bg=BG_CARD, width=350, padx=16, pady=12)
        left_summary.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 14))
        left_summary.pack_propagate(False)
        self._build_order_summary_panel(left_summary)

        # Right Column: Loyalty Membership & Payment Method Selection
        right_panel = tk.Frame(content_split, bg=BG_MIDDLE)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self._build_payment_options_panel(right_panel)

        # 3. Footer (Color #3A0C51)
        self._build_payment_footer(page)

    def _build_payment_header(self, parent: tk.Frame) -> None:
        """Top banner for Page 2 (Background: #3A0C51)."""
        header = tk.Frame(parent, bg=BG_APP, height=60, padx=20)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand_frame = tk.Frame(header, bg=BG_APP)
        brand_frame.pack(side=tk.LEFT, fill=tk.Y)

        logo_path = os.path.join(os.path.dirname(__file__), "assets", "edge_hill_logo.png")
        if os.path.exists(logo_path) and hasattr(self, "header_logo"):
            logo_lbl = tk.Label(
                brand_frame,
                image=self.header_logo,
                bg=BG_APP,
            )
            logo_lbl.pack(side=tk.LEFT, pady=8)
        else:
            tk.Label(
                brand_frame,
                text="Edge Hill University",
                font=("Georgia", 16, "bold"),
                fg=CLR_WHITE,
                bg=BG_APP,
            ).pack(side=tk.LEFT, pady=14)

        tk.Label(
            brand_frame,
            text="• Campus Vending Machine",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LILAC,
            bg=BG_APP,
        ).pack(side=tk.LEFT, padx=14, pady=16)

        # Step Indicator Badge
        step_badge = tk.Label(
            header,
            text="STEP 2: PAYMENT & LOYALTY",
            font=("Helvetica", 11, "bold"),
            fg=BTN_FG,
            bg=BTN_BG,
            padx=12,
            pady=4,
        )
        step_badge.pack(side=tk.RIGHT, pady=13)

    def _build_order_summary_panel(self, parent: tk.Frame) -> None:
        """Left panel on Page 2 detailing the selected beverage, discount, and total due."""
        tk.Label(
            parent,
            text="🛒 ORDER SUMMARY",
            font=("Helvetica", 16, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 4))

        # Drink Graphic Canvas / Showcase Box
        self.summary_canvas = tk.Canvas(
            parent,
            width=120,
            height=72,
            bg=CLR_WHITE,
            highlightthickness=1,
            highlightbackground=CLR_LILAC,
        )
        self.summary_canvas.pack(pady=3)

        # Drink Name
        self.summary_name_lbl = tk.Label(
            parent,
            text="Selected Drink",
            font=("Helvetica", 16, "bold"),
            fg=CLR_WHITE,
            bg=BG_CARD,
        )
        self.summary_name_lbl.pack(fill=tk.X, pady=(2, 1))

        # Drink Description
        self.summary_desc_lbl = tk.Label(
            parent,
            text="",
            font=("Helvetica", 12),
            fg=CLR_LILAC,
            bg=BG_CARD,
            wraplength=320,
            justify=tk.CENTER,
        )
        self.summary_desc_lbl.pack(fill=tk.X, pady=(0, 4))

        # Thin divider
        tk.Frame(parent, bg=CLR_LILAC, height=1).pack(fill=tk.X, pady=(2, 6))

        # Price Breakdown
        prices_frame = tk.Frame(parent, bg=BG_CARD)
        prices_frame.pack(fill=tk.X, pady=(0, 4))

        row1 = tk.Frame(prices_frame, bg=BG_CARD)
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="Drink Regular Price:", font=("Helvetica", 12, "bold"), fg=CLR_WHITE, bg=BG_CARD).pack(side=tk.LEFT)
        self.summary_base_price_lbl = tk.Label(row1, text="£0.00", font=("Menlo", 13, "bold"), fg=CLR_WHITE, bg=BG_CARD)
        self.summary_base_price_lbl.pack(side=tk.RIGHT)

        row2 = tk.Frame(prices_frame, bg=BG_CARD)
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="Membership Discount:", font=("Helvetica", 12, "bold"), fg=CLR_WHITE, bg=BG_CARD).pack(side=tk.LEFT)
        self.summary_discount_lbl = tk.Label(row2, text="£0.00", font=("Menlo", 13, "bold"), fg=CLR_LILAC, bg=BG_CARD)
        self.summary_discount_lbl.pack(side=tk.RIGHT)

        # Total Amount Due Screen Box
        screen_frame = tk.Frame(
            parent,
            bg=BG_SCREEN,
            padx=12,
            pady=8,
            highlightbackground=CLR_LIME,
            highlightthickness=2,
        )
        screen_frame.pack(fill=tk.X, pady=(6, 10))

        tk.Label(
            screen_frame,
            text="TOTAL AMOUNT DUE",
            font=("Helvetica", 11, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(anchor="w")

        self.summary_total_lbl = tk.Label(
            screen_frame,
            text="£0.00",
            font=("Menlo", 26, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        self.summary_total_lbl.pack(anchor="e", pady=(2, 0))

        # Back to catalogue button (at the very bottom)
        self.back_btn = tk.Button(
            parent,
            text="[ 4 ] ← Change Drink / Back (Esc)",
            font=("Helvetica", 13, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            padx=12,
            pady=7,
            command=self._on_cancel_payment,
        )
        self.back_btn.pack(side=tk.BOTTOM, fill=tk.X)
        self._attach_button_animation(self.back_btn)

        # Member Information Box (In bottom-left area, right above back button)
        self.member_info_box = tk.Frame(
            parent,
            bg=BG_SCREEN,
            padx=10,
            pady=8,
            highlightbackground=CLR_LILAC,
            highlightthickness=1,
        )
        self.member_info_box.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10))

        mem_hdr = tk.Frame(self.member_info_box, bg=BG_SCREEN)
        mem_hdr.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            mem_hdr,
            text="👤 MEMBER PROFILE",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        ).pack(side=tk.LEFT)

        self.summary_member_badge = tk.Label(
            mem_hdr,
            text="NOT SCANNED",
            font=("Helvetica", 9, "bold"),
            fg=CLR_LILAC,
            bg=BG_CARD,
            padx=6,
            pady=1,
        )
        self.summary_member_badge.pack(side=tk.RIGHT)

        mem_name_row = tk.Frame(self.member_info_box, bg=BG_SCREEN)
        mem_name_row.pack(fill=tk.X, pady=2)

        tk.Label(
            mem_name_row,
            text="Name:",
            font=("Helvetica", 11, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(side=tk.LEFT)

        self.summary_member_name_lbl = tk.Label(
            mem_name_row,
            text="No Card Scanned",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
            anchor="e",
        )
        self.summary_member_name_lbl.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        mem_card_row = tk.Frame(self.member_info_box, bg=BG_SCREEN)
        mem_card_row.pack(fill=tk.X, pady=2)

        tk.Label(
            mem_card_row,
            text="Card ID:",
            font=("Helvetica", 11, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(side=tk.LEFT)

        self.summary_member_card_lbl = tk.Label(
            mem_card_row,
            text="------",
            font=("Menlo", 11, "bold"),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
            anchor="e",
        )
        self.summary_member_card_lbl.pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def _build_payment_options_panel(self, parent: tk.Frame) -> None:
        """Right panel on Page 2 with Loyalty Card scan and Cash / Card payment choices."""
        # --- Section 1: Loyalty Membership Card ---
        loyalty_card = tk.Frame(
            parent,
            bg=BG_CARD,
            padx=16,
            pady=12,
            highlightthickness=1,
            highlightbackground=CLR_LIME,
        )
        loyalty_card.pack(fill=tk.X, pady=(0, 10))

        hdr_row = tk.Frame(loyalty_card, bg=BG_CARD)
        hdr_row.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            hdr_row,
            text="⭐ EDGE HILL LOYALTY CLUB",
            font=("Helvetica", 16, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(side=tk.LEFT)

        discount_badge = tk.Label(
            hdr_row,
            text="10% OFF DISCOUNT",
            font=("Helvetica", 12, "bold"),
            fg=BTN_FG,
            bg=BTN_BG,
            padx=8,
            pady=3,
        )
        discount_badge.pack(side=tk.RIGHT)

        tk.Label(
            loyalty_card,
            text="Scan your Edge Hill University membership or student card to apply an instant 10% discount.",
            font=("Helvetica", 13),
            fg=CLR_WHITE,
            bg=BG_CARD,
            wraplength=480,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 6))

        # Status box
        status_box = tk.Frame(loyalty_card, bg=BG_SCREEN, padx=10, pady=6)
        status_box.pack(fill=tk.X, pady=(0, 8))

        self.loyalty_status_lbl = tk.Label(
            status_box,
            text="💳 Status: No Membership Card Scanned",
            font=("Helvetica", 13, "bold"),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
        )
        self.loyalty_status_lbl.pack(anchor="w")

        # Scan button
        self.scan_loyalty_btn = tk.Button(
            loyalty_card,
            text="[ 1 ] 📷 Scan Member Card",
            font=("Helvetica", 14, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            padx=14,
            pady=8,
            command=self._open_loyalty_scan_dialog,
        )
        self.scan_loyalty_btn.pack(fill=tk.X)
        self._attach_button_animation(self.scan_loyalty_btn)

        # --- Section 2: Choose Payment Method ---
        pay_card = tk.Frame(
            parent,
            bg=BG_CARD,
            padx=16,
            pady=12,
            highlightthickness=1,
            highlightbackground=CLR_WHITE,
        )
        pay_card.pack(fill=tk.BOTH, expand=True)

        pay_hdr = tk.Frame(pay_card, bg=BG_CARD)
        pay_hdr.pack(fill=tk.X, pady=(0, 4))

        tk.Label(
            pay_hdr,
            text="💳 SELECT PAYMENT METHOD",
            font=("Helvetica", 16, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(side=tk.LEFT)

        tk.Label(
            pay_card,
            text="Choose your preferred payment method below to complete your purchase:",
            font=("Helvetica", 13),
            fg=CLR_WHITE,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 8))

        # Side-by-side Buttons Container (Responsive Grid)
        btn_container = tk.Frame(pay_card, bg=BG_CARD)
        btn_container.pack(fill=tk.BOTH, expand=True)
        btn_container.columnconfigure(0, weight=1, uniform="pay")
        btn_container.columnconfigure(1, weight=1, uniform="pay")

        # 1. Cash Button Box (Column 0)
        cash_box = tk.Frame(btn_container, bg=BG_CARD, padx=5)
        cash_box.grid(row=0, column=0, sticky="nsew")

        self.cash_btn = tk.Button(
            cash_box,
            text="[ 2 ] 💵 PAY WITH CASH",
            font=("Helvetica", 16, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            pady=12,
            command=self._on_choose_cash,
        )
        self.cash_btn.pack(fill=tk.X)
        self._attach_button_animation(self.cash_btn)

        tk.Label(
            cash_box,
            text="Accepts £2, £1, 50p, 20p, 10p & notes\nAutomatic change return",
            font=("Helvetica", 12),
            fg=CLR_LILAC,
            bg=BG_CARD,
            justify=tk.CENTER,
        ).pack(pady=(4, 0))

        # 2. Card Button Box (Column 1)
        card_box = tk.Frame(btn_container, bg=BG_CARD, padx=5)
        card_box.grid(row=0, column=1, sticky="nsew")

        self.card_btn = tk.Button(
            card_box,
            text="[ 3 ] 💳 PAY WITH CARD / QR",
            font=("Helvetica", 16, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            pady=12,
            command=self._on_choose_card,
        )
        self.card_btn.pack(fill=tk.X)
        self._attach_button_animation(self.card_btn)

        tk.Label(
            card_box,
            text="Scan QR Code with phone to checkout\nApple Pay, Google Pay & Cards supported",
            font=("Helvetica", 12),
            fg=CLR_LILAC,
            bg=BG_CARD,
            justify=tk.CENTER,
        ).pack(pady=(4, 0))

    def _build_payment_footer(self, parent: tk.Frame) -> None:
        """Bottom status bar for Page 2 (Background: #3A0C51)."""
        footer = tk.Frame(parent, bg=BG_APP, height=40, padx=20)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        tk.Label(
            footer,
            text="Press keypad 1, 2, 3 or Esc / 4 to control payment terminal",
            font=("Helvetica", 12, "bold"),
            fg=CLR_WHITE,
            bg=BG_APP,
        ).pack(side=tk.RIGHT, pady=10)

    def _refresh_payment_page(self) -> None:
        """Refreshes order summary and pricing when entering or updating Page 2."""
        if not self.selected_product:
            return

        prod = self.selected_product
        # 1. Update Canvas Artwork / Product Photo
        if hasattr(self, "summary_canvas"):
            render_product_artwork(
                canvas=self.summary_canvas,
                prod=prod,
                width=120,
                height=72,
                photo_cache=self._product_images,
                default_bg=CLR_WHITE,
                fallback_bg=BG_CARD,
            )

        # 2. Update Name & Desc
        if hasattr(self, "summary_name_lbl"):
            self.summary_name_lbl.config(text=f"{prod['name']} (No. {prod['slot_num']})")
        if hasattr(self, "summary_desc_lbl"):
            self.summary_desc_lbl.config(text=prod.get("desc", ""))

        # 3. Update Base Price
        base_pence = prod["price"]
        if hasattr(self, "summary_base_price_lbl"):
            self.summary_base_price_lbl.config(text=f"£{base_pence / 100:.2f} ({base_pence}p)")

        # 4. Check Loyalty Discount & Member Profile
        if self.controller.loyaltyApplied:
            amount_due = self.controller.amountDue
            discount_pence = base_pence - amount_due
            discount_text = f"✅ -10% (-£{discount_pence / 100:.2f})"
            discount_color = CLR_LIME
            status_text = "🎉 Verified Member • 10% Discount Active"
            status_color = CLR_LIME

            account = getattr(self.loyalty_scanner, "_last_scanned", None)
            if account:
                member_name = getattr(account, "member_name", "Verified Member")
                card_id = getattr(account, "card_id", "------")
            elif hasattr(self, "scanned_member") and self.scanned_member:
                member_name = self.scanned_member.get("name", "Verified Member")
                card_id = self.scanned_member.get("card_id", "------")
            else:
                member_name = "Verified Member"
                card_id = "------"

            if hasattr(self, "summary_member_name_lbl"):
                self.summary_member_name_lbl.config(text=member_name, fg=CLR_LIME)
            if hasattr(self, "summary_member_card_lbl"):
                self.summary_member_card_lbl.config(text=card_id, fg=CLR_LIME)
            if hasattr(self, "summary_member_badge"):
                self.summary_member_badge.config(text="VERIFIED", fg=BTN_FG, bg=CLR_LIME)
            if hasattr(self, "member_info_box"):
                self.member_info_box.config(highlightbackground=CLR_LIME, highlightthickness=2)
        else:
            amount_due = base_pence
            discount_text = "£0.00 (No Card Scanned)"
            discount_color = CLR_LILAC
            status_text = "💳 Status: No Membership Card Scanned"
            status_color = CLR_LILAC

            if hasattr(self, "summary_member_name_lbl"):
                self.summary_member_name_lbl.config(text="No Card Scanned", fg=CLR_LILAC)
            if hasattr(self, "summary_member_card_lbl"):
                self.summary_member_card_lbl.config(text="------", fg=CLR_LILAC)
            if hasattr(self, "summary_member_badge"):
                self.summary_member_badge.config(text="NOT SCANNED", fg=CLR_LILAC, bg=BG_CARD)
            if hasattr(self, "member_info_box"):
                self.member_info_box.config(highlightbackground=CLR_LILAC, highlightthickness=1)

        if hasattr(self, "summary_discount_lbl"):
            self.summary_discount_lbl.config(text=discount_text, fg=discount_color)

        if hasattr(self, "summary_total_lbl"):
            self.summary_total_lbl.config(text=f"£{amount_due / 100:.2f} ({amount_due}p)")

        if hasattr(self, "loyalty_status_lbl"):
            self.loyalty_status_lbl.config(text=status_text, fg=status_color)

        # 5. Update Cash & Card Channel Availability on Page 2
        if hasattr(self, "cash_btn") and self.cash_btn.winfo_exists():
            if getattr(self, "cash_enabled", True):
                self.cash_btn.config(
                    text="[ 2 ] 💵 PAY WITH CASH",
                    state=tk.NORMAL,
                    bg=BTN_BG,
                    fg=BTN_FG,
                    cursor="hand2",
                )
            else:
                self.cash_btn.config(
                    text="[ 2 ] 💵 CASH (UNAVAILABLE)",
                    state=tk.DISABLED,
                    bg="#444444",
                    fg="#888888",
                    cursor="arrow",
                )

        if hasattr(self, "card_btn") and self.card_btn.winfo_exists():
            if getattr(self, "card_enabled", True):
                gw = getattr(self, "active_gateway_name", "stripe").upper()
                gw_lbl = "CARD / QR" if gw == "STRIPE" else f"CARD / {gw}"
                self.card_btn.config(
                    text=f"[ 3 ] 💳 PAY WITH {gw_lbl}",
                    state=tk.NORMAL,
                    bg=BTN_BG,
                    fg=BTN_FG,
                    cursor="hand2",
                )
            else:
                self.card_btn.config(
                    text="[ 3 ] 💳 CARD / QR (UNAVAILABLE)",
                    state=tk.DISABLED,
                    bg="#444444",
                    fg="#888888",
                    cursor="arrow",
                )

    def _on_cancel_payment(self) -> None:
        """Cancels payment and slides back to catalogue with reverse motion."""
        self.controller.cancel()
        if hasattr(self, "loyalty_scanner"):
            self.loyalty_scanner._last_scanned = None
        self.scanned_member = None
        self.entered_slot.set("--")
        self.selected_product = None
        self._highlight_active_card(None)
        self._update_preview(None)
        self.root.focus_force()
        self.root.focus_set()
        self.root.after(50, lambda: (self.root.focus_force(), self.root.focus_set()))
        self.transition_to_page("catalogue", direction="right")
        self.root.after(300, lambda: (self.root.focus_force(), self.root.focus_set()))

    def _open_loyalty_scan_dialog(self) -> None:
        """
        Opens a modal dialog to scan Code 128 linear barcodes using camera,
        with a Cancel button to dismiss.
        """
        if self.controller.loyaltyApplied:
            if hasattr(self, "loyalty_status_lbl") and self.loyalty_status_lbl.winfo_exists():
                self.loyalty_status_lbl.config(text="⚠️ Loyalty discount is already active for this order!", fg=CLR_LIME)
            return

        dialog = tk.Toplevel(self.root)
        self._active_modal = dialog
        dialog.title("Scan Loyalty Card")
        dw, dh = 580, 480
        dialog.geometry(f"{dw}x{dh}")
        dialog.minsize(520, 460)
        dialog.configure(bg=BG_APP)
        dialog.transient(self.root)
        dialog.grab_set()

        # Center on parent window
        dialog.update_idletasks()
        x = max(10, self.root.winfo_x() + (self.root.winfo_width() - dw) // 2)
        y = max(10, self.root.winfo_y() + (self.root.winfo_height() - dh) // 2)
        dialog.geometry(f"+{x}+{y}")

        dlg_hdr = tk.Frame(dialog, bg=BG_APP, padx=16, pady=10)
        dlg_hdr.pack(fill=tk.X)

        tk.Label(
            dlg_hdr,
            text="⭐ EDGE HILL LOYALTY CLUB",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_APP,
        ).pack(anchor="w")

        body = tk.Frame(dialog, bg=BG_MIDDLE, padx=10, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        content_card = tk.Frame(body, bg=BG_CARD, padx=12, pady=10)
        content_card.pack(fill=tk.BOTH, expand=True)

        scanner_state = {
            "cap": None,
            "running": False,
            "photo_ref": None,
            "after_id": None,
        }

        camera_frame = tk.Frame(content_card, bg=BG_CARD)
        camera_frame.pack(fill=tk.BOTH, expand=True)

        def cleanup_camera():
            scanner_state["running"] = False
            if scanner_state["after_id"]:
                try:
                    dialog.after_cancel(scanner_state["after_id"])
                except Exception:
                    pass
                scanner_state["after_id"] = None
            if scanner_state["cap"] is not None:
                try:
                    scanner_state["cap"].release()
                except Exception:
                    pass
                scanner_state["cap"] = None

        def on_close_dialog():
            cleanup_camera()
            try:
                dialog.grab_release()
                dialog.destroy()
            except Exception:
                pass
            self._active_modal = None
            self.root.focus_force()
            self.root.focus_set()
            self.root.after(50, lambda: (self.root.focus_force(), self.root.focus_set()))

        dialog.protocol("WM_DELETE_WINDOW", on_close_dialog)

        def on_loyalty_dlg_key(event: tk.Event):
            if event.keysym in ("Escape", "BackSpace") or event.char in ("4",):
                on_close_dialog()

        dialog.bind("<Key>", on_loyalty_dlg_key)

        # -------------------------------------------------------------
        # CAMERA SCANNER VIEW
        # -------------------------------------------------------------
        tk.Label(
            camera_frame,
            text="📷 SCAN MEMBER CARD BARCODE",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(pady=(0, 4))

        video_lbl = tk.Label(camera_frame, bg=BG_SCREEN)
        video_lbl.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        cam_status_lbl = tk.Label(
            camera_frame,
            text="",
            font=("Helvetica", 10, "bold"),
            fg=CLR_LILAC,
            bg=BG_CARD,
        )
        cam_status_lbl.pack(pady=(4, 6))

        cam_btn_row = tk.Frame(camera_frame, bg=BG_CARD)
        cam_btn_row.pack(fill=tk.X, pady=(2, 0))

        cam_cancel_btn = tk.Button(
            cam_btn_row,
            text="[ Esc ] Cancel",
            font=("Helvetica", 12, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            activebackground=BTN_BG,
            activeforeground=BTN_FG,
            relief=tk.FLAT,
            padx=16,
            pady=8,
            cursor="hand2",
            command=on_close_dialog,
        )
        cam_cancel_btn.pack(fill=tk.X)
        self._attach_button_animation(
            cam_cancel_btn,
            normal_bg=BTN_BG,
            normal_fg=BTN_FG,
            hover_bg=CLR_WHITE,
            hover_fg=BTN_FG,
        )

        # -------------------------------------------------------------
        # Camera Loop & Code 128 Detection
        # -------------------------------------------------------------
        def update_camera_stream():
            if not scanner_state["running"] or scanner_state["cap"] is None or not dialog.winfo_exists():
                return

            cap = scanner_state["cap"]
            ret, frame = cap.read()
            if ret and frame is not None:
                # 1. Mirror horizontally for natural user experience
                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape

                # 2. Draw wide horizontal green targeting reticle for Code 128
                box_w = int(w * 0.76)
                box_h = int(h * 0.38)
                x1 = (w - box_w) // 2
                y1 = (h - box_h) // 2
                x2 = x1 + box_w
                y2 = y1 + box_h

                cv2.rectangle(frame, (x1, y1), (x2, y2), (45, 239, 186), 2)
                mid_y = y1 + (box_h // 2)
                cv2.line(frame, (x1 + 10, mid_y), (x2 - 10, mid_y), (255, 131, 216), 1)

                cv2.putText(
                    frame,
                    "SCAN MEMBER CARD BARCODE HERE",
                    (x1 + 10, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (45, 239, 186),
                    2,
                )

                # 3. Code 128 Barcode Detection using zxingcpp
                detected_card_id = None
                if HAS_ZXING and zxingcpp is not None:
                    try:
                        results = zxingcpp.read_barcodes(frame, formats=zxingcpp.BarcodeFormat.Code128)
                        for r in results:
                            if r.text and r.text.strip():
                                detected_card_id = r.text.strip()
                                break
                    except Exception:
                        pass

                # Fallback to OpenCV barcode detector
                if not detected_card_id and hasattr(cv2, "barcode"):
                    try:
                        bd = cv2.barcode.BarcodeDetector()
                        ok, decoded_info, _, _ = bd.detectAndDecode(frame)
                        if ok:
                            if isinstance(decoded_info, (list, tuple)) and decoded_info:
                                detected_card_id = decoded_info[0].strip()
                            elif isinstance(decoded_info, str) and decoded_info.strip():
                                detected_card_id = decoded_info.strip()
                    except Exception:
                        pass

                if detected_card_id:
                    cleanup_camera()
                    cam_status_lbl.config(
                        text=f"✅ Scanned Barcode: '{detected_card_id}' — Verifying...",
                        fg=CLR_LIME,
                    )
                    success = self.controller.scanLoyalty(detected_card_id)
                    if success:
                        account = getattr(self.loyalty_scanner, "_last_scanned", None)
                        if account:
                            self.scanned_member = {
                                "name": getattr(account, "member_name", "Verified Member"),
                                "card_id": getattr(account, "card_id", detected_card_id),
                            }
                        cam_status_lbl.config(
                            text="🎉 Card Verified! 10% Discount Applied!",
                            fg=CLR_LIME,
                        )
                        self._refresh_payment_page()
                        dialog.after(700, on_close_dialog)
                    else:
                        cam_status_lbl.config(
                            text=f"❌ Card '{detected_card_id}' is invalid or inactive.",
                            fg=CLR_LILAC,
                        )
                        def resume_camera_scan():
                            if dialog.winfo_exists():
                                cam_status_lbl.config(
                                    text="",
                                    fg=CLR_LILAC,
                                )
                                start_camera()
                        dialog.after(2000, resume_camera_scan)
                    return

                # 4. Render to UI
                render_w = 520
                render_h = 280
                if HAS_PIL and Image is not None and ImageTk is not None:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(rgb_frame)
                    pil_img = pil_img.resize((render_w, render_h), Image.Resampling.LANCZOS)
                    scanner_state["photo_ref"] = ImageTk.PhotoImage(image=pil_img)
                else:
                    resized = cv2.resize(frame, (render_w, render_h))
                    ret_enc, buf = cv2.imencode(".png", resized)
                    if ret_enc:
                        b64 = base64.b64encode(buf).decode("ascii")
                        scanner_state["photo_ref"] = tk.PhotoImage(data=b64)
                    else:
                        scanner_state["photo_ref"] = None

                if scanner_state["photo_ref"] and video_lbl.winfo_exists():
                    video_lbl.config(image=scanner_state["photo_ref"])

            if scanner_state["running"] and dialog.winfo_exists():
                scanner_state["after_id"] = dialog.after(30, update_camera_stream)

        def start_camera():
            if not HAS_CV2 or cv2 is None:
                cam_status_lbl.config(
                    text="⚠️ OpenCV unavailable. Camera barcode scanning is disabled.",
                    fg=CLR_LILAC,
                )
                return

            try:
                scanner_state["cap"] = cv2.VideoCapture(0)
                if not scanner_state["cap"].isOpened():
                    scanner_state["cap"] = None
                    cam_status_lbl.config(
                        text="⚠️ Camera device unavailable or disconnected.",
                        fg=CLR_LILAC,
                    )
                    return
            except Exception:
                scanner_state["cap"] = None
                cam_status_lbl.config(
                    text="⚠️ Camera device unavailable or disconnected.",
                    fg=CLR_LILAC,
                )
                return

            scanner_state["running"] = True
            update_camera_stream()

        # Start camera scanner directly
        start_camera()

    def _on_choose_cash(self) -> None:
        """Handles Cash payment selection and opens cash insertion dialog."""
        if not getattr(self, "cash_enabled", True):
            messagebox.showwarning(
                "Payment Unavailable",
                "Cash payment is currently disabled by system administration.\n"
                "Please choose another payment method or contact support.",
            )
            return
        self._last_payment_method = "Cash Receiver"
        amount_due = self.controller.amountDue
        self.controller.startPayment(self.cash_receiver)
        self.cash_receiver.processPayment(amount_due)

        # Start 60-second TransactionTimer for cash payment
        self.timer.start()

        dialog = tk.Toplevel(self.root)
        self._active_modal = dialog
        dialog.title("Cash Payment Terminal")
        cw, ch = 540, 590
        dialog.geometry(f"{cw}x{ch}")
        dialog.resizable(False, False)
        dialog.configure(bg=BG_APP)
        dialog.transient(self.root)
        dialog.grab_set()

        cash_state = {
            "after_id": None,
            "completed": False,
        }

        def cleanup_cash():
            if cash_state["after_id"]:
                try:
                    dialog.after_cancel(cash_state["after_id"])
                except Exception:
                    pass
                cash_state["after_id"] = None

        def on_cancel():
            cash_state["completed"] = True
            cleanup_cash()
            self.timer.stop()
            self._on_cancel_cash_dialog(dialog)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        # Center on parent
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - cw) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - ch) // 2
        dialog.geometry(f"+{x}+{y}")

        top_bar = tk.Frame(dialog, bg=BG_APP, padx=16, pady=12)
        top_bar.pack(fill=tk.X)
        tk.Label(
            top_bar,
            text="💵 CASH PAYMENT TERMINAL",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_APP,
        ).pack(side=tk.LEFT)

        initial_timeout = getattr(self, "session_timeout_seconds", 60)
        cash_timer_badge = tk.Label(
            top_bar,
            text=f"⏱️ {initial_timeout}s",
            font=("Menlo", 12, "bold"),
            fg=CLR_WHITE,
            bg=BG_CARD,
            padx=8,
            pady=3,
        )
        cash_timer_badge.pack(side=tk.RIGHT)

        def tick_cash_timer():
            if not dialog.winfo_exists() or cash_state["completed"]:
                return
            if self.timer.hasExpired():
                to_sec = getattr(self, "session_timeout_seconds", 60)
                print(f"[Cash Payment] {to_sec}s TransactionTimer expired without full payment. Refunding all inserted cash.")
                cash_state["completed"] = True
                cleanup_cash()
                self.timer.stop()
                self._on_timeout_cash_dialog(dialog)
                return

            rem_sec = self.timer.getRemainingTime()
            if cash_timer_badge.winfo_exists():
                if rem_sec <= 10:
                    cash_timer_badge.config(text=f"⏱️ {rem_sec}s", fg="#FF4444")
                elif rem_sec <= 20:
                    cash_timer_badge.config(text=f"⏱️ {rem_sec}s", fg=CLR_LILAC)
                else:
                    cash_timer_badge.config(text=f"⏱️ {rem_sec}s", fg=CLR_WHITE)
            cash_state["after_id"] = dialog.after(1000, tick_cash_timer)

        cash_state["after_id"] = dialog.after(1000, tick_cash_timer)

        body = tk.Frame(dialog, bg=BG_MIDDLE, padx=16, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        screen = tk.Frame(body, bg=BG_SCREEN, padx=16, pady=12, highlightthickness=2, highlightbackground=CLR_LIME)
        screen.pack(fill=tk.X, pady=(0, 12))

        lbl_due = tk.Label(
            screen,
            text=f"Amount Due: £{amount_due / 100:.2f} ({amount_due}p)",
            font=("Helvetica", 12, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        )
        lbl_due.pack(anchor="w")

        lbl_inserted = tk.Label(
            screen,
            text="Total Inserted: £0.00 (0p)",
            font=("Menlo", 16, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        lbl_inserted.pack(anchor="w", pady=(4, 2))

        lbl_status = tk.Label(
            screen,
            text=f"Please insert coins or notes (£{amount_due / 100:.2f} remaining)",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
        )
        lbl_status.pack(anchor="w")

        lbl_change = tk.Label(
            screen,
            text="",
            font=("Helvetica", 10, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
            wraplength=480,
            justify="left",
        )
        lbl_change.pack(anchor="w", pady=(2, 0))

        coins_box = tk.Frame(body, bg=BG_CARD, padx=12, pady=10)
        coins_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tk.Label(
            coins_box,
            text="Simulate Cash Insertion — Accepted: 10p to £10.00 (Keypad 1 - 9):",
            font=("Helvetica", 11, "bold"),
            fg=CLR_WHITE,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 2))

        tk.Label(
            coins_box,
            text="⚠️ Note: £20 and £50 banknotes will not be accepted and will be returned.",
            font=("Helvetica", 9),
            fg=CLR_LILAC,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 6))

        grid_btn = tk.Frame(coins_box, bg=BG_CARD)
        grid_btn.pack(fill=tk.X)

        denominations = [
            ("[ 1 ] 10p", 10),
            ("[ 2 ] 20p", 20),
            ("[ 3 ] 50p", 50),
            ("[ 4 ] £1.00", 100),
            ("[ 5 ] £2.00", 200),
            ("[ 6 ] £5.00 Note", 500),
            ("[ 7 ] £10.00 Note", 1000),
            ("[ 8 ] £20 Note ⚠️", 2000),
            ("[ 9 ] £50 Note ⚠️", 5000),
        ]

        coin_buttons = []

        def insert_coin(pence: int):
            accepted = self.cash_receiver.insertItem(pence)
            inserted = self.cash_receiver._total
            rem = max(0, amount_due - inserted)
            lbl_inserted.config(text=f"Total Inserted: £{inserted / 100:.2f} ({inserted}p)")

            if not accepted:
                # Banknote or coin is rejected and returned to customer
                if pence >= 100:
                    val_str = f"£{pence / 100:.2f}"
                else:
                    val_str = f"{pence}p"

                note_or_coin = "Banknote" if pence >= 500 else "Coin"
                lbl_status.config(
                    text=f"❌ {val_str} {note_or_coin} Rejected! Accepted: 10p to £10.00 only.",
                    fg="#FF6B6B",
                )
                lbl_change.config(
                    text=f"↩️ {note_or_coin} Ejected & Returned: {val_str} was not accepted and has been returned to customer.",
                    fg="#FF6B6B",
                )
                screen.config(highlightbackground="#FF6B6B")
                dialog.after(1400, lambda: screen.config(highlightbackground=CLR_LIME) if dialog.winfo_exists() else None)
                log_activity("CASH_REJECTED", f"{val_str} {note_or_coin.lower()} rejected by CashValidator and returned (Accepted: 10p to £10.00 only)")

                def restore_prompt():
                    if dialog.winfo_exists() and not cash_state["completed"]:
                        cur_inserted = self.cash_receiver._total
                        cur_rem = max(0, amount_due - cur_inserted)
                        lbl_status.config(
                            text=f"Awaiting cash: £{cur_rem / 100:.2f} ({cur_rem}p remaining) — Accepted: 10p to £10",
                            fg=CLR_LILAC,
                        )
                dialog.after(3500, restore_prompt)
                return

            # Accepted item
            screen.config(highlightbackground=CLR_LIME)
            lbl_change.config(text="", fg=CLR_LIME)

            if self.cash_receiver._state == CashReceiverState.PAYMENT_COMPLETE:
                cash_state["completed"] = True
                cleanup_cash()
                self.timer.stop()
                overpaid = max(0, inserted - amount_due)
                change_summary = getattr(self.cash_receiver, "lastDispensedSummary", "")
                if overpaid > 0:
                    lbl_status.config(
                        text="✅ Payment Complete! Dispensing drink...",
                        fg=CLR_LIME,
                    )
                    coins_info = f" ({change_summary})" if change_summary else ""
                    lbl_change.config(
                        text=f"💰 Change Dispensed: £{overpaid / 100:.2f} ({overpaid}p){coins_info}",
                        fg=CLR_LIME,
                    )
                else:
                    lbl_status.config(
                        text="✅ Payment Complete! (Exact Cash) Dispensing drink...",
                        fg=CLR_LIME,
                    )
                    lbl_change.config(
                        text="💰 No change required (Exact amount paid).",
                        fg=CLR_WHITE,
                    )

                self.controller.onPaymentComplete()
                for b in coin_buttons:
                    b.config(state=tk.DISABLED)
                self.root.after(1400, lambda: self._on_sale_completed_dismiss(dialog))
            else:
                lbl_status.config(
                    text=f"Awaiting cash: £{rem / 100:.2f} ({rem}p remaining)",
                    fg=CLR_LILAC,
                )

        for i, (label, val) in enumerate(denominations):
            r = i // 3
            c = i % 3
            is_rej = (val in (2000, 5000))
            btn = tk.Button(
                grid_btn,
                text=label,
                font=("Menlo", 10, "bold"),
                bg=CLR_DEEP_PURPLE if is_rej else BTN_BG,
                fg=CLR_WHITE if is_rej else BTN_FG,
                activebackground=CLR_WHITE,
                activeforeground=CLR_DEEP_PURPLE if is_rej else BTN_FG,
                relief=tk.FLAT,
                padx=6,
                pady=6,
                cursor="hand2",
                command=lambda v=val: insert_coin(v),
            )
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="nsew")
            self._attach_button_animation(btn)
            coin_buttons.append(btn)

        for c in range(3):
            grid_btn.columnconfigure(c, weight=1)

        cancel_btn = tk.Button(
            body,
            text="[ Esc ] Cancel Cash Payment",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            activebackground=BTN_BG,
            activeforeground=BTN_FG,
            relief=tk.FLAT,
            padx=12,
            pady=7,
            cursor="hand2",
            command=on_cancel,
        )
        cancel_btn.pack(side=tk.BOTTOM, fill=tk.X)
        self._attach_button_animation(cancel_btn)

        def on_cash_key(event: tk.Event):
            k = event.keysym
            ch = event.char
            if k == "Escape" or ch in ("c", "C"):
                on_cancel()
                return "break"
            key_map = {
                "1": (0, 10), "KP_1": (0, 10),
                "2": (1, 20), "KP_2": (1, 20),
                "3": (2, 50), "KP_3": (2, 50),
                "4": (3, 100), "KP_4": (3, 100),
                "5": (4, 200), "KP_5": (4, 200),
                "6": (5, 500), "KP_6": (5, 500),
                "7": (6, 1000), "KP_7": (6, 1000),
                "8": (7, 2000), "KP_8": (7, 2000),
                "9": (8, 5000), "KP_9": (8, 5000),
            }
            target = key_map.get(k) or key_map.get(ch)
            if target:
                idx, val = target
                if idx < len(coin_buttons):
                    btn = coin_buttons[idx]
                    if btn.cget("state") != tk.DISABLED:
                        btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                        orig_bg = CLR_DEEP_PURPLE if (val in (2000, 5000)) else BTN_BG
                        dialog.after(120, lambda b=btn, ob=orig_bg: self._safe_config(b, bg=ob, relief=tk.FLAT))
                insert_coin(val)
                return "break"

        dialog.bind("<Key>", on_cash_key)
        cancel_btn.bind("<Key>", on_cash_key)
        cancel_btn.focus_set()

    def _on_choose_card(self) -> None:
        """Handles Card payment selection and opens QR Code payment terminal dialog."""
        if not getattr(self, "card_enabled", True):
            messagebox.showwarning(
                "Payment Unavailable",
                "Card & Digital payment is currently disabled by system administration.\n"
                "Please choose another payment method or contact support.",
            )
            return
        self._last_payment_method = "Contactless Card"
        amount_due = self.controller.amountDue
        self.controller.startPayment(self.card_reader)
        self.card_reader.readCard("DEBIT-4021")

        # Start 60-second TransactionTimer for card payment
        self.timer.start()

        gw_name_title = getattr(self, "active_gateway_name", "stripe").upper()
        dialog = tk.Toplevel(self.root)
        self._active_modal = dialog
        dialog.title(f"Scan QR Code to Pay ({gw_name_title})")
        dw, dh = 560, 690
        dialog.geometry(f"{dw}x{dh}")
        dialog.minsize(540, 670)
        dialog.resizable(False, False)
        dialog.configure(bg=BG_APP)
        dialog.transient(self.root)
        dialog.grab_set()

        # Checkout state tracking
        checkout_state = {
            "session_id": None,
            "session_url": None,
            "poll_id": None,
            "timer_id": None,
            "completed": False,
            "is_connecting": False,
            "qr_photo": None,
        }

        def cleanup_dialog():
            if checkout_state["poll_id"]:
                try:
                    dialog.after_cancel(checkout_state["poll_id"])
                except Exception:
                    pass
                checkout_state["poll_id"] = None
            if checkout_state.get("timer_id"):
                try:
                    dialog.after_cancel(checkout_state["timer_id"])
                except Exception:
                    pass
                checkout_state["timer_id"] = None

        def on_cancel():
            checkout_state["completed"] = True
            cleanup_dialog()
            self.timer.stop()

            # Expire Stripe Checkout Session asynchronously so it cannot be used
            sid = checkout_state.get("session_id")
            if sid:
                threading.Thread(
                    target=lambda s=sid: self.stripe_bank.expireCheckoutSession(s),
                    daemon=True,
                ).start()

            self._on_cancel_card_dialog(dialog)

        dialog.protocol("WM_DELETE_WINDOW", on_cancel)

        # Center on parent safely
        dialog.update_idletasks()
        x = max(20, self.root.winfo_x() + max(0, (self.root.winfo_width() - dw) // 2))
        y = max(20, self.root.winfo_y() + max(0, (self.root.winfo_height() - dh) // 2))
        dialog.geometry(f"+{x}+{y}")

        top_bar = tk.Frame(dialog, bg=BG_APP, padx=16, pady=10)
        top_bar.pack(fill=tk.X)
        tk.Label(
            top_bar,
            text="📱 STRIPE QR PAYMENT",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_APP,
        ).pack(side=tk.LEFT)

        initial_timeout = getattr(self, "session_timeout_seconds", 60)
        card_timer_badge = tk.Label(
            top_bar,
            text=f"⏱️ {initial_timeout}s",
            font=("Menlo", 12, "bold"),
            fg=CLR_WHITE,
            bg=BG_CARD,
            padx=8,
            pady=3,
        )
        card_timer_badge.pack(side=tk.RIGHT)

        def tick_card_timer():
            if not dialog.winfo_exists() or checkout_state["completed"]:
                return
            if self.timer.hasExpired():
                to_sec = getattr(self, "session_timeout_seconds", 60)
                print(f"[Card Payment] {to_sec}s TransactionTimer expired without payment. Cancelling order.")
                checkout_state["completed"] = True
                cleanup_dialog()
                self.timer.stop()

                # Expire Stripe Checkout Session on Stripe's server in background
                sid = checkout_state.get("session_id")
                if sid:
                    threading.Thread(
                        target=lambda s=sid: self.stripe_bank.expireCheckoutSession(s),
                        daemon=True,
                    ).start()

                self.controller.onTimeout()
                self._on_timeout_card_dialog(dialog)
                return

            rem_sec = self.timer.getRemainingTime()
            if card_timer_badge.winfo_exists():
                if rem_sec <= 10:
                    card_timer_badge.config(text=f"⏱️ {rem_sec}s", fg="#FF4444")
                elif rem_sec <= 20:
                    card_timer_badge.config(text=f"⏱️ {rem_sec}s", fg=CLR_LILAC)
                else:
                    card_timer_badge.config(text=f"⏱️ {rem_sec}s", fg=CLR_WHITE)
            checkout_state["timer_id"] = dialog.after(1000, tick_card_timer)

        checkout_state["timer_id"] = dialog.after(1000, tick_card_timer)

        body = tk.Frame(dialog, bg=BG_MIDDLE, padx=14, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        screen = tk.Frame(body, bg=BG_SCREEN, padx=14, pady=8, highlightthickness=2, highlightbackground=CLR_LIME)
        screen.pack(fill=tk.X, pady=(0, 8))

        tk.Label(
            screen,
            text=f"Total Charge: £{amount_due / 100:.2f} ({amount_due}p)",
            font=("Helvetica", 14, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(anchor="w")

        status_lbl = tk.Label(
            screen,
            text="⏳ Generating Stripe QR Code...",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        status_lbl.pack(anchor="w", pady=(4, 0))

        # Pack Cancel button at bottom FIRST to guarantee it is never squeezed
        cancel_btn = tk.Button(
            body,
            text="[ Esc ] Cancel Transaction",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            activebackground=BTN_BG,
            activeforeground=BTN_FG,
            relief=tk.FLAT,
            padx=12,
            pady=9,
            cursor="hand2",
            command=on_cancel,
        )
        cancel_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        self._attach_button_animation(cancel_btn)

        action_box = tk.Frame(body, bg=BG_CARD, padx=12, pady=10)
        action_box.pack(fill=tk.BOTH, expand=True)

        guide_lbl = tk.Label(
            action_box,
            text="📱 Point phone camera at the QR code to open Stripe payment.",
            font=("Helvetica", 11),
            fg=CLR_WHITE,
            bg=BG_CARD,
            wraplength=480,
            justify="center",
        )
        guide_lbl.pack(pady=(0, 6))

        # QR Code Display Frame (White background container)
        qr_container = tk.Frame(
            action_box,
            bg=CLR_WHITE,
            padx=10,
            pady=10,
            highlightthickness=2,
            highlightbackground=CLR_LIME,
        )
        qr_container.pack(pady=(0, 6))

        qr_img_lbl = tk.Label(
            qr_container,
            text="⏳\nGenerating Stripe QR Code...",
            font=("Helvetica", 13, "bold"),
            fg=BG_APP,
            bg=CLR_WHITE,
            padx=20,
            pady=40,
        )
        qr_img_lbl.pack()

        def simulate_card_payment():
            if checkout_state["completed"]:
                return
            checkout_state["completed"] = True
            cleanup_dialog()
            self.timer.stop()
            self.controller.onPaymentComplete()
            self._on_sale_completed_dismiss(dialog)

        retry_btn = tk.Button(
            action_box,
            text="[ 1 ] 🔄 Retry Connecting to Stripe (Enter)",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            pady=8,
            cursor="hand2",
            command=lambda: start_checkout_connection(),
        )
        self._attach_button_animation(retry_btn)

        simulate_btn = tk.Button(
            action_box,
            text="[ 1 ] 💳 Simulate Card Payment (1 / Enter)",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            pady=8,
            cursor="hand2",
            command=simulate_card_payment,
        )
        simulate_btn.pack(fill=tk.X, pady=(6, 0))
        self._attach_button_animation(simulate_btn)

        def poll_checkout_status():
            if not dialog.winfo_exists() or checkout_state["completed"]:
                return

            sid = checkout_state["session_id"]
            if not sid:
                return

            def check_worker():
                info = self.stripe_bank.checkCheckoutSessionStatus(sid)

                def on_polled():
                    if not dialog.winfo_exists() or checkout_state["completed"]:
                        return

                    if info:
                        pstatus = info.get("payment_status")
                        sstatus = info.get("status")

                        if pstatus == "paid":
                            checkout_state["completed"] = True
                            cleanup_dialog()
                            self.timer.stop()
                            self.controller.onPaymentComplete()
                            self._on_sale_completed_dismiss(dialog)
                            return

                        elif sstatus == "expired":
                            checkout_state["completed"] = True
                            cleanup_dialog()
                            self.timer.stop()
                            status_lbl.config(text="❌ Stripe Checkout Expired. Transaction cancelled.", fg=CLR_LILAC)
                            self.controller.onPaymentFailed("expired")
                            dialog.after(2000, on_cancel)
                            return

                    if dialog.winfo_exists() and not checkout_state["completed"]:
                        checkout_state["poll_id"] = dialog.after(1500, poll_checkout_status)

                dialog.after(0, on_polled)

            threading.Thread(target=check_worker, daemon=True).start()

        def start_checkout_connection():
            if checkout_state["is_connecting"] or checkout_state["completed"]:
                return
            checkout_state["is_connecting"] = True
            if dialog.winfo_exists():
                retry_btn.pack_forget()
                status_lbl.config(text="⏳ Generating Stripe QR Code...", fg=CLR_LIME)
                guide_lbl.config(text="Contacting Stripe server to generate secure QR checkout session...")
                qr_img_lbl.config(
                    image="",
                    text="⏳\nGenerating Stripe QR Code...",
                    font=("Helvetica", 13, "bold"),
                    fg=BG_APP,
                    bg=CLR_WHITE,
                    width=0,
                    height=0,
                    padx=20,
                    pady=40,
                )

            def worker():
                if isinstance(self.selected_product, dict):
                    drink_name = self.selected_product.get("name", "Beverage")
                    slot_num = self.selected_product.get("slot_num", "")
                elif self.selected_product is not None:
                    drink_name = getattr(self.selected_product, "name", "Beverage")
                    slot_num = getattr(self.selected_product, "drink_id", "")
                else:
                    drink_name = "Beverage"
                    slot_num = ""
                session = self.stripe_bank.createCheckoutSession(
                    amount=amount_due,
                    drink_name=drink_name,
                    slot_num=slot_num,
                )
                qr_pil = None
                if session and session.get("url"):
                    qr_pil = generate_stripe_qr_image(session.get("url"), size=300)

                def on_done():
                    checkout_state["is_connecting"] = False
                    if not dialog.winfo_exists() or checkout_state["completed"]:
                        return

                    if session and session.get("url"):
                        checkout_state["session_id"] = session.get("id")
                        checkout_state["session_url"] = session.get("url")
                        if qr_pil is not None and HAS_PIL and ImageTk is not None:
                            try:
                                photo = ImageTk.PhotoImage(qr_pil)
                                checkout_state["qr_photo"] = photo
                                qr_img_lbl.config(
                                    image=photo,
                                    text="",
                                    width=0,
                                    height=0,
                                    padx=0,
                                    pady=0,
                                )
                            except Exception as e:
                                print(f"[QR] Failed to render photo: {e}")
                        retry_btn.pack_forget()
                        status_lbl.config(text="📱 Scan QR with phone • Waiting for confirmation...", fg=CLR_LIME)
                        guide_lbl.config(text="Point phone camera at QR code to open Stripe. Result updates here automatically.")
                        simulate_btn.config(text="[ 1 ] 💳 Simulate Card Payment (1 / Enter)", state=tk.NORMAL)
                        simulate_btn.pack(fill=tk.X, pady=(4, 0))
                        checkout_state["poll_id"] = dialog.after(1500, poll_checkout_status)
                    else:
                        status_lbl.config(text="⚠️ Could not connect to Stripe (Offline/Network)", fg=CLR_LILAC)
                        guide_lbl.config(
                            text="Unable to reach Stripe server.\n"
                                 "Click Retry [ 1 ] or use Simulate Test Card [ 2 ] below."
                        )
                        qr_img_lbl.config(
                            image="",
                            text="⚠️\nOffline / Error\nCould not reach Stripe",
                            font=("Helvetica", 12, "bold"),
                            fg=CLR_LILAC,
                            bg=CLR_WHITE,
                            width=0,
                            height=0,
                            padx=15,
                            pady=30,
                        )
                        retry_btn.pack(fill=tk.X, pady=(4, 4))
                        simulate_btn.config(text="[ 2 ] 💳 Simulate Card Payment (Keypad 2)", state=tk.NORMAL)
                        simulate_btn.pack(fill=tk.X, pady=(0, 0))

                try:
                    if dialog.winfo_exists() and not checkout_state["completed"]:
                        dialog.after(0, on_done)
                except Exception:
                    pass

            threading.Thread(target=worker, daemon=True).start()

        def on_card_key(event: tk.Event):
            k = event.keysym
            ch = event.char
            if k in ("Escape", "KP_4") or ch in ("c", "C", "4"):
                on_cancel()
            elif k in ("Return", "KP_Enter", "KP_1", "1") or ch == "1":
                if retry_btn.winfo_ismapped() and retry_btn.cget("state") != tk.DISABLED:
                    retry_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    dialog.after(120, lambda: self._safe_config(retry_btn, bg=BTN_BG, relief=tk.FLAT))
                    start_checkout_connection()
                elif simulate_btn.cget("state") != tk.DISABLED:
                    simulate_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    dialog.after(120, lambda: self._safe_config(simulate_btn, bg=BTN_BG, relief=tk.FLAT))
                    simulate_card_payment()
            elif k in ("KP_2", "2") or ch == "2":
                if simulate_btn.cget("state") != tk.DISABLED:
                    simulate_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    dialog.after(120, lambda: self._safe_config(simulate_btn, bg=BTN_BG, relief=tk.FLAT))
                    simulate_card_payment()

        dialog.bind("<Key>", on_card_key)
        simulate_btn.focus_set()
        dialog.after(100, start_checkout_connection)

    def _on_cancel_cash_dialog(self, dialog: tk.Toplevel) -> None:
        """Handles cancellation of active cash payment — navigate to cancelled/refund page."""
        refunded = getattr(self.cash_receiver, "_total", 0)
        self.last_cancelled_order = {"refunded": refunded, "method": "cash", "reason": "user_cancelled"}
        self.controller.cancel()
        if hasattr(self, "cash_receiver") and getattr(self.cash_receiver, "_total", 0) > 0:
            self.cash_receiver.cancel()
        try:
            if dialog.winfo_exists():
                dialog.grab_release()
                dialog.destroy()
        except Exception:
            pass
        self._active_modal = None
        self.root.focus_force()
        self.root.focus_set()
        self.root.after(50, lambda: (self.root.focus_force(), self.root.focus_set()))
        self.transition_to_page("cancelled", direction="left")

    def _on_timeout_cash_dialog(self, dialog: tk.Toplevel) -> None:
        """Handles timeout of active cash payment — refund all inserted coins and navigate to cancelled page."""
        # Capture inserted cash BEFORE controller aborts sale and clears receiver state
        refunded = getattr(self.cash_receiver, "_total", 0)
        items = list(getattr(self.cash_receiver, "_inserted_items", []))
        self.last_cancelled_order = {
            "refunded": refunded,
            "method": "cash",
            "reason": "timeout",
            "items": items,
        }
        self.controller.onTimeout()
        if hasattr(self, "cash_receiver") and getattr(self.cash_receiver, "_total", 0) > 0:
            self.cash_receiver.cancel()
        try:
            if dialog.winfo_exists():
                dialog.grab_release()
                dialog.destroy()
        except Exception:
            pass
        self._active_modal = None
        self.root.focus_force()
        self.root.focus_set()
        self.root.after(50, lambda: (self.root.focus_force(), self.root.focus_set()))
        self.transition_to_page("cancelled", direction="left")

    def _on_cancel_card_dialog(self, dialog: tk.Toplevel) -> None:
        """Handles user cancellation of active card payment — navigate to cancelled page."""
        self.last_cancelled_order = {"refunded": 0, "method": "card", "reason": "user_cancelled"}
        self.controller.cancel()
        try:
            if dialog.winfo_exists():
                dialog.grab_release()
                dialog.destroy()
        except Exception:
            pass
        self._active_modal = None
        self.root.focus_force()
        self.root.focus_set()
        self.root.after(50, lambda: (self.root.focus_force(), self.root.focus_set()))
        self.transition_to_page("cancelled", direction="left")

    def _on_timeout_card_dialog(self, dialog: tk.Toplevel) -> None:
        """Handles timeout of active card payment — navigate to cancelled page with timeout notice."""
        self.last_cancelled_order = {"refunded": 0, "method": "card", "reason": "timeout"}
        try:
            if dialog.winfo_exists():
                dialog.grab_release()
                dialog.destroy()
        except Exception:
            pass
        self._active_modal = None
        self.root.focus_force()
        self.root.focus_set()
        self.root.after(50, lambda: (self.root.focus_force(), self.root.focus_set()))
        self.transition_to_page("cancelled", direction="left")

    def _show_dispense_banner(self, drink_name: str) -> None:
        """Shows non-blocking dispense celebration and guidance for the next order."""
        self._dispense_banner_active = True
        if hasattr(self, "preview_name_lbl") and self.preview_name_lbl.winfo_exists():
            self.preview_name_lbl.config(
                text=f"🎉 {drink_name} Dispensed!",
                fg=CLR_LIME,
            )
        if hasattr(self, "preview_price_lbl") and self.preview_price_lbl.winfo_exists():
            self.preview_price_lbl.config(
                text="Ready for Next Order (Type Slot)",
                fg=CLR_WHITE,
            )
        if hasattr(self, "footer_tip_lbl") and self.footer_tip_lbl.winfo_exists():
            max_slot = f"{len(self.catalogue):02d}" if self.catalogue else "09"
            self.footer_tip_lbl.config(
                text=f"🎉 Enjoy your {drink_name}! Ready for next order — type slot number (01-{max_slot}) on keypad.",
                fg=CLR_LIME,
            )

        def restore_idle():
            self._dispense_banner_active = False
            try:
                # Only restore if user hasn't started typing the next order
                if self.entered_slot.get() == "--" and self.selected_product is None:
                    if hasattr(self, "preview_name_lbl") and self.preview_name_lbl.winfo_exists():
                        self.preview_name_lbl.config(text="No Drink Selected", fg=CLR_WHITE)
                    if hasattr(self, "preview_price_lbl") and self.preview_price_lbl.winfo_exists():
                        self.preview_price_lbl.config(text="Enter slot number to order", fg=CLR_LILAC)
                if hasattr(self, "footer_tip_lbl") and self.footer_tip_lbl.winfo_exists():
                    self.footer_tip_lbl.config(
                        text="💡 Tip: Check the slot number on any drink box and type it on your keyboard to order.",
                        fg=CLR_WHITE,
                    )
            except Exception:
                pass

        self._dispense_restore_after_id = self.root.after(5000, restore_idle)

    def _on_sale_completed_dismiss(self, dialog: tk.Toplevel) -> None:
        """Dismisses payment modal automatically, records order info, and slides to order success page."""
        try:
            if dialog.winfo_exists():
                dialog.grab_release()
                dialog.destroy()
        except Exception:
            pass

        self._active_modal = None
        prod = self.selected_product
        overpaid = 0
        change_summary = ""
        if hasattr(self, "cash_receiver") and getattr(self, "_last_payment_method", "") == "Cash Receiver":
            overpaid = max(0, getattr(self.cash_receiver, "_total", 0) - getattr(self.cash_receiver, "_amount_due", 0))
            change_summary = getattr(self.cash_receiver, "lastDispensedSummary", "")

        self.last_completed_order = {
            "name": prod["name"] if prod else "Your Drink",
            "slot_num": prod.get("slot_num", "--") if prod else "--",
            "price": self.controller.amountDue if hasattr(self.controller, "amountDue") and self.controller.amountDue else (prod["price"] if prod else 0),
            "original_price": prod["price"] if prod else 0,
            "loyalty_applied": getattr(self.controller, "loyaltyApplied", False),
            "method": getattr(self, "_last_payment_method", "Payment Terminal"),
            "image": prod.get("image", "") if prod else "",
            "icon_type": prod.get("icon_type", "water") if prod else "water",
            "change_amount": overpaid,
            "change_summary": change_summary,
        }

        # Slide smoothly to the success page by moving current page all the way to the left
        self.transition_to_page("success", direction="left")

    # =======================================================================
    # Page 3: Order Success & Dispense Confirmation Screen
    # =======================================================================
    def _build_page3_success(self) -> None:
        """Page 3: Dispense confirmation with 10-second auto-return countdown."""
        page = tk.Frame(self.container, bg=BG_APP)
        self.pages["success"] = page

        # 1. Header (Color #3A0C51)
        self._build_success_header(page)

        # 2. Middle Area (Color #D883FF)
        middle_area = tk.Frame(page, bg=BG_MIDDLE)
        middle_area.pack(fill=tk.BOTH, expand=True)

        center_wrap = tk.Frame(middle_area, bg=BG_MIDDLE)
        center_wrap.pack(expand=True, fill=tk.BOTH, padx=20, pady=8)

        # Center card box (Border: #BAEF2D)
        card = tk.Frame(
            center_wrap,
            bg=BG_CARD,
            padx=28,
            pady=20,
            highlightthickness=3,
            highlightbackground=CLR_LIME,
        )
        card.pack(expand=True, fill=tk.Y, pady=4)

        # Large Green Checkmark
        tk.Label(
            card,
            text="\u2714",
            font=("Helvetica", 90, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="center", pady=(0, 6))

        # Payment Successful title
        tk.Label(
            card,
            text="Payment Successful",
            font=("Helvetica", 22, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="center", pady=(0, 6))

        # Collection instruction
        tk.Label(
            card,
            text="Please collect your item from the slot below.",
            font=("Helvetica", 14),
            fg=CLR_WHITE,
            bg=BG_CARD,
        ).pack(anchor="center", pady=(0, 14))

        # Countdown label (hidden — logic still runs for auto-return)
        self.success_countdown_lbl = tk.Label(
            card,
            text="",
            font=("Menlo", 1),
            fg=BG_CARD,
            bg=BG_CARD,
        )
        self.success_countdown_lbl.pack_forget()

        # Return Button
        self.return_home_btn = tk.Button(
            card,
            text="[ Enter ] Return to Catalogue (10s)",
            font=("Helvetica", 13, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            padx=16,
            pady=10,
            cursor="hand2",
            command=self._return_to_catalogue,
        )
        self.return_home_btn.pack(anchor="center", fill=tk.X, pady=(2, 0))
        self._attach_button_animation(self.return_home_btn)

        # 3. Footer (Color #3A0C51)
        self._build_success_footer(page)

    def _build_success_header(self, parent: tk.Frame) -> None:
        """Top banner for Page 3 (Background: #3A0C51)."""
        header = tk.Frame(parent, bg=BG_APP, height=60, padx=20)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand_frame = tk.Frame(header, bg=BG_APP)
        brand_frame.pack(side=tk.LEFT, fill=tk.Y)

        logo_path = os.path.join(os.path.dirname(__file__), "assets", "edge_hill_logo.png")
        if os.path.exists(logo_path) and hasattr(self, "header_logo"):
            logo_lbl = tk.Label(
                brand_frame,
                image=self.header_logo,
                bg=BG_APP,
            )
            logo_lbl.pack(side=tk.LEFT, pady=8)
        else:
            tk.Label(
                brand_frame,
                text="Edge Hill University",
                font=("Georgia", 15, "bold"),
                fg=CLR_WHITE,
                bg=BG_APP,
            ).pack(side=tk.LEFT, pady=14)

        tk.Label(
            header,
            text="• Campus Vending Machine",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LILAC,
            bg=BG_APP,
        ).pack(side=tk.LEFT, padx=12, pady=18)

        # Step Indicator Badge
        step_badge = tk.Label(
            header,
            text="ORDER SUCCESSFUL",
            font=("Helvetica", 9, "bold"),
            fg=BTN_FG,
            bg=BTN_BG,
            padx=10,
            pady=3,
        )
        step_badge.pack(side=tk.RIGHT, pady=14)

    def _build_success_footer(self, parent: tk.Frame) -> None:
        """Bottom status bar on Page 3 (Background: #3A0C51)."""
        footer = tk.Frame(parent, bg=BG_APP, height=40, padx=20)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        # Current Time label
        time_lbl = tk.Label(
            footer,
            text=time.strftime("%H:%M:%S"),
            font=("Menlo", 10, "bold"),
            fg=CLR_LIME,
            bg=BG_APP,
        )
        time_lbl.pack(side=tk.RIGHT, pady=10)

    def _refresh_success_page(self) -> None:
        """Refreshes the success page (countdown label is handled by _start_success_countdown)."""
        # No dynamic widgets to refresh on this simplified page.
        # Countdown and return button are updated by _start_success_countdown.
        pass

    def _start_success_countdown(self) -> None:
        """Starts a 10-second countdown before automatically sliding back to catalogue."""
        if getattr(self, "_success_countdown_after_id", None):
            try:
                self.root.after_cancel(self._success_countdown_after_id)
            except Exception:
                pass
            self._success_countdown_after_id = None

        self._success_seconds_left = 10

        if hasattr(self, "success_countdown_lbl") and self.success_countdown_lbl.winfo_exists():
            self.success_countdown_lbl.config(text="⏱️ Auto-returning to catalogue in 10s...")
        if hasattr(self, "return_home_btn") and self.return_home_btn.winfo_exists():
            self.return_home_btn.config(text="[ Enter ] Return to Catalogue (10s)")

        def tick():
            if getattr(self, "current_page", None) != "success":
                return
            self._success_seconds_left -= 1
            if self._success_seconds_left <= 0:
                self._return_to_catalogue()
            else:
                sec = self._success_seconds_left
                if hasattr(self, "success_countdown_lbl") and self.success_countdown_lbl.winfo_exists():
                    self.success_countdown_lbl.config(text=f"⏱️ Auto-returning to catalogue in {sec}s...")
                if hasattr(self, "return_home_btn") and self.return_home_btn.winfo_exists():
                    self.return_home_btn.config(text=f"[ Enter ] Return to Catalogue ({sec}s)")
                self._success_countdown_after_id = self.root.after(1000, tick)

        self._success_countdown_after_id = self.root.after(1000, tick)

    def _return_to_catalogue(self) -> None:
        """Cancels countdown and smoothly slides back to the main catalogue page."""
        if getattr(self, "_success_countdown_after_id", None):
            try:
                self.root.after_cancel(self._success_countdown_after_id)
            except Exception:
                pass
            self._success_countdown_after_id = None

        drink_name = getattr(self, "last_completed_order", {}).get("name", "Your Drink")

        # Reset selection state
        self.entered_slot.set("--")
        self.selected_product = None
        self.scanned_member = None
        if hasattr(self, "loyalty_scanner"):
            self.loyalty_scanner._last_scanned = None
        self._highlight_active_card(None)
        self._update_preview(None)

        # Non-blocking dispense confirmation banner on catalogue preview & footer
        self._show_dispense_banner(drink_name)

        # Force focus back to root
        self.root.focus_force()
        self.root.focus_set()
        self.root.after(50, lambda: (self.root.focus_force(), self.root.focus_set()))

        # Slide back to catalogue
        self.transition_to_page("catalogue", direction="right")

        # Re-assert keyboard focus after slide finishes
        self.root.after(300, lambda: (self.root.focus_force(), self.root.focus_set()))

    # =======================================================================
    # Page 4: Order Cancelled & Refund Confirmation Screen
    # =======================================================================
    def _build_page_cancelled(self) -> None:
        """Page 4: Shown when user cancels a cash payment mid-insertion."""
        page = tk.Frame(self.container, bg=BG_APP)
        self.pages["cancelled"] = page

        # 1. Header (same style as Page 3)
        self._build_cancelled_header(page)

        # 2. Middle Area (Color #D883FF)
        middle_area = tk.Frame(page, bg=BG_MIDDLE)
        middle_area.pack(fill=tk.BOTH, expand=True)

        center_wrap = tk.Frame(middle_area, bg=BG_MIDDLE)
        center_wrap.pack(expand=True, fill=tk.BOTH, padx=20, pady=8)

        # Center card box (Border: red)
        card = tk.Frame(
            center_wrap,
            bg=BG_CARD,
            padx=28,
            pady=20,
            highlightthickness=3,
            highlightbackground="#FF4444",
        )
        card.pack(expand=True, fill=tk.Y, pady=4)

        # Large Red Cross
        tk.Label(
            card,
            text="\u2716",
            font=("Helvetica", 90, "bold"),
            fg="#FF4444",
            bg=BG_CARD,
        ).pack(anchor="center", pady=(0, 6))

        # Order Cancelled title
        tk.Label(
            card,
            text="Order Cancelled",
            font=("Helvetica", 22, "bold"),
            fg="#FF4444",
            bg=BG_CARD,
        ).pack(anchor="center", pady=(0, 6))

        # Refund info (dynamic)
        self.cancelled_refund_lbl = tk.Label(
            card,
            text="Refund: \u00a30.00",
            font=("Helvetica", 16, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        )
        self.cancelled_refund_lbl.pack(anchor="center", pady=(0, 4))

        # Sub-instruction (dynamic)
        self.cancelled_sub_lbl = tk.Label(
            card,
            text="Please collect your refund from the coin return slot.",
            font=("Helvetica", 13),
            fg=CLR_WHITE,
            bg=BG_CARD,
        )
        self.cancelled_sub_lbl.pack(anchor="center", pady=(0, 14))

        # Countdown label (hidden — logic still runs for auto-return)
        self.cancelled_countdown_lbl = tk.Label(
            card,
            text="",
            font=("Menlo", 1),
            fg=BG_CARD,
            bg=BG_CARD,
        )
        self.cancelled_countdown_lbl.pack_forget()

        # Return Button
        self.cancelled_home_btn = tk.Button(
            card,
            text="[ Enter ] Return to Catalogue (10s)",
            font=("Helvetica", 13, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            padx=16,
            pady=10,
            cursor="hand2",
            command=self._return_to_catalogue_from_cancelled,
        )
        self.cancelled_home_btn.pack(anchor="center", fill=tk.X, pady=(2, 0))
        self._attach_button_animation(self.cancelled_home_btn)

        # 3. Footer (same style as Page 3)
        self._build_cancelled_footer(page)

        # Keyboard binding — Enter or Esc returns to catalogue
        page.bind("<Return>", lambda e: self._return_to_catalogue_from_cancelled())
        page.bind("<Escape>", lambda e: self._return_to_catalogue_from_cancelled())
        page.bind("<KP_Enter>", lambda e: self._return_to_catalogue_from_cancelled())

    def _build_cancelled_header(self, parent: tk.Frame) -> None:
        """Top banner for Page 4 (same layout as Page 3 header)."""
        header = tk.Frame(parent, bg=BG_APP, height=60, padx=20)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand_frame = tk.Frame(header, bg=BG_APP)
        brand_frame.pack(side=tk.LEFT, fill=tk.Y)

        logo_path = os.path.join(os.path.dirname(__file__), "assets", "edge_hill_logo.png")
        if os.path.exists(logo_path) and hasattr(self, "header_logo"):
            tk.Label(brand_frame, image=self.header_logo, bg=BG_APP).pack(side=tk.LEFT, pady=8)
        else:
            tk.Label(
                brand_frame,
                text="Edge Hill University",
                font=("Georgia", 15, "bold"),
                fg=CLR_WHITE,
                bg=BG_APP,
            ).pack(side=tk.LEFT, pady=14)

        tk.Label(
            header,
            text="• Campus Vending Machine",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LILAC,
            bg=BG_APP,
        ).pack(side=tk.LEFT, padx=12, pady=18)

        tk.Label(
            header,
            text="ORDER CANCELLED",
            font=("Helvetica", 9, "bold"),
            fg=BTN_FG,
            bg="#FF4444",
            padx=10,
            pady=3,
        ).pack(side=tk.RIGHT, pady=14)

    def _build_cancelled_footer(self, parent: tk.Frame) -> None:
        """Bottom status bar for Page 4."""
        footer = tk.Frame(parent, bg=BG_APP, height=40, padx=20)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        time_lbl = tk.Label(
            footer,
            text=time.strftime("%H:%M:%S"),
            font=("Menlo", 10, "bold"),
            fg=CLR_LIME,
            bg=BG_APP,
        )
        time_lbl.pack(side=tk.RIGHT, pady=10)

    def _refresh_cancelled_page(self) -> None:
        """Updates labels based on the payment method and reason for cancellation."""
        info = getattr(self, "last_cancelled_order", {}) or {}
        refunded = info.get("refunded", 0)
        method = info.get("method", "cash")
        reason = info.get("reason", "cancelled")

        if hasattr(self, "cancelled_refund_lbl") and self.cancelled_refund_lbl.winfo_exists():
            if method == "card":
                if reason == "timeout":
                    self.cancelled_refund_lbl.config(
                        text="Card Payment Timed Out (60s Expired)",
                        fg="#FF4444",
                    )
                else:
                    self.cancelled_refund_lbl.config(
                        text="Credit Card Payment Cancelled",
                        fg="#FF4444",
                    )
            elif refunded > 0:
                refund_txt = f"Full Refund: \u00a3{refunded / 100:.2f} ({refunded}p)"
                if reason == "timeout":
                    refund_txt += " (Timed Out)"
                self.cancelled_refund_lbl.config(
                    text=refund_txt,
                    fg=CLR_LIME,
                )
            else:
                self.cancelled_refund_lbl.config(
                    text="Cash Payment Timed Out — No money inserted."
                    if reason == "timeout"
                    else "No money inserted — no refund needed.",
                    fg=CLR_WHITE,
                )

        if hasattr(self, "cancelled_sub_lbl") and self.cancelled_sub_lbl.winfo_exists():
            if method == "card":
                if reason == "timeout":
                    self.cancelled_sub_lbl.config(
                        text="Payment session expired (60s). Order was cancelled and no charge was made."
                    )
                else:
                    self.cancelled_sub_lbl.config(
                        text="No charge has been applied to your card."
                    )
            else:
                if refunded > 0:
                    self.cancelled_sub_lbl.config(
                        text=f"Payment timed out. All \u00a3{refunded / 100:.2f} ({refunded}p) inserted has been returned to the coin slot."
                        if reason == "timeout"
                        else f"Transaction cancelled. All \u00a3{refunded / 100:.2f} ({refunded}p) inserted has been returned."
                    )
                else:
                    self.cancelled_sub_lbl.config(
                        text="Session expired without payment."
                        if reason == "timeout"
                        else "No money was inserted."
                    )

    def _start_cancelled_countdown(self) -> None:
        """Starts a 10-second countdown then auto-returns to catalogue."""
        if getattr(self, "_cancelled_countdown_after_id", None):
            try:
                self.root.after_cancel(self._cancelled_countdown_after_id)
            except Exception:
                pass
            self._cancelled_countdown_after_id = None

        if hasattr(self, "cancelled_home_btn") and self.cancelled_home_btn.winfo_exists():
            self.cancelled_home_btn.config(text="[ Enter ] Return to Catalogue (10s)")

        def tick(sec: int = 9) -> None:
            if self.current_page != "cancelled":
                return
            if sec <= 0:
                self._return_to_catalogue_from_cancelled()
                return
            if hasattr(self, "cancelled_home_btn") and self.cancelled_home_btn.winfo_exists():
                self.cancelled_home_btn.config(text=f"[ Enter ] Return to Catalogue ({sec}s)")
            self._cancelled_countdown_after_id = self.root.after(1000, lambda: tick(sec - 1))

        self._cancelled_countdown_after_id = self.root.after(1000, lambda: tick(9))

    def _cancel_cancelled_countdown(self) -> None:
        """Cancels the auto-return countdown on the cancelled page."""
        if getattr(self, "_cancelled_countdown_after_id", None):
            try:
                self.root.after_cancel(self._cancelled_countdown_after_id)
            except Exception:
                pass
            self._cancelled_countdown_after_id = None

    def _return_to_catalogue_from_cancelled(self) -> None:
        """Returns to catalogue from the cancelled/refund page."""
        self._cancel_cancelled_countdown()

        # Reset selection state
        self.entered_slot.set("--")
        self.selected_product = None
        self.scanned_member = None
        if hasattr(self, "loyalty_scanner"):
            self.loyalty_scanner._last_scanned = None
        self._highlight_active_card(None)
        self._update_preview(None)

        self.root.focus_force()
        self.root.focus_set()
        self.root.after(50, lambda: (self.root.focus_force(), self.root.focus_set()))

        self.transition_to_page("catalogue", direction="right")
        self.root.after(300, lambda: (self.root.focus_force(), self.root.focus_set()))


# ===========================================================================
# Launch Entrypoint
# ===========================================================================
def main():
    root = tk.Tk()
    app = CustomerVendingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

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
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Tuple

# Safe OpenCV (cv2) import with graceful error handling
try:
    import cv2  # type: ignore
    HAS_CV2 = True
except Exception:
    cv2 = None  # type: ignore
    HAS_CV2 = False

# Safe PIL (Pillow) support
try:
    from PIL import Image, ImageTk  # type: ignore
    HAS_PIL = True
except Exception:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore
    HAS_PIL = False

# Safe zxing-cpp for Code 128 linear barcode decoding
try:
    import zxingcpp  # type: ignore
    HAS_ZXING = True
except Exception:
    zxingcpp = None  # type: ignore
    HAS_ZXING = False

# System Model Imports
from controller import (
    VendingController,
    MachineState,
    load_products,
    save_products,
    load_members,
    DATA_DIR,
    PRODUCTS_FILE,
)
from inventory import Drink, DrinkDispenser, LoyaltyScanner, StockSensor
from payment import PaymentModule, CashReceiver, CardReader, PaymentResult, CashReceiverState
from bank import MockBankService
from logger import Logger
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

            return data
    except Exception as e:
        print(f"[customer_ui] Error reading products from {file_path}: {e}")
        return []


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
                    with Image.open(file_path) as im:
                        im_copy = im.copy()
                        max_w = max(10, width - 8)
                        max_h = max(10, height - 8)
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
            )
            for d in self.catalogue
        ]

        self.dispenser = DrinkDispenser(loaded_drinks)
        self.stock_sensor = StockSensor(self.dispenser, low_stock_level=3)

        # 3. Loyalty Programme
        loaded_accounts = load_members()
        self.loyalty_scanner = LoyaltyScanner(loaded_accounts)

        # 4. Payments
        self.cash_receiver = CashReceiver()
        self.mock_bank = MockBankService()
        self.card_reader = CardReader(self.mock_bank)
        self.payment_module = PaymentModule([self.cash_receiver, self.card_reader])

        # 5. Logger & Timer
        self.logger = Logger()
        self.timer = TransactionTimer(timeout_seconds=60)

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
                        )
                    )
            self.dispenser._slots = new_slots

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
            text="• Campus Vending Barista",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_APP,
        ).pack(side=tk.LEFT, padx=14, pady=20)

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
        top_row.pack(fill=tk.X, pady=(0, 2))

        # Prominent Product Number Badge (Button color: #BAEF2D)
        slot_badge = tk.Label(
            top_row,
            text=f"No. {prod['slot_num']}",
            font=("Menlo", 11, "bold"),
            fg=BTN_FG,
            bg=BTN_BG,
            padx=6,
            pady=1,
        )
        slot_badge.pack(side=tk.LEFT)

        # Stock indicator pill
        stock_text = f"Stock: {stock}" if in_stock else "SOLD OUT"
        stock_color = CLR_LIME if in_stock else CLR_LILAC
        stock_pill = tk.Label(
            top_row,
            text=stock_text,
            font=("Helvetica", 10, "bold"),
            fg=stock_color,
            bg=BG_CARD,
        )
        stock_pill.pack(side=tk.RIGHT)

        # Center Product Showcase Canvas (Photograph from assets/ with vector fallback)
        canvas = tk.Canvas(
            card,
            width=140,
            height=76,
            bg=CLR_WHITE,
            highlightthickness=1,
            highlightbackground=CLR_LILAC,
        )
        canvas.pack(pady=2)
        render_product_artwork(
            canvas=canvas,
            prod=prod,
            width=140,
            height=76,
            photo_cache=self._product_images,
            default_bg=CLR_WHITE,
            fallback_bg=BG_CARD,
        )

        # Product Name
        name_lbl = tk.Label(
            card,
            text=prod["name"],
            font=("Helvetica", 12, "bold"),
            fg=CLR_WHITE if in_stock else CLR_LILAC,
            bg=BG_CARD,
            anchor="center",
        )
        name_lbl.pack(fill=tk.X, pady=(2, 0))

        # Price Display
        price_pounds = f"£{prod['price'] / 100:.2f}"
        price_lbl = tk.Label(
            card,
            text=f"{price_pounds}  ({prod['price']}p)",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LIME if in_stock else CLR_LILAC,
            bg=BG_CARD,
        )
        price_lbl.pack(pady=(0, 2))

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
            text="🗑️ Clear Selection (Esc / C)",
            font=("Helvetica", 10, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            activebackground=CLR_WHITE,
            activeforeground=BTN_FG,
            relief=tk.FLAT,
            bd=0,
            pady=5,
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
                if hasattr(self, "cash_btn") and self.cash_btn.winfo_exists():
                    self.cash_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    self.root.after(120, lambda: self._safe_config(self.cash_btn, bg=BTN_BG, relief=tk.FLAT))
                self.root.after(130, self._on_choose_cash)
                return
            elif char == "3" or key in ("KP_3", "3"):
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

        # Keypad Control on Page 1 (Catalogue Page)
        # Numbers 0-9 (standard keys or numeric keypad)
        if char in "0123456789" and len(char) == 1:
            self._handle_digit_input(char)
        elif key in ("KP_0", "KP_1", "KP_2", "KP_3", "KP_4", "KP_5", "KP_6", "KP_7", "KP_8", "KP_9"):
            digit = key.replace("KP_", "")
            self._handle_digit_input(digit)
        elif key in ("BackSpace", "Delete"):
            self._handle_backspace()
        elif key in ("Escape", "c", "C"):
            self._handle_clear()
        elif key in ("Return", "KP_Enter"):
            # Animate confirm button on Enter keypress
            if hasattr(self, "confirm_btn"):
                self.confirm_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                self.root.after(120, lambda: self._safe_config(self.confirm_btn, bg=BTN_BG, relief=tk.FLAT))
            self.root.after(130, self._on_confirm_selection)

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
        """Clears slot selection back to default on Esc / C with button animation."""
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

        # Trigger smooth slide to left transition to Page 2 (old page slides left until out of screen)
        self.transition_to_page("payment", direction="left")

    def _build_footer(self, parent: tk.Frame) -> None:
        """Bottom status and instruction bar (Background: #3A0C51)."""
        footer = tk.Frame(parent, bg=BG_APP, height=40, padx=20)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        footer.pack_propagate(False)

        self.footer_tip_lbl = tk.Label(
            footer,
            text="💡 Tip: Check the slot number on any drink box and type it on your keyboard to order.",
            font=("Helvetica", 10),
            fg=CLR_WHITE,
            bg=BG_APP,
        )
        self.footer_tip_lbl.pack(side=tk.LEFT, pady=10)

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

        # Left Column: Order Summary Card (Width: ~340px)
        left_summary = tk.Frame(content_split, bg=BG_CARD, width=340, padx=16, pady=12)
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
                font=("Georgia", 15, "bold"),
                fg=CLR_WHITE,
                bg=BG_APP,
            ).pack(side=tk.LEFT, pady=14)

        tk.Label(
            header,
            text="Official Smart Drink Dispenser",
            font=("Helvetica", 10),
            fg=CLR_LILAC,
            bg=BG_APP,
        ).pack(side=tk.LEFT, padx=12, pady=18)

        # Step Indicator Badge
        step_badge = tk.Label(
            header,
            text="STEP 2: PAYMENT & LOYALTY",
            font=("Helvetica", 9, "bold"),
            fg=BTN_FG,
            bg=BTN_BG,
            padx=10,
            pady=3,
        )
        step_badge.pack(side=tk.RIGHT, pady=14)

    def _build_order_summary_panel(self, parent: tk.Frame) -> None:
        """Left panel on Page 2 detailing the selected beverage, discount, and total due."""
        tk.Label(
            parent,
            text="🛒 ORDER SUMMARY",
            font=("Helvetica", 14, "bold"),
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
            font=("Helvetica", 14, "bold"),
            fg=CLR_WHITE,
            bg=BG_CARD,
        )
        self.summary_name_lbl.pack(fill=tk.X, pady=(1, 1))

        # Drink Description
        self.summary_desc_lbl = tk.Label(
            parent,
            text="",
            font=("Helvetica", 10),
            fg=CLR_LILAC,
            bg=BG_CARD,
            wraplength=310,
            justify=tk.CENTER,
        )
        self.summary_desc_lbl.pack(fill=tk.X, pady=(0, 4))

        # Thin divider
        tk.Frame(parent, bg=CLR_LILAC, height=1).pack(fill=tk.X, pady=(2, 6))

        # Price Breakdown
        prices_frame = tk.Frame(parent, bg=BG_CARD)
        prices_frame.pack(fill=tk.X, pady=(0, 4))

        row1 = tk.Frame(prices_frame, bg=BG_CARD)
        row1.pack(fill=tk.X, pady=1)
        tk.Label(row1, text="Drink Regular Price:", font=("Helvetica", 10), fg=CLR_WHITE, bg=BG_CARD).pack(side=tk.LEFT)
        self.summary_base_price_lbl = tk.Label(row1, text="£0.00", font=("Menlo", 11, "bold"), fg=CLR_WHITE, bg=BG_CARD)
        self.summary_base_price_lbl.pack(side=tk.RIGHT)

        row2 = tk.Frame(prices_frame, bg=BG_CARD)
        row2.pack(fill=tk.X, pady=1)
        tk.Label(row2, text="Membership Discount:", font=("Helvetica", 10), fg=CLR_WHITE, bg=BG_CARD).pack(side=tk.LEFT)
        self.summary_discount_lbl = tk.Label(row2, text="£0.00", font=("Menlo", 11, "bold"), fg=CLR_LILAC, bg=BG_CARD)
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
            font=("Helvetica", 9, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(anchor="w")

        self.summary_total_lbl = tk.Label(
            screen_frame,
            text="£0.00",
            font=("Menlo", 22, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        self.summary_total_lbl.pack(anchor="e", pady=(2, 0))

        # Back to catalogue button
        self.back_btn = tk.Button(
            parent,
            text="[ 4 ] ← Change Drink / Back (Esc)",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            padx=12,
            pady=7,
            command=self._on_cancel_payment,
        )
        self.back_btn.pack(side=tk.BOTTOM, fill=tk.X)
        self._attach_button_animation(self.back_btn)

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
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(side=tk.LEFT)

        discount_badge = tk.Label(
            hdr_row,
            text="10% OFF DISCOUNT",
            font=("Helvetica", 10, "bold"),
            fg=BTN_FG,
            bg=BTN_BG,
            padx=8,
            pady=3,
        )
        discount_badge.pack(side=tk.RIGHT)

        tk.Label(
            loyalty_card,
            text="Scan your Edge Hill University membership or student card to apply an instant 10% discount.",
            font=("Helvetica", 11),
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
            font=("Helvetica", 11, "bold"),
            fg=CLR_LILAC,
            bg=BG_SCREEN,
        )
        self.loyalty_status_lbl.pack(anchor="w")

        # Scan button
        self.scan_loyalty_btn = tk.Button(
            loyalty_card,
            text="[ 1 ] 📷 Scan Member Card",
            font=("Helvetica", 12, "bold"),
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
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(side=tk.LEFT)

        tk.Label(
            pay_card,
            text="Choose your preferred payment method below to complete your purchase:",
            font=("Helvetica", 11),
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
            font=("Helvetica", 14, "bold"),
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
            font=("Helvetica", 10),
            fg=CLR_LILAC,
            bg=BG_CARD,
            justify=tk.CENTER,
        ).pack(pady=(4, 0))

        # 2. Card Button Box (Column 1)
        card_box = tk.Frame(btn_container, bg=BG_CARD, padx=5)
        card_box.grid(row=0, column=1, sticky="nsew")

        self.card_btn = tk.Button(
            card_box,
            text="[ 3 ] 💳 PAY WITH CARD",
            font=("Helvetica", 14, "bold"),
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
            text="Contactless, Chip & PIN, Apple Pay\n& Google Wallet supported",
            font=("Helvetica", 10),
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
            text="🔒 256-Bit Bank Encrypted Payment Processing • Fast & Contactless",
            font=("Helvetica", 11),
            fg=CLR_LILAC,
            bg=BG_APP,
        ).pack(side=tk.LEFT, pady=10)

        tk.Label(
            footer,
            text="Press keypad 1, 2, 3 or Esc / 4 to control payment terminal",
            font=("Helvetica", 11),
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

        # 4. Check Loyalty Discount
        if self.controller.loyaltyApplied:
            amount_due = self.controller.amountDue
            discount_pence = base_pence - amount_due
            discount_text = f"✅ -10% (-£{discount_pence / 100:.2f})"
            discount_color = CLR_LIME
            status_text = "🎉 Verified Member • 10% Discount Active"
            status_color = CLR_LIME
        else:
            amount_due = base_pence
            discount_text = "£0.00 (No Card Scanned)"
            discount_color = CLR_LILAC
            status_text = "💳 Status: No Membership Card Scanned"
            status_color = CLR_LILAC

        if hasattr(self, "summary_discount_lbl"):
            self.summary_discount_lbl.config(text=discount_text, fg=discount_color)

        if hasattr(self, "summary_total_lbl"):
            self.summary_total_lbl.config(text=f"£{amount_due / 100:.2f} ({amount_due}p)")

        if hasattr(self, "loyalty_status_lbl"):
            self.loyalty_status_lbl.config(text=status_text, fg=status_color)

    def _on_cancel_payment(self) -> None:
        """Cancels payment and slides back to catalogue with reverse motion."""
        self.controller.cancel()
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
        or allows typing member card ID manually (strictly no combobox / member list).
        """
        if self.controller.loyaltyApplied:
            if hasattr(self, "loyalty_status_lbl") and self.loyalty_status_lbl.winfo_exists():
                self.loyalty_status_lbl.config(text="⚠️ Loyalty discount is already active for this order!", fg=CLR_LIME)
            return

        dialog = tk.Toplevel(self.root)
        self._active_modal = dialog
        dialog.title("Scan Member Card (Code 128)")
        dw, dh = 580, 480
        dialog.geometry(f"{dw}x{dh}")
        dialog.minsize(520, 440)
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

        sub_hdr_lbl = tk.Label(
            dlg_hdr,
            text="Scan Code 128 Barcode with Camera or Enter Member ID Manually",
            font=("Helvetica", 10),
            fg=CLR_LILAC,
            bg=BG_APP,
        )
        sub_hdr_lbl.pack(anchor="w")

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
        manual_frame = tk.Frame(content_card, bg=BG_CARD)

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

        # -------------------------------------------------------------
        # 1. CAMERA SCANNER VIEW (Default)
        # -------------------------------------------------------------
        tk.Label(
            camera_frame,
            text="📷 ALIGN CODE 128 BARCODE INSIDE RETICLE",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(pady=(0, 4))

        video_lbl = tk.Label(camera_frame, bg=BG_SCREEN)
        video_lbl.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        cam_status_lbl = tk.Label(
            camera_frame,
            text="🔍 Point your Code 128 card barcode towards the camera...",
            font=("Helvetica", 10, "bold"),
            fg=CLR_LILAC,
            bg=BG_CARD,
        )
        cam_status_lbl.pack(pady=(4, 6))

        cam_btn_row = tk.Frame(camera_frame, bg=BG_CARD)
        cam_btn_row.pack(fill=tk.X, pady=(2, 0))

        type_btn = tk.Button(
            cam_btn_row,
            text="[ 1 ] ⌨️ Type Member ID Manually",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
            command=lambda: switch_to_manual(clear_msg=True),
        )
        type_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self._attach_button_animation(type_btn)

        cam_cancel_btn = tk.Button(
            cam_btn_row,
            text="[ Esc ] Cancel",
            font=("Helvetica", 11),
            bg=CLR_DARK_GREEN,
            fg=CLR_WHITE,
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
            command=on_close_dialog,
        )
        cam_cancel_btn.pack(side=tk.RIGHT)
        self._attach_button_animation(
            cam_cancel_btn,
            normal_bg=CLR_DARK_GREEN,
            normal_fg=CLR_WHITE,
            hover_bg=CLR_WHITE,
            hover_fg=CLR_DEEP_PURPLE,
        )

        # -------------------------------------------------------------
        # 2. MANUAL ENTRY VIEW (Alternative / Fallback)
        # -------------------------------------------------------------
        tk.Label(
            manual_frame,
            text="⌨️ ENTER MEMBER CARD ID MANUALLY",
            font=("Helvetica", 13, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            manual_frame,
            text="Type your student or staff membership card ID:",
            font=("Helvetica", 10),
            fg=CLR_WHITE,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 10))

        # Clean text entry — strictly no combobox and no member list!
        entry_box = tk.Frame(manual_frame, bg=BG_SCREEN, padx=10, pady=8, relief=tk.SUNKEN, bd=2)
        entry_box.pack(fill=tk.X, pady=(0, 10))

        card_id_entry = tk.Entry(
            entry_box,
            font=("Menlo", 15, "bold"),
            bg=BG_SCREEN,
            fg=CLR_LIME,
            insertbackground=CLR_LIME,
            relief=tk.FLAT,
            bd=0,
        )
        card_id_entry.pack(fill=tk.X)

        manual_status_lbl = tk.Label(
            manual_frame,
            text="",
            font=("Helvetica", 10, "bold"),
            fg=CLR_LIME,
            bg=BG_CARD,
        )
        manual_status_lbl.pack(pady=(0, 8))

        manual_btn_row = tk.Frame(manual_frame, bg=BG_CARD)
        manual_btn_row.pack(fill=tk.X, pady=(4, 0))

        def apply_manual_card():
            raw_id = card_id_entry.get().strip()
            if not raw_id:
                manual_status_lbl.config(text="⚠️ Please enter your Member Card ID", fg=CLR_LILAC)
                return

            success = self.controller.scanLoyalty(raw_id)
            if success:
                manual_status_lbl.config(text="✅ Card Verified! 10% Discount Applied!", fg=CLR_LIME)
                self._refresh_payment_page()
                dialog.after(700, on_close_dialog)
            else:
                manual_status_lbl.config(text=f"❌ Member Card '{raw_id}' is Invalid or Inactive", fg=CLR_LILAC)

        apply_btn = tk.Button(
            manual_btn_row,
            text="[ Enter ] ✓ Apply Member Discount",
            font=("Helvetica", 11, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
            command=apply_manual_card,
        )
        apply_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self._attach_button_animation(apply_btn)

        card_id_entry.bind("<Return>", lambda e: apply_manual_card())
        card_id_entry.bind("<KP_Enter>", lambda e: apply_manual_card())

        def on_loyalty_dlg_key(event: tk.Event):
            k = event.keysym
            ch = event.char
            if k == "Escape":
                on_close_dialog()
            elif camera_frame.winfo_ismapped():
                if ch == "1" or k in ("KP_1", "1", "Return", "KP_Enter"):
                    switch_to_manual(clear_msg=True)

        dialog.bind("<Key>", on_loyalty_dlg_key)

        switch_cam_btn = tk.Button(
            manual_btn_row,
            text="[ 2 ] 📷 Camera Scanner",
            font=("Helvetica", 11),
            bg=CLR_DARK_GREEN,
            fg=CLR_WHITE,
            relief=tk.FLAT,
            padx=10,
            pady=8,
            cursor="hand2",
            command=lambda: switch_to_camera(),
        )
        switch_cam_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._attach_button_animation(
            switch_cam_btn,
            normal_bg=CLR_DARK_GREEN,
            normal_fg=CLR_WHITE,
            hover_bg=CLR_WHITE,
            hover_fg=CLR_DEEP_PURPLE,
        )

        manual_cancel_btn = tk.Button(
            manual_btn_row,
            text="[ Esc ] Cancel",
            font=("Helvetica", 11),
            bg=CLR_DARK_GREEN,
            fg=CLR_WHITE,
            relief=tk.FLAT,
            padx=12,
            pady=8,
            cursor="hand2",
            command=on_close_dialog,
        )
        manual_cancel_btn.pack(side=tk.RIGHT)
        self._attach_button_animation(
            manual_cancel_btn,
            normal_bg=CLR_DARK_GREEN,
            normal_fg=CLR_WHITE,
            hover_bg=CLR_WHITE,
            hover_fg=CLR_DEEP_PURPLE,
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
                    "ALIGN CODE 128 BARCODE HERE",
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
                        text=f"✅ Scanned Code 128: '{detected_card_id}' — Verifying...",
                        fg=CLR_LIME,
                    )
                    success = self.controller.scanLoyalty(detected_card_id)
                    if success:
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
                        dialog.after(1400, lambda: switch_to_manual(prefill=detected_card_id))
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

        def switch_to_camera():
            manual_frame.pack_forget()
            camera_frame.pack(fill=tk.BOTH, expand=True)
            sub_hdr_lbl.config(text="Live Camera Active • Point Code 128 barcode at camera")
            cam_status_lbl.config(
                text="🔍 Point your Code 128 card barcode towards the camera...",
                fg=CLR_LILAC,
            )

            if not HAS_CV2 or cv2 is None:
                switch_to_manual(notice="⚠️ OpenCV unavailable. Please enter Member ID manually:")
                return

            try:
                scanner_state["cap"] = cv2.VideoCapture(0)
                if not scanner_state["cap"].isOpened():
                    scanner_state["cap"] = None
                    switch_to_manual(notice="📷 Camera device unavailable. Please enter Member ID manually:")
                    return
            except Exception:
                scanner_state["cap"] = None
                switch_to_manual(notice="📷 Camera device unavailable. Please enter Member ID manually:")
                return

            scanner_state["running"] = True
            update_camera_stream()

        def switch_to_manual(notice: Optional[str] = None, prefill: str = "", clear_msg: bool = False):
            cleanup_camera()
            camera_frame.pack_forget()
            manual_frame.pack(fill=tk.BOTH, expand=True)
            sub_hdr_lbl.config(text="Manual Member Card Entry • Type Card ID and Apply")
            if prefill:
                card_id_entry.delete(0, tk.END)
                card_id_entry.insert(0, prefill)
            if notice:
                manual_status_lbl.config(text=notice, fg=CLR_LIME)
            elif clear_msg:
                manual_status_lbl.config(text="")
            card_id_entry.focus_set()

        # Start directly with camera scanner (falls back cleanly to manual if no webcam)
        switch_to_camera()

    def _on_choose_cash(self) -> None:
        """Handles Cash payment selection and opens cash insertion dialog."""
        self._last_payment_method = "Cash Receiver"
        amount_due = self.controller.amountDue
        self.controller.startPayment(self.cash_receiver)
        self.cash_receiver.processPayment(amount_due)

        dialog = tk.Toplevel(self.root)
        self._active_modal = dialog
        dialog.title("Cash Payment Terminal")
        dialog.geometry("500x520")
        dialog.resizable(False, False)
        dialog.configure(bg=BG_APP)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._on_cancel_cash_dialog(dialog))

        # Center on parent
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 500) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 520) // 2
        dialog.geometry(f"+{x}+{y}")

        top_bar = tk.Frame(dialog, bg=BG_APP, padx=16, pady=12)
        top_bar.pack(fill=tk.X)
        tk.Label(
            top_bar,
            text="💵 CASH PAYMENT TERMINAL",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_APP,
        ).pack(anchor="w")

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
            wraplength=450,
            justify="left",
        )
        lbl_change.pack(anchor="w", pady=(2, 0))

        coins_box = tk.Frame(body, bg=BG_CARD, padx=12, pady=10)
        coins_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tk.Label(
            coins_box,
            text="Simulate Coin & Note Insertion (Keypad 1 - 9):",
            font=("Helvetica", 11, "bold"),
            fg=CLR_WHITE,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 6))

        grid_btn = tk.Frame(coins_box, bg=BG_CARD)
        grid_btn.pack(fill=tk.X)

        denominations = [
            ("[ 1 ] 1p", 1),
            ("[ 2 ] 2p", 2),
            ("[ 3 ] 5p", 5),
            ("[ 4 ] 10p", 10),
            ("[ 5 ] 20p", 20),
            ("[ 6 ] 50p", 50),
            ("[ 7 ] £1.00", 100),
            ("[ 8 ] £2.00", 200),
            ("[ 9 ] £5.00", 500),
        ]

        coin_buttons = []

        def insert_coin(pence: int):
            self.cash_receiver.insertItem(pence)
            inserted = self.cash_receiver._total
            rem = max(0, amount_due - inserted)
            lbl_inserted.config(text=f"Total Inserted: £{inserted / 100:.2f} ({inserted}p)")

            if self.cash_receiver._state == CashReceiverState.PAYMENT_COMPLETE:
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
            btn = tk.Button(
                grid_btn,
                text=label,
                font=("Menlo", 10, "bold"),
                bg=BTN_BG,
                fg=BTN_FG,
                relief=tk.FLAT,
                padx=6,
                pady=5,
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
            font=("Helvetica", 10),
            bg=CLR_DARK_GREEN,
            fg=CLR_WHITE,
            relief=tk.FLAT,
            padx=12,
            pady=6,
            command=lambda: self._on_cancel_cash_dialog(dialog),
        )
        cancel_btn.pack(side=tk.BOTTOM, fill=tk.X)
        self._attach_button_animation(cancel_btn, normal_bg=CLR_DARK_GREEN, normal_fg=CLR_WHITE, hover_bg=CLR_WHITE, hover_fg=CLR_DEEP_PURPLE)

        def on_cash_key(event: tk.Event):
            k = event.keysym
            ch = event.char
            if k == "Escape" or ch in ("c", "C"):
                self._on_cancel_cash_dialog(dialog)
                return "break"
            key_map = {
                "1": (0, 1), "KP_1": (0, 1),
                "2": (1, 2), "KP_2": (1, 2),
                "3": (2, 5), "KP_3": (2, 5),
                "4": (3, 10), "KP_4": (3, 10),
                "5": (4, 20), "KP_5": (4, 20),
                "6": (5, 50), "KP_6": (5, 50),
                "7": (6, 100), "KP_7": (6, 100),
                "8": (7, 200), "KP_8": (7, 200),
                "9": (8, 500), "KP_9": (8, 500),
            }
            target = key_map.get(k) or key_map.get(ch)
            if target:
                idx, val = target
                if idx < len(coin_buttons):
                    btn = coin_buttons[idx]
                    if btn.cget("state") != tk.DISABLED:
                        btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                        dialog.after(120, lambda b=btn: self._safe_config(b, bg=BTN_BG, relief=tk.FLAT))
                insert_coin(val)
                return "break"

        dialog.bind("<Key>", on_cash_key)
        cancel_btn.focus_set()

    def _on_choose_card(self) -> None:
        """Handles Card payment selection and opens card reader terminal dialog."""
        self._last_payment_method = "Contactless Card"
        amount_due = self.controller.amountDue
        self.controller.startPayment(self.card_reader)
        self.card_reader.readCard("DEBIT-4021")

        dialog = tk.Toplevel(self.root)
        self._active_modal = dialog
        dialog.title("Card Payment Terminal")
        dialog.geometry("480x380")
        dialog.resizable(False, False)
        dialog.configure(bg=BG_APP)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._on_cancel_card_dialog(dialog))

        # Center on parent
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 480) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 380) // 2
        dialog.geometry(f"+{x}+{y}")

        top_bar = tk.Frame(dialog, bg=BG_APP, padx=16, pady=12)
        top_bar.pack(fill=tk.X)
        tk.Label(
            top_bar,
            text="💳 CARD PAYMENT TERMINAL",
            font=("Helvetica", 14, "bold"),
            fg=CLR_LIME,
            bg=BG_APP,
        ).pack(anchor="w")

        body = tk.Frame(dialog, bg=BG_MIDDLE, padx=16, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        screen = tk.Frame(body, bg=BG_SCREEN, padx=16, pady=16, highlightthickness=2, highlightbackground=CLR_LIME)
        screen.pack(fill=tk.X, pady=(0, 16))

        tk.Label(
            screen,
            text=f"Total Charge: £{amount_due / 100:.2f} ({amount_due}p)",
            font=("Helvetica", 13, "bold"),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        ).pack(anchor="w")

        status_lbl = tk.Label(
            screen,
            text="📶 Terminal Ready • Please tap contactless card or phone",
            font=("Helvetica", 11),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        status_lbl.pack(anchor="w", pady=(8, 0))

        action_box = tk.Frame(body, bg=BG_CARD, padx=16, pady=16)
        action_box.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        def tap_card():
            tap_btn.config(state=tk.DISABLED)
            status_lbl.config(text="⏳ Communicating with bank server...", fg=CLR_WHITE)
            dialog.update_idletasks()

            def process_bank():
                result = self.card_reader.processPayment(amount_due)
                if result == PaymentResult.SUCCESS:
                    status_lbl.config(text="✅ Approved by Bank! Dispensing drink...", fg=CLR_LIME)
                    self.controller.onPaymentComplete()
                    self.root.after(1200, lambda: self._on_sale_completed_dismiss(dialog))
                else:
                    status_lbl.config(text="❌ Declined by bank server", fg=CLR_LILAC)
                    tap_btn.config(state=tk.NORMAL)

            self.root.after(450, process_bank)

        tap_btn = tk.Button(
            action_box,
            text="[ 1 ] 📶 TAP CONTACTLESS CARD / PHONE (Enter)",
            font=("Helvetica", 13, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            pady=12,
            command=tap_card,
        )
        tap_btn.pack(fill=tk.X, pady=(4, 0))
        self._attach_button_animation(tap_btn)

        tk.Label(
            action_box,
            text="Keypad: Press [ 1 ] or [ Enter ] to tap card, [ Esc ] to cancel",
            font=("Helvetica", 10),
            fg=CLR_WHITE,
            bg=BG_CARD,
        ).pack(pady=(8, 0))

        cancel_btn = tk.Button(
            body,
            text="[ Esc ] Cancel Card Transaction",
            font=("Helvetica", 11),
            bg=CLR_DARK_GREEN,
            fg=CLR_WHITE,
            relief=tk.FLAT,
            padx=12,
            pady=6,
            command=lambda: self._on_cancel_card_dialog(dialog),
        )
        cancel_btn.pack(side=tk.BOTTOM, fill=tk.X)
        self._attach_button_animation(cancel_btn, normal_bg=CLR_DARK_GREEN, normal_fg=CLR_WHITE, hover_bg=CLR_WHITE, hover_fg=CLR_DEEP_PURPLE)

        def on_card_key(event: tk.Event):
            k = event.keysym
            ch = event.char
            if k in ("Escape", "KP_4") or ch in ("c", "C", "4"):
                self._on_cancel_card_dialog(dialog)
            elif k in ("Return", "KP_Enter", "KP_1", "1") or ch == "1":
                if tap_btn.cget("state") != tk.DISABLED:
                    tap_btn.config(bg=CLR_WHITE, relief=tk.SUNKEN)
                    dialog.after(120, lambda: self._safe_config(tap_btn, bg=BTN_BG, relief=tk.FLAT))
                    tap_card()

        dialog.bind("<Key>", on_card_key)
        tap_btn.focus_set()

    def _on_cancel_cash_dialog(self, dialog: tk.Toplevel) -> None:
        """Handles cancellation of active cash payment."""
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

    def _on_cancel_card_dialog(self, dialog: tk.Toplevel) -> None:
        """Handles cancellation of active card payment."""
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

        # 2. Middle Celebratory Area (Color #D883FF)
        middle_area = tk.Frame(page, bg=BG_MIDDLE)
        middle_area.pack(fill=tk.BOTH, expand=True)

        center_wrap = tk.Frame(middle_area, bg=BG_MIDDLE)
        center_wrap.pack(expand=True, fill=tk.BOTH, padx=20, pady=8)

        # Center celebratory card box (Background: #FFFFFF, Border: #BAEF2D)
        card = tk.Frame(
            center_wrap,
            bg=BG_CARD,
            padx=28,
            pady=14,
            highlightthickness=3,
            highlightbackground=CLR_LIME,
        )
        card.pack(expand=True, fill=tk.Y, pady=4)

        # Celebration Header
        tk.Label(
            card,
            text="🎉 ORDER DISPENSED SUCCESSFULLY!",
            font=("Helvetica", 16, "bold"),
            fg=CLR_DEEP_PURPLE,
            bg=BG_CARD,
        ).pack(anchor="center", pady=(0, 4))

        # Product Artwork / Photo Canvas
        self.success_canvas = tk.Canvas(
            card,
            width=180,
            height=110,
            bg=BG_SCREEN,
            highlightthickness=2,
            highlightbackground=CLR_LILAC,
        )
        self.success_canvas.pack(anchor="center", pady=4)

        # Drink Name Label
        self.success_drink_name_lbl = tk.Label(
            card,
            text="Your Beverage",
            font=("Helvetica", 15, "bold"),
            fg=CLR_DEEP_PURPLE,
            bg=BG_CARD,
        )
        self.success_drink_name_lbl.pack(anchor="center", pady=(2, 3))

        # Info Box (Paid & Method)
        info_row = tk.Frame(card, bg=BG_SCREEN, padx=14, pady=5, highlightthickness=1, highlightbackground=CLR_LILAC)
        info_row.pack(fill=tk.X, pady=(2, 6))

        self.success_paid_lbl = tk.Label(
            info_row,
            text="Total Paid: £0.00",
            font=("Helvetica", 11, "bold"),
            fg=CLR_LIME,
            bg=BG_SCREEN,
        )
        self.success_paid_lbl.pack(side=tk.LEFT, padx=6)

        self.success_method_lbl = tk.Label(
            info_row,
            text="Method: Cash Receiver",
            font=("Helvetica", 11),
            fg=CLR_WHITE,
            bg=BG_SCREEN,
        )
        self.success_method_lbl.pack(side=tk.RIGHT, padx=6)

        # Tray Collection Instruction
        tk.Label(
            card,
            text="⬇️ Please take your cup/can from the dispenser compartment below ⬇️",
            font=("Helvetica", 11, "bold"),
            fg=CLR_DARK_GREEN,
            bg=BG_CARD,
        ).pack(anchor="center", pady=(3, 5))

        # Live Countdown Label
        self.success_countdown_lbl = tk.Label(
            card,
            text="⏱️ Auto-returning to catalogue in 10s...",
            font=("Menlo", 12, "bold"),
            fg=CLR_DEEP_PURPLE,
            bg=BG_CARD,
        )
        self.success_countdown_lbl.pack(anchor="center", pady=(2, 4))

        # Return Button
        self.return_home_btn = tk.Button(
            card,
            text="[ Enter ] Return to Catalogue (10s)",
            font=("Helvetica", 12, "bold"),
            bg=BTN_BG,
            fg=BTN_FG,
            relief=tk.FLAT,
            padx=16,
            pady=8,
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
            text="Official Smart Drink Dispenser",
            font=("Helvetica", 10),
            fg=CLR_LILAC,
            bg=BG_APP,
        ).pack(side=tk.LEFT, padx=12, pady=18)

        # Step Indicator Badge
        step_badge = tk.Label(
            header,
            text="STEP 3: ORDER SUCCESSFUL",
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

        tk.Label(
            footer,
            text="💡 Tip: Press [ Enter ] or [ Esc ] on keypad to return immediately.",
            font=("Helvetica", 10),
            fg=CLR_WHITE,
            bg=BG_APP,
        ).pack(side=tk.LEFT, pady=10)

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
        """Populates the success page widgets with details of the dispensed beverage."""
        info = getattr(self, "last_completed_order", None) or {}
        drink_name = info.get("name", "Your Beverage")
        slot_num = info.get("slot_num", "--")
        price = info.get("price", 0)
        method = info.get("method", "Payment Terminal")
        loyalty = info.get("loyalty_applied", False)
        img_name = info.get("image", "")
        icon_type = info.get("icon_type", "water")

        if hasattr(self, "success_drink_name_lbl") and self.success_drink_name_lbl.winfo_exists():
            self.success_drink_name_lbl.config(text=f"{drink_name} (Slot {slot_num})")

        change_amount = info.get("change_amount", 0)
        change_summary = info.get("change_summary", "")

        if hasattr(self, "success_paid_lbl") and self.success_paid_lbl.winfo_exists():
            discount_note = " (-10% Loyalty)" if loyalty else ""
            change_note = f" • Change: £{change_amount / 100:.2f} ({change_summary})" if change_amount > 0 and change_summary else (f" • Change: £{change_amount / 100:.2f}" if change_amount > 0 else "")
            self.success_paid_lbl.config(text=f"Total Paid: £{price / 100:.2f} ({price}p){discount_note}{change_note}")

        if hasattr(self, "success_method_lbl") and self.success_method_lbl.winfo_exists():
            self.success_method_lbl.config(text=f"Method: {method}")

        if hasattr(self, "success_canvas") and self.success_canvas.winfo_exists():
            render_product_artwork(
                canvas=self.success_canvas,
                prod=info,
                width=180,
                height=110,
                photo_cache=self._product_images,
                default_bg=CLR_WHITE,
                fallback_bg=BG_CARD,
            )

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


# ===========================================================================
# Launch Entrypoint
# ===========================================================================
def main():
    root = tk.Tk()
    app = CustomerVendingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

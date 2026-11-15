"""
Code 128 Barcode Camera Scanner (barcode_scanner.py)
---------------------------------------------------
Provides webcam-based live scanning of loyalty cards, with dedicated
support for Code 128 1D linear barcodes using zxing-cpp & OpenCV.
Integrates seamlessly with Tkinter as a modal scanning dialog.
"""

import os
import base64
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional, Tuple

# Safe OpenCV (cv2) import with graceful error handling
try:
    import cv2  # type: ignore
    HAS_CV2 = True
except (ImportError, ModuleNotFoundError):
    cv2 = None  # type: ignore
    HAS_CV2 = False

# Optional PIL (Pillow) support with pure OpenCV + Tkinter fallback
try:
    from PIL import Image, ImageTk  # type: ignore
    HAS_PIL = True
except (ImportError, ModuleNotFoundError):
    Image = None  # type: ignore
    ImageTk = None  # type: ignore
    HAS_PIL = False

# Import zxing-cpp for Code 128 linear barcode decoding.
# NOTE: Install via: pip install zxing-cpp (package name has a hyphen; Python import is 'zxingcpp')
try:
    import zxingcpp  # type: ignore
    HAS_ZXING = True
except (ImportError, ModuleNotFoundError):
    try:
        import importlib
        zxingcpp = importlib.import_module("zxingcpp")  # type: ignore
        HAS_ZXING = True
    except Exception:
        zxingcpp = None  # type: ignore
        HAS_ZXING = False


class BarcodeDetectorEngine:
    """
    Decodes Code 128 1D linear barcodes from live camera video frames.
    """

    def __init__(self):
        # 1. zxing-cpp setup (fast and highly accurate for Code 128)
        self.has_zxing = HAS_ZXING
        if self.has_zxing:
            print("[BarcodeDetectorEngine] zxing-cpp engine loaded (Code 128 dedicated).")
        else:
            print(
                "[BarcodeDetectorEngine] ⚠️ Warning: 'zxingcpp' module not found in this Python environment.\n"
                "  To enable high-accuracy Code 128 barcode reading, install via:\n"
                "    pip install zxing-cpp\n"
                "  Falling back to OpenCV native 1D barcode detector."
            )

        # 2. OpenCV fallback detector (1D barcodes only)
        if not HAS_CV2 or cv2 is None:
            print("[BarcodeDetectorEngine] ⚠️ OpenCV (cv2) not available.")
            self._cv_barcode_detector = None
            return

        try:
            self._cv_barcode_detector = cv2.barcode.BarcodeDetector()
        except Exception:
            self._cv_barcode_detector = None

    def decode_frame(self, frame) -> Optional[Tuple[str, str]]:
        """
        Attempt to detect and decode a Code 128 1D linear barcode from a video frame.

        :param frame: OpenCV image (BGR numpy array)
        :return: Tuple of (decoded_text, "Code 128") if found, otherwise None.
        """
        if frame is None:
            return None

        # Primary engine: zxing-cpp (strictly Code 128 format)
        if self.has_zxing and zxingcpp is not None:
            try:
                c128_results = zxingcpp.read_barcodes(frame, formats=zxingcpp.BarcodeFormat.Code128)
                for res in c128_results:
                    if res.text and res.text.strip():
                        return res.text.strip(), "Code 128"
            except Exception:
                pass

        # Fallback: OpenCV 1D Barcode detector
        if self._cv_barcode_detector is not None:
            try:
                ret, decoded_info, decoded_type, points = self._cv_barcode_detector.detectAndDecode(frame)
                if ret:
                    if isinstance(decoded_info, (list, tuple)):
                        for item in decoded_info:
                            if item and item.strip():
                                return item.strip(), "Code 128"
                    elif isinstance(decoded_info, str) and decoded_info.strip():
                        return decoded_info.strip(), "Code 128"
            except Exception:
                pass

        return None

    def decode_code128(self, frame) -> Optional[str]:
        """
        Specifically decode only Code 128 barcodes from a video frame.
        """
        res = self.decode_frame(frame)
        if res:
            text, _ = res
            return text
        return None


class BarcodeCameraScanner:
    """
    Manages live camera capture inside a Tkinter popup window.
    Focuses on Code 128 linear barcodes with a wide scanning reticle.
    """

    def __init__(self):
        self.engine = BarcodeDetectorEngine()
        self._cap = None
        self._window: Optional[tk.Toplevel] = None
        self._on_detected: Optional[Callable[[str], None]] = None
        self._is_running: bool = False
        self._photo_ref = None

    def start_scan(
        self,
        parent: tk.Tk,
        on_detected: Callable[[str], None],
        camera_index: int = 0,
    ) -> None:
        """
        Opens a popup dialog displaying the live camera stream and scans for Code 128 barcodes.

        :param parent: Parent Tkinter window.
        :param on_detected: Callback function invoked with detected card ID string.
        :param camera_index: Webcam device index (default 0).
        """
        if self._is_running:
            return

        if not HAS_CV2 or cv2 is None:
            messagebox.showerror(
                "OpenCV Required",
                "OpenCV ('cv2') is required for webcam scanning.\n"
                "Please run in your terminal:\n\n"
                "    pip3 install opencv-python\n\n"
                "You can still enter card IDs directly in the main window.",
                parent=parent,
            )
            return

        self._on_detected = on_detected
        self._is_running = True

        # Open camera
        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            self._is_running = False
            messagebox.showerror(
                "Camera Error",
                "Could not open webcam.\nPlease check camera connections and macOS privacy permissions.",
            )
            return

        # Create TopLevel Popup
        self._window = tk.Toplevel(parent)
        self._window.title("📷 Code 128 Barcode Scanner")
        self._window.geometry("660x580")
        self._window.resizable(False, False)
        self._window.transient(parent)
        self._window.grab_set()

        # Handle window close (X button)
        self._window.protocol("WM_DELETE_WINDOW", self.stop_scan)

        # UI Header
        header = tk.Frame(self._window, bg="#0f172a", padx=12, pady=10)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="📷 Scan Membership Card (Code 128 Barcode)",
            font=("Helvetica", 14, "bold"),
            fg="#38bdf8",
            bg="#0f172a",
        ).pack()
        tk.Label(
            header,
            text="Hold your Code 128 linear barcode inside the green frame",
            font=("Helvetica", 9),
            fg="#94a3b8",
            bg="#0f172a",
        ).pack(pady=(2, 0))

        if not self.engine.has_zxing:
            tk.Label(
                header,
                text="⚠️ zxing-cpp library not found — Code 128 detection limited. Run: pip install zxing-cpp",
                font=("Helvetica", 8, "italic"),
                fg="#f59e0b",
                bg="#0f172a",
            ).pack(pady=(3, 0))

        # Video stream label
        self._video_label = tk.Label(self._window, bg="#000000")
        self._video_label.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Control Bar
        control_frame = ttk.Frame(self._window, padding=8)
        control_frame.pack(fill=tk.X)

        ttk.Button(
            control_frame,
            text="❌ Cancel & Close Camera",
            command=self.stop_scan,
        ).pack(side=tk.RIGHT, padx=6)

        # Start video polling loop
        self._update_frame()

    def _update_frame(self) -> None:
        """Fetch frame from webcam, scan for Code 128 barcode, and render to UI."""
        if not self._is_running or self._cap is None:
            return

        ret, frame = self._cap.read()
        if ret and frame is not None:
            # 1. Flip horizontally for mirror effect (more natural for user)
            frame = cv2.flip(frame, 1)
            h, w, _ = frame.shape

            # 2. Draw wide horizontal green targeting reticle (optimal for Code 128 barcodes)
            box_w, box_h = int(w * 0.75), int(h * 0.40)
            x1 = (w - box_w) // 2
            y1 = (h - box_h) // 2
            x2 = x1 + box_w
            y2 = y1 + box_h
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Center guide line
            mid_y = y1 + (box_h // 2)
            cv2.line(frame, (x1 + 15, mid_y), (x2 - 15, mid_y), (0, 200, 255), 1)

            cv2.putText(
                frame,
                "ALIGN CODE 128 BARCODE HERE",
                (x1 + 10, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 0),
                2,
            )

            # 3. Detect Code 128 barcode
            detection = self.engine.decode_frame(frame)
            if detection:
                detected_text, fmt = detection
                print(f"[BarcodeScanner] Successfully detected {fmt}: '{detected_text}'")
                self._handle_successful_scan(detected_text)
                return

            # 4. Render frame to Tkinter label
            if HAS_PIL and Image is not None and ImageTk is not None:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb_frame)
                img = img.resize((640, 430), Image.Resampling.LANCZOS)
                self._photo_ref = ImageTk.PhotoImage(image=img)
            else:
                # Native Tkinter + OpenCV fallback (does not require PIL)
                resized = cv2.resize(frame, (640, 430))
                ret_enc, buf = cv2.imencode(".png", resized)
                if ret_enc:
                    b64_data = base64.b64encode(buf).decode("ascii")
                    self._photo_ref = tk.PhotoImage(data=b64_data)
                else:
                    self._photo_ref = None

            if self._photo_ref is not None:
                self._video_label.config(image=self._photo_ref)

        if self._is_running and self._window is not None:
            self._window.after(30, self._update_frame)

    def _handle_successful_scan(self, detected_text: str) -> None:
        """Cleans up camera resources and notifies the caller."""
        cb = self._on_detected
        self.stop_scan()
        if cb:
            cb(detected_text)

    def stop_scan(self) -> None:
        """Releases the camera and closes the popup dialog."""
        self._is_running = False
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        if self._window is not None:
            try:
                self._window.grab_release()
                self._window.destroy()
            except Exception:
                pass
            self._window = None
        self._photo_ref = None

"""
Barcode & QR Code Camera Scanner (barcode_scanner.py)
---------------------------------------------------
Provides webcam-based live scanning of loyalty cards, with first-class
support for Code 128 1D barcodes and 2D QR codes using zxing-cpp & OpenCV.
Integrates seamlessly with Tkinter as a modal scanning dialog.
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Callable, Optional, Tuple
from PIL import Image, ImageTk
import cv2

# Import zxing-cpp for Code 128 and linear barcode decoding
try:
    import zxingcpp
    HAS_ZXING = True
except ImportError:
    HAS_ZXING = False


class BarcodeDetectorEngine:
    """
    Decodes Code 128 1D barcodes and 2D QR codes from camera video frames
    or image files on disk.
    """

    def __init__(self):
        # 1. zxing-cpp setup (fast and highly accurate for Code 128)
        self.has_zxing = HAS_ZXING
        if self.has_zxing:
            print("[BarcodeDetectorEngine] zxing-cpp engine loaded (Code 128 optimized).")

        # 2. OpenCV fallback detectors
        self._qr_detector = cv2.QRCodeDetector()
        try:
            self._cv_barcode_detector = cv2.barcode.BarcodeDetector()
        except Exception:
            self._cv_barcode_detector = None

    def decode_frame(self, frame) -> Optional[Tuple[str, str]]:
        """
        Attempt to detect and decode a Code 128 barcode or QR code from a video frame.

        :param frame: OpenCV image (BGR numpy array)
        :return: Tuple of (decoded_text, format_name) if found, otherwise None.
        """
        if frame is None:
            return None

        # Primary engine: zxing-cpp (robust Code 128 & Linear barcodes)
        if self.has_zxing:
            try:
                # 1. Try specifically for Code 128 first
                c128_results = zxingcpp.read_barcodes(frame, formats=zxingcpp.BarcodeFormat.Code128)
                for res in c128_results:
                    if res.text and res.text.strip():
                        return res.text.strip(), "Code 128"

                # 2. Try general barcode / QR detection
                all_results = zxingcpp.read_barcodes(frame)
                for res in all_results:
                    if res.text and res.text.strip():
                        return res.text.strip(), str(res.format)
            except Exception as e:
                pass

        # Fallback 1: OpenCV QR Code detector
        try:
            text, points, _ = self._qr_detector.detectAndDecode(frame)
            if text and text.strip():
                return text.strip(), "QR Code"
        except Exception:
            pass

        # Fallback 2: OpenCV 1D Barcode detector
        if self._cv_barcode_detector is not None:
            try:
                ret, decoded_info, decoded_type, points = self._cv_barcode_detector.detectAndDecode(frame)
                if ret:
                    if isinstance(decoded_info, (list, tuple)):
                        for item in decoded_info:
                            if item and item.strip():
                                return item.strip(), "1D Barcode"
                    elif isinstance(decoded_info, str) and decoded_info.strip():
                        return decoded_info.strip(), "1D Barcode"
            except Exception:
                pass

        return None

    def decode_code128(self, frame) -> Optional[str]:
        """
        Specifically decode only Code 128 barcodes from a frame.
        """
        res = self.decode_frame(frame)
        if res:
            text, fmt = res
            return text
        return None

    def decode_file(self, file_path: str) -> Optional[Tuple[str, str]]:
        """
        Read an image from disk and decode any Code 128 barcode or QR code.
        """
        if not os.path.exists(file_path):
            return None
        img = cv2.imread(file_path)
        if img is None:
            return None
        return self.decode_frame(img)


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

        self._on_detected = on_detected
        self._is_running = True

        # Open camera
        self._cap = cv2.VideoCapture(camera_index)
        if not self._cap.isOpened():
            self._is_running = False
            messagebox.showerror(
                "Camera Error",
                "Could not open webcam.\nPlease check camera connections and macOS privacy permissions,\n"
                "or use the 'Upload Barcode Image' feature to test with sample Code 128 barcodes.",
            )
            return

        # Create TopLevel Popup
        self._window = tk.Toplevel(parent)
        self._window.title("📷 Code 128 Barcode & QR Scanner")
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
            text="Hold your Code 128 linear barcode or QR code inside the green frame",
            font=("Helvetica", 9),
            fg="#94a3b8",
            bg="#0f172a",
        ).pack(pady=(2, 0))

        # Video stream label
        self._video_label = tk.Label(self._window, bg="#000000")
        self._video_label.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Control Bar
        control_frame = ttk.Frame(self._window, padding=8)
        control_frame.pack(fill=tk.X)

        ttk.Button(
            control_frame,
            text="📁 Test with Sample Code 128 Image...",
            command=self._upload_image,
        ).pack(side=tk.LEFT, padx=6)

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

            # 3. Detect Code 128 barcode or QR
            detection = self.engine.decode_frame(frame)
            if detection:
                detected_text, fmt = detection
                print(f"[BarcodeScanner] Successfully detected {fmt}: '{detected_text}'")
                self._handle_successful_scan(detected_text)
                return

            # 4. Convert BGR to RGB for Tkinter display
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb_frame)
            img = img.resize((640, 430), Image.Resampling.LANCZOS)
            self._photo_ref = ImageTk.PhotoImage(image=img)
            self._video_label.config(image=self._photo_ref)

        if self._is_running and self._window is not None:
            self._window.after(30, self._update_frame)

    def _handle_successful_scan(self, detected_text: str) -> None:
        """Cleans up camera resources and notifies the caller."""
        cb = self._on_detected
        self.stop_scan()
        if cb:
            cb(detected_text)

    def _upload_image(self) -> None:
        """Allow testing via a Code 128 barcode image file."""
        initial_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "barcodes"
        )
        if not os.path.exists(initial_dir):
            initial_dir = os.path.dirname(os.path.abspath(__file__))

        file_path = filedialog.askopenfilename(
            parent=self._window,
            initialdir=initial_dir,
            title="Select Code 128 Barcode Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All Files", "*.*")],
        )
        if not file_path:
            return

        result = self.engine.decode_file(file_path)
        if result:
            detected_text, fmt = result
            print(f"[BarcodeScanner] Decoded {fmt} from file: '{detected_text}'")
            self._handle_successful_scan(detected_text)
        else:
            messagebox.showwarning(
                "Scan Result",
                "No valid Code 128 barcode or QR code detected in the selected image.",
                parent=self._window,
            )

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

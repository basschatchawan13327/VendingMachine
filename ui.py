"""
Vending Machine Prototype & Test Suite (ui.py)
-----------------------------------------------
GUI prototype implementation following the UML Class Diagram:
- VendingGUI (controller, drinkButtons, statusLabel)
  + onDrinkSelected(drinkId)
  + onScanCard(cardId)
  + onInsertMoney(pence)
  + onTapCard(cardId)
  + onCancel()
  + refreshDisplay()

Wires together:
  VendingController, DrinkDispenser, Drink, StockSensor,
  LoyaltyScanner, LoyaltyAccount, PaymentModule, CashReceiver,
  CashValidator, ChangeDispenser, CardReader, BankService,
  MockBankService, Logger, TransactionRecord, and TransactionTimer.
"""

import sys
import time
import io
import argparse
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from typing import List, Optional

# Core imports
from controller import (
    VendingController,
    MachineState,
    load_products,
    save_products,
    load_members,
    save_members,
    load_transactions,
    save_transactions,
    load_activity_logs,
    log_activity,
)
from inventory import Drink, DrinkDispenser, StockSensor, LoyaltyAccount, LoyaltyScanner
from payment import (
    PaymentModule,
    PaymentResult,
    PaymentMethod,
    CashReceiver,
    CashReceiverState,
    CashValidator,
    ChangeDispenser,
    CardReader,
)
from bank import BankService, MockBankService
from logger import Logger, TransactionRecord
from timer import TransactionTimer
from barcode_scanner import BarcodeCameraScanner


# ===========================================================================
# Stdout Redirector for Live UI Console Output
# ===========================================================================

class ConsoleRedirector(io.StringIO):
    """Duplicates stdout to both standard terminal stream and a UI text callback."""
    def __init__(self, original_stdout, callback=None):
        super().__init__()
        self.original_stdout = original_stdout
        self.callback = callback

    def write(self, s: str):
        self.original_stdout.write(s)
        if self.callback:
            try:
                self.callback(s)
            except Exception:
                pass

    def flush(self):
        self.original_stdout.flush()


# ===========================================================================
# System Factory / Initializer
# ===========================================================================

def build_vending_system() -> tuple[
    VendingController,
    DrinkDispenser,
    StockSensor,
    LoyaltyScanner,
    PaymentModule,
    CashReceiver,
    CardReader,
    MockBankService,
    Logger,
    TransactionTimer,
]:
    """
    Constructs and connects all components according to the UML Class Diagram.
    """
    # 1. Drinks loaded from products.json database
    loaded_drinks = load_products()
    if not loaded_drinks:
        loaded_drinks = [
            Drink("ESPRESSO", "Espresso", 150, stock=8),
            Drink("LATTE", "Latte", 220, stock=8),
            Drink("HOT_CHOCOLATE", "Hot Chocolate", 200, stock=6),
            Drink("WATER", "Bottled Water", 100, stock=12),
        ]
        save_products(loaded_drinks)
    dispenser = DrinkDispenser(loaded_drinks)
    stock_sensor = StockSensor(dispenser, low_stock_level=3)

    # 2. Loyalty Programme loaded from members.json database
    loaded_accounts = load_members()
    if not loaded_accounts:
        loaded_accounts = [
            LoyaltyAccount("LOYAL-001", "Alice Smith", active=True),
            LoyaltyAccount("LOYAL-002", "Bob Jones", active=False),  # inactive test
            LoyaltyAccount("LOYAL-003", "Carol White", active=True),
        ]
        save_members(loaded_accounts)
    loyalty_scanner = LoyaltyScanner(loaded_accounts, discount_rate=0.10)

    # 3. Cash Hardware with Composition (CashReceiver owns CashValidator and ChangeDispenser)
    validator = CashValidator()
    change_dispenser = ChangeDispenser(
        coin_stock={200: 5, 100: 10, 50: 10, 20: 20, 10: 20, 5: 30, 2: 50, 1: 100}
    )
    cash_receiver = CashReceiver(validator=validator, dispenser=change_dispenser)

    # 4. Card Hardware & Mock Bank
    mock_bank = MockBankService()
    card_reader = CardReader(bank=mock_bank)

    # 5. Payment Module
    payment_module = PaymentModule(supported_methods=[cash_receiver, card_reader])

    # 6. Logger and Timer (load past transactions from database)
    logger = Logger()
    for past_tx in load_transactions():
        logger._records.append(past_tx)
    timer = TransactionTimer(timeout_seconds=30)

    # 7. VendingController (central coordinator with 6 compositions)
    controller = VendingController(
        dispenser=dispenser,
        loyalty_scanner=loyalty_scanner,
        payment_module=payment_module,
        logger=logger,
        timer=timer,
        stock_sensor=stock_sensor,
    )

    return (
        controller,
        dispenser,
        stock_sensor,
        loyalty_scanner,
        payment_module,
        cash_receiver,
        card_reader,
        mock_bank,
        logger,
        timer,
    )


# ===========================================================================
# VendingGUI (UML Specified Class)
# ===========================================================================

class VendingGUI:
    """
    «GUI prototype»
    Class specified in the UML Class Diagram:
    Attributes:
        - controller: VendingController
        - drinkButtons: List[ttk.Button]
        - statusLabel: ttk.Label
    Methods:
        + onDrinkSelected(drinkId)
        + onScanCard(cardId)
        + onInsertMoney(pence)
        + onTapCard(cardId)
        + onCancel()
        + refreshDisplay()
    """

    def __init__(self, root: tk.Tk, controller: VendingController, system_bundle: tuple):
        self.root = root
        (
            self._controller,
            self._dispenser,
            self._stock_sensor,
            self._loyalty_scanner,
            self._payment_module,
            self._cash_receiver,
            self._card_reader,
            self._mock_bank,
            self._logger,
            self._timer,
        ) = system_bundle

        # UML Attributes
        self._drink_buttons: List[ttk.Button] = []
        self._status_label: Optional[ttk.Label] = None

        # Build GUI Layout
        self._build_ui()

        # Start periodic tick for timer and LCD refresh
        self._schedule_tick()

    # ------------------------------------------------------------------
    # UML Specified Public Methods
    # ------------------------------------------------------------------

    def onDrinkSelected(self, drinkId: str) -> None:
        """
        Invoked when the user clicks a drink button or selects a drink.
        """
        success = self._controller.selectDrink(drinkId)
        self.refreshDisplay()
        if not success:
            state_name = self._controller._state.name
            messagebox.showwarning(
                "Drink Selection",
                f"Cannot select drink '{drinkId}'. Machine is in {state_name} state or drink is out of stock."
            )

    def onScanCard(self, cardId: str) -> None:
        """
        Invoked when the user scans a loyalty card.
        """
        success = self._controller.scanLoyalty(cardId)
        self.refreshDisplay()
        if success:
            discount_pct = int(self._loyalty_scanner.getDiscountRate() * 100)
            messagebox.showinfo(
                "Loyalty Discount",
                f"Loyalty card '{cardId}' verified!\n"
                f"{discount_pct}% discount applied. Amount due: {self._controller._amount_due}p"
            )
        else:
            messagebox.showerror(
                "Loyalty Scan Failed",
                f"Card '{cardId}' is invalid, inactive, or not scanned during drink selection."
            )

    def onInsertMoney(self, pence: int) -> None:
        """
        Invoked when coins or notes are inserted into the machine.
        """
        if self._controller._state not in (MachineState.DRINK_SELECTED, MachineState.PAYMENT_PROCESSING):
            messagebox.showwarning("Payment", "Please select a drink first before inserting money.")
            return

        # Start cash payment if not yet in payment processing
        if self._controller._state == MachineState.DRINK_SELECTED:
            self._controller.startPayment(self._cash_receiver)
            self._cash_receiver.processPayment(self._controller._amount_due)

        # Feed item directly to CashReceiver (which internally validates and dispenses change)
        self._cash_receiver.insertItem(pence)

        # Check if cash receiver completed payment
        if self._cash_receiver._state == CashReceiverState.PAYMENT_COMPLETE:
            self._controller.onPaymentComplete()
            self._cash_receiver._state = CashReceiverState.IDLE
            messagebox.showinfo("Sale Complete", f"Payment received! Dispensed your drink. Enjoy!")

        self.refreshDisplay()

    def onTapCard(self, cardId: str) -> None:
        """
        Invoked when a payment card is tapped or read at the card terminal.
        """
        if self._controller._state != MachineState.DRINK_SELECTED:
            messagebox.showwarning("Card Payment", "Please select a drink first.")
            return

        self._card_reader.readCard(cardId)
        self._controller.startPayment(self._card_reader)
        result = self._card_reader.processPayment(self._controller._amount_due)

        if result == PaymentResult.SUCCESS:
            self._controller.onPaymentComplete()
            self.refreshDisplay()
            messagebox.showinfo("Payment Successful", f"Card approved! Dispensed your drink. Thank you!")
        else:
            reason = "Card transaction declined by bank"
            self._controller.onPaymentFailed(reason)
            self.refreshDisplay()
            messagebox.showerror("Payment Failed", f"{reason}. Transaction aborted.")

    def onCancel(self) -> None:
        """
        Invoked when the user presses the Cancel button.
        """
        if self._controller._state in (MachineState.IDLE, MachineState.COMPLETED, MachineState.CANCELLED):
            messagebox.showinfo("Cancel", "No active transaction to cancel.")
            return

        self._controller.cancel()
        self.refreshDisplay()
        messagebox.showinfo("Cancelled", "Transaction cancelled. Any inserted cash has been refunded.")

    def refreshDisplay(self) -> None:
        """
        Refreshes all LCD labels, button states, and metric displays.
        """
        st = self._controller._state
        self._lcd_state.config(text=st.name)

        if st == MachineState.IDLE:
            self._lcd_state.config(fg="#38bdf8")
        elif st == MachineState.DRINK_SELECTED:
            self._lcd_state.config(fg="#facc15")
        elif st == MachineState.PAYMENT_PROCESSING:
            self._lcd_state.config(fg="#fb923c")
        elif st == MachineState.COMPLETED:
            self._lcd_state.config(fg="#4ade80")
        else:
            self._lcd_state.config(fg="#f87171")

        if self._controller._selected_drink:
            self._lcd_drink.config(
                text=f"{self._controller._selected_drink.name} ({self._controller._selected_drink.drink_id})"
            )
        else:
            self._lcd_drink.config(text="None")

        self._lcd_price.config(text=f"{self._controller._list_price}p")
        self._lcd_due.config(text=f"{self._controller._amount_due}p")
        self._lcd_loyalty.config(
            text="10% Applied" if self._controller._loyalty_applied else "No",
            fg="#4ade80" if self._controller._loyalty_applied else "#94a3b8",
        )

        # Timer label
        if self._timer._running and self._timer._start_time:
            elapsed = time.monotonic() - self._timer._start_time
            remaining = max(0, self._timer._timeout_seconds - int(elapsed))
            if self._timer.hasExpired():
                self._lcd_timer.config(text="EXPIRED!", fg="#ef4444")
            else:
                self._lcd_timer.config(text=f"{remaining}s remaining", fg="#a855f7")
        else:
            self._lcd_timer.config(text="STOPPED", fg="#64748b")

        # Status label
        if self._status_label:
            self._status_label.config(
                text=f"State: {st.name} | Amount Due: {self._controller._amount_due}p | Cash in Box: {self._cash_receiver._total}p"
            )

        # Refresh coin stock and audit tables if views exist
        if hasattr(self, "_refresh_stock_view"):
            self._refresh_stock_view()
        if hasattr(self, "_refresh_log_table"):
            self._refresh_log_table()

    # ------------------------------------------------------------------
    # UI Building Helpers
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Header banner
        header = tk.Frame(self.root, bg="#1e293b", padx=16, pady=12)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="🥤 DRINK VENDING MACHINE (VendingGUI)",
            font=("Helvetica", 16, "bold"),
            fg="#f8fafc",
            bg="#1e293b",
        ).pack(side=tk.LEFT)

        tk.Label(
            header,
            text="UML Prototype Test Suite",
            font=("Helvetica", 10),
            fg="#94a3b8",
            bg="#1e293b",
        ).pack(side=tk.LEFT, padx=12, pady=(4, 0))

        # LCD Display Panel
        lcd_frame = tk.Frame(self.root, bg="#0f172a", padx=14, pady=10)
        lcd_frame.pack(fill=tk.X, padx=12, pady=6)

        lcd_grid = tk.Frame(lcd_frame, bg="#0f172a")
        lcd_grid.pack(fill=tk.X)

        def make_metric(parent, label_text, init_value, col):
            f = tk.Frame(parent, bg="#0f172a", padx=8)
            f.grid(row=0, column=col, sticky="w", padx=10)
            tk.Label(f, text=label_text, font=("Helvetica", 9, "bold"), fg="#64748b", bg="#0f172a").pack(anchor="w")
            val = tk.Label(f, text=init_value, font=("Menlo", 13, "bold"), fg="#38bdf8", bg="#0f172a")
            val.pack(anchor="w")
            return val

        self._lcd_state = make_metric(lcd_grid, "MACHINE STATE", "IDLE", 0)
        self._lcd_drink = make_metric(lcd_grid, "SELECTED DRINK", "None", 1)
        self._lcd_price = make_metric(lcd_grid, "LIST PRICE", "0p", 2)
        self._lcd_due = make_metric(lcd_grid, "AMOUNT DUE", "0p", 3)
        self._lcd_loyalty = make_metric(lcd_grid, "LOYALTY DISCOUNT", "No", 4)
        self._lcd_timer = make_metric(lcd_grid, "TRANSACTION TIMER", "STOPPED", 5)

        # Tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        tab_main = ttk.Frame(notebook)
        tab_cash = ttk.Frame(notebook)
        tab_card = ttk.Frame(notebook)
        tab_stock = ttk.Frame(notebook)
        tab_logs = ttk.Frame(notebook)
        tab_future = ttk.Frame(notebook)

        notebook.add(tab_main, text="🛒 Vending Machine Interface")
        notebook.add(tab_cash, text="🪙 Cash & Change Dispenser")
        notebook.add(tab_card, text="💳 Card & Bank Terminal")
        notebook.add(tab_stock, text="📦 Drink Slots & StockSensor")
        notebook.add(tab_logs, text="📜 Transaction Audit Log")
        notebook.add(tab_future, text="🚀 Future Features & Placeholders")

        self._build_tab_main(tab_main)
        self._build_tab_cash(tab_cash)
        self._build_tab_card(tab_card)
        self._build_tab_stock(tab_stock)
        self._build_tab_logs(tab_logs)
        self._build_tab_future(tab_future)

        # Bottom status label (UML statusLabel attribute)
        self._status_label = ttk.Label(
            self.root,
            text="System Initialized — Ready",
            font=("Helvetica", 9, "italic"),
            padding=4,
        )
        self._status_label.pack(fill=tk.X, padx=14)

        # Bottom Live Event Console
        console_frame = ttk.LabelFrame(self.root, text="💻 Live System Component Logs", padding=6)
        console_frame.pack(fill=tk.BOTH, expand=False, padx=12, pady=(2, 8))

        self._log_text = scrolledtext.ScrolledText(
            console_frame,
            height=6,
            bg="#0f172a",
            fg="#e2e8f0",
            insertbackground="white",
            font=("Menlo", 9),
        )
        self._log_text.pack(fill=tk.BOTH, expand=True)

        def write_console(msg: str):
            def _append():
                self._log_text.insert(tk.END, msg)
                self._log_text.see(tk.END)
            self.root.after(0, _append)

        sys.stdout = ConsoleRedirector(sys.stdout, write_console)

    def _build_tab_main(self, parent: ttk.Frame) -> None:
        panes = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left Column: Drink Selection & Loyalty
        left = ttk.LabelFrame(panes, text="1. Select Beverage", padding=10)
        panes.add(left, weight=1)

        drinks_frame = ttk.Frame(left)
        drinks_frame.pack(fill=tk.X, pady=4)

        # Drink buttons specified in Diagram Notes
        self._drink_buttons.clear()
        for drink in self._dispenser._slots:
            btn = ttk.Button(
                drinks_frame,
                text=f"{drink.name} — {drink.price}p (Stock: {drink.stock})",
                command=lambda did=drink.drink_id: self.onDrinkSelected(did),
            )
            btn.pack(fill=tk.X, pady=3)
            self._drink_buttons.append(btn)

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Loyalty scan area
        ttk.Label(left, text="Scan Loyalty Card:").pack(anchor="w")
        card_ent = ttk.Entry(left)
        card_ent.insert(0, "LOYAL-001")
        card_ent.pack(fill=tk.X, pady=3)

        loyalty_btn_row = ttk.Frame(left)
        loyalty_btn_row.pack(fill=tk.X, pady=2)

        ttk.Button(
            loyalty_btn_row,
            text="🏷️ Apply Card ID",
            command=lambda: self.onScanCard(card_ent.get().strip()),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        def open_camera_scanner():
            def on_barcode_found(detected_code: str):
                card_ent.delete(0, tk.END)
                card_ent.insert(0, detected_code)
                self.onScanCard(detected_code)

            scanner = BarcodeCameraScanner()
            scanner.start_scan(parent=self.root, on_detected=on_barcode_found)

        ttk.Button(
            loyalty_btn_row,
            text="📷 Scan Barcode / QR",
            command=open_camera_scanner,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # General Action controls
        ttk.Button(left, text="❌ Cancel Transaction", command=self.onCancel).pack(fill=tk.X, pady=3)
        ttk.Button(
            left,
            text="⏱️ Trigger Timeout",
            command=lambda: (self._controller.onTimeout(), self.refreshDisplay()),
        ).pack(fill=tk.X, pady=3)

        # Right Column: Payment Quick Actions
        right = ttk.LabelFrame(panes, text="2. Quick Payment", padding=10)
        panes.add(right, weight=1)

        # Cash quick buttons
        cash_box = ttk.LabelFrame(right, text="Insert Cash (Coins/Banknotes)", padding=8)
        cash_box.pack(fill=tk.X, pady=4)

        grid = ttk.Frame(cash_box)
        grid.pack(fill=tk.X, pady=4)
        for i, val in enumerate([10, 20, 50, 100, 200]):
            label = f"£{val//100}" if val >= 100 else f"{val}p"
            b = ttk.Button(grid, text=f"+{label}", command=lambda v=val: self.onInsertMoney(v))
            b.grid(row=0, column=i, padx=2, pady=2, sticky="ew")
            grid.columnconfigure(i, weight=1)

        ttk.Button(
            cash_box,
            text="🔄 Return Inserted Money",
            command=lambda: (self._cash_receiver.returnInsertedMoney(), self.refreshDisplay()),
        ).pack(fill=tk.X, pady=3)

        # Card quick action
        card_box = ttk.LabelFrame(right, text="Tap Card", padding=8)
        card_box.pack(fill=tk.X, pady=10)

        card_num_ent = ttk.Entry(card_box)
        card_num_ent.insert(0, "VISA-DEBIT-5522")
        card_num_ent.pack(fill=tk.X, pady=4)

        decline_var = tk.BooleanVar(value=False)

        def toggle_decline():
            self._mock_bank.declineNext = decline_var.get()

        ttk.Checkbutton(
            card_box,
            text="⚠️ Simulate Bank Decline (declineNext)",
            variable=decline_var,
            command=toggle_decline,
        ).pack(anchor="w", pady=2)

        ttk.Button(
            card_box,
            text="💳 Tap & Pay with Card",
            command=lambda: self.onTapCard(card_num_ent.get().strip()),
        ).pack(fill=tk.X, pady=4)

    def _build_tab_cash(self, parent: ttk.Frame) -> None:
        panes = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Validator section
        val_box = ttk.LabelFrame(panes, text="CashValidator Diagnostics", padding=10)
        panes.add(val_box, weight=1)

        ttk.Label(val_box, text="Test Denomination Acceptance:").pack(anchor="w")
        v_ent = ttk.Entry(val_box, width=12)
        v_ent.insert(0, "50")
        v_ent.pack(anchor="w", pady=4)

        v_lbl = ttk.Label(val_box, text="Status: Ready", font=("Menlo", 10))
        v_lbl.pack(anchor="w", pady=4)

        def check_denom():
            try:
                amt = int(v_ent.get().strip())
                ok = self._cash_receiver._validator.validate(amt)
                if ok:
                    v_lbl.config(text=f"✅ {amt}p accepted", foreground="green")
                else:
                    v_lbl.config(text=f"❌ {amt}p rejected", foreground="red")
            except ValueError:
                v_lbl.config(text="Error: Enter integer", foreground="red")

        ttk.Button(val_box, text="Validate Denomination", command=check_denom).pack(anchor="w", pady=2)

        # Change dispenser stock section
        disp_box = ttk.LabelFrame(panes, text="ChangeDispenser Coin Stock", padding=10)
        panes.add(disp_box, weight=1)

        self._stock_tree = ttk.Treeview(
            disp_box,
            columns=("denomination", "quantity", "subtotal"),
            show="headings",
            height=8,
        )
        self._stock_tree.heading("denomination", text="Denomination")
        self._stock_tree.heading("quantity", text="Quantity in Machine")
        self._stock_tree.heading("subtotal", text="Subtotal")
        self._stock_tree.column("denomination", width=100, anchor="center")
        self._stock_tree.column("quantity", width=120, anchor="center")
        self._stock_tree.column("subtotal", width=100, anchor="center")
        self._stock_tree.pack(fill=tk.X, pady=4)

        def refresh_stock_table():
            self._stock_tree.delete(*self._stock_tree.get_children())
            total = 0
            for d, q in sorted(self._cash_receiver._dispenser._coin_stock.items(), reverse=True):
                sub = d * q
                total += sub
                name = f"£{d//100}" if d >= 100 else f"{d}p"
                self._stock_tree.insert("", tk.END, values=(name, q, f"{sub}p"))

        self._refresh_stock_view = refresh_stock_table
        refresh_stock_table()

    def _build_tab_card(self, parent: ttk.Frame) -> None:
        panes = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        left = ttk.LabelFrame(panes, text="CardReader Terminal", padding=10)
        panes.add(left, weight=1)

        ttk.Label(left, text="Card Buffer:").pack(anchor="w")
        c_ent = ttk.Entry(left, width=28)
        c_ent.insert(0, "4111-2222-3333-4444")
        c_ent.pack(anchor="w", pady=4)

        c_lbl = ttk.Label(left, text="Card in Reader: None", font=("Menlo", 10))
        c_lbl.pack(anchor="w", pady=4)

        def read_c():
            cid = c_ent.get().strip()
            self._card_reader.readCard(cid)
            c_lbl.config(text=f"Card in Reader: '{self._card_reader._card_id}'")

        def cancel_c():
            self._card_reader.cancel()
            c_lbl.config(text="Card in Reader: None (Cleared)")

        ttk.Button(left, text="Read / Insert Card", command=read_c).pack(anchor="w", pady=2)
        ttk.Button(left, text="Cancel / Eject Card", command=cancel_c).pack(anchor="w", pady=2)

        right = ttk.LabelFrame(panes, text="BankService Interface", padding=10)
        panes.add(right, weight=1)

        ttk.Label(right, text="Direct validatePayment(amount) Test:").pack(anchor="w")
        amt_ent = ttk.Entry(right, width=12)
        amt_ent.insert(0, "200")
        amt_ent.pack(anchor="w", pady=4)

        def test_bank_val():
            try:
                amt = int(amt_ent.get().strip())
                ok = self._mock_bank.validatePayment(amt)
                if ok:
                    messagebox.showinfo("Bank Service", f"✅ Bank validated and approved {amt}p.")
                else:
                    messagebox.showerror("Bank Service", f"❌ Bank declined payment of {amt}p.")
            except ValueError:
                pass

        ttk.Button(right, text="Call validatePayment()", command=test_bank_val).pack(anchor="w", pady=2)

    def _build_tab_stock(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="StockSensor & DrinkDispenser Diagnostics", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tree = ttk.Treeview(
            frame,
            columns=("code", "name", "price", "stock", "sensor_status"),
            show="headings",
            height=6,
        )
        tree.heading("code", text="Drink Code")
        tree.heading("name", text="Name")
        tree.heading("price", text="Price")
        tree.heading("stock", text="Stock Count")
        tree.heading("sensor_status", text="StockSensor Status")
        tree.pack(fill=tk.BOTH, expand=True, pady=4)

        def refresh_dispenser_view():
            tree.delete(*tree.get_children())
            for d in self._dispenser._slots:
                is_ok = self._stock_sensor.checkStock(d.drink_id)
                st_text = "✅ OK" if is_ok else ("❌ OUT" if d.stock == 0 else "⚠️ LOW")
                tree.insert(
                    "",
                    tk.END,
                    values=(d.drink_id, d.name, f"{d.price}p", f"{d.stock} cans", st_text),
                )

        ttk.Button(frame, text="🔄 Refresh Stock Levels (StockSensor.refresh())", command=refresh_dispenser_view).pack(
            anchor="w", pady=4
        )
        refresh_dispenser_view()

    def _build_tab_logs(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Audit Trail History (Logger & TransactionRecord)", padding=10)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        log_tree = ttk.Treeview(
            frame,
            columns=("timestamp", "drink", "amount", "status"),
            show="headings",
            height=10,
        )
        log_tree.heading("timestamp", text="Timestamp")
        log_tree.heading("drink", text="Drink Name")
        log_tree.heading("amount", text="Amount Paid")
        log_tree.heading("status", text="Outcome Status")
        log_tree.column("timestamp", width=180, anchor="center")
        log_tree.column("drink", width=180, anchor="center")
        log_tree.column("amount", width=120, anchor="center")
        log_tree.column("status", width=140, anchor="center")
        log_tree.pack(fill=tk.BOTH, expand=True, pady=4)

        def refresh_logs():
            log_tree.delete(*log_tree.get_children())
            for r in self._logger.getHistory():
                ts = r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                log_tree.insert("", tk.END, values=(ts, r.drinkName, f"{r.amountPaid}p", r.status))

        self._refresh_log_table = refresh_logs
        ttk.Button(frame, text="🔄 Refresh Log History", command=refresh_logs).pack(anchor="w", pady=2)
        refresh_logs()

    def _build_tab_future(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Extensibility & Future Component Placeholders", padding=12)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        ttk.Label(
            frame,
            text=(
                "🚀 Reserved Placeholders for Upcoming Hardware Integration:\n\n"
                "1. Dispenser Chute Sensor: verifies drink physical fall into user cup tray.\n"
                "2. IoT Telemetry: remote reporting of coin levels and daily profit metrics.\n"
                "3. Temperature Sensor: chiller thermostat monitoring for ice-cold beverages."
            ),
            font=("Helvetica", 10),
        ).pack(anchor="w", pady=6)

    def _schedule_tick(self) -> None:
        self.refreshDisplay()
        self.root.after(500, self._schedule_tick)


# ===========================================================================
# Interactive Terminal / CLI Mode Fallback
# ===========================================================================

def run_cli():
    print("=" * 65)
    print("🥤 Vending Machine Simulator — CLI Test Suite")
    print("=" * 65)

    system_bundle = build_vending_system()
    controller, dispenser, stock_sensor, loyalty_scanner, payment_module, cash_receiver, card_reader, mock_bank, logger, timer = system_bundle

    while True:
        st = controller._state.name
        drink = controller._selected_drink.name if controller._selected_drink else "None"
        due = controller._amount_due
        print(f"\n[Status] State: {st} | Selected: {drink} | Due: {due}p | Loyalty: {controller._loyalty_applied}")
        print("Commands:")
        print("  1) Select Espresso (150p)     6) Pay with Card (Mock Bank)")
        print("  2) Select Latte (220p)        7) Toggle Bank Decline Flag")
        print("  3) Select Hot Chocolate (200p)8) Cancel Transaction")
        print("  4) Select Water (100p)        9) Trigger Timeout")
        print("  5) Scan Loyalty Card         10) View Audit Logs (Logger)")
        print("  11) Insert Cash              12) Exit")

        choice = input("\nEnter choice (1-12): ").strip()
        if choice == "1":
            controller.selectDrink("ESPRESSO")
        elif choice == "2":
            controller.selectDrink("LATTE")
        elif choice == "3":
            controller.selectDrink("HOT_CHOCOLATE")
        elif choice == "4":
            controller.selectDrink("WATER")
        elif choice == "5":
            cid = input("Card ID [LOYAL-001]: ").strip() or "LOYAL-001"
            controller.scanLoyalty(cid)
        elif choice == "6":
            cid = input("Card Number [VISA-1122]: ").strip() or "VISA-1122"
            card_reader.readCard(cid)
            controller.startPayment(card_reader)
            res = card_reader.processPayment(controller._amount_due)
            if res == PaymentResult.SUCCESS:
                controller.onPaymentComplete()
            else:
                controller.onPaymentFailed("declined")
        elif choice == "7":
            mock_bank.declineNext = not mock_bank.declineNext
            print(f"Bank declineNext is now: {mock_bank.declineNext}")
        elif choice == "8":
            controller.cancel()
        elif choice == "9":
            controller.onTimeout()
        elif choice == "10":
            print("\n--- Audit Log History ---")
            for r in logger.getHistory():
                print(r.toString())
        elif choice == "11":
            amt_str = input("Enter coin/note pence [e.g. 50]: ").strip() or "50"
            try:
                pence = int(amt_str)
                if controller._state == MachineState.DRINK_SELECTED:
                    controller.startPayment(cash_receiver)
                cash_receiver.insertItem(pence)
                if cash_receiver._state == CashReceiverState.PAYMENT_COMPLETE:
                    controller.onPaymentComplete()
                    cash_receiver._state = CashReceiverState.IDLE
            except ValueError:
                print("Invalid integer.")
        elif choice == "12":
            print("Exiting...")
            break


# ===========================================================================
# Main Entry Point
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(description="Vending Machine GUI & Simulator")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    args = parser.parse_args()

    if args.cli:
        run_cli()
    else:
        try:
            root = tk.Tk()
            root.title("🥤 Drink Vending Machine Program (VendingGUI)")
            root.geometry("1020x840")
            root.minsize(920, 720)

            system_bundle = build_vending_system()
            controller = system_bundle[0]
            VendingGUI(root, controller, system_bundle)
            root.mainloop()
        except Exception as e:
            print(f"[Warning] GUI launch encountered an issue ({e}). Launching CLI mode instead...")
            run_cli()


if __name__ == "__main__":
    main()

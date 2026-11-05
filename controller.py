import os
import json
from datetime import datetime
from enum import Enum, auto
from typing import Optional, List, Dict, Any

from payment import PaymentMethod, PaymentModule
from inventory import Drink, DrinkDispenser, LoyaltyAccount, LoyaltyScanner, StockSensor
from logger import Logger, TransactionRecord
from timer import TransactionTimer


# ===========================================================================
# Database File Paths & Constants
# ===========================================================================

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
MEMBERS_FILE = os.path.join(DATA_DIR, "members.json")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "transactions.json")
ACTIVITY_LOG_FILE = os.path.join(DATA_DIR, "activity_log.json")


def _ensure_data_dir() -> None:
    """Ensure data directory exists before read/write operations."""
    os.makedirs(DATA_DIR, exist_ok=True)


# ===========================================================================
# Database Load & Save Functions
# ===========================================================================

# 1. Product Database Functions (ข้อมูลสินค้าที่ขาย)
def load_products(file_path: str = PRODUCTS_FILE) -> List[Drink]:
    """
    Load drink catalogue and stock levels from the products JSON database.

    :param file_path: Path to products JSON file.
    :return: List of Drink objects.
    """
    _ensure_data_dir()
    if not os.path.exists(file_path):
        print(f"[Database] Products file not found at {file_path}, returning empty list.")
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            drinks = [
                Drink(
                    drink_id=item["drink_id"],
                    name=item["name"],
                    price=item["price"],
                    stock=item.get("stock", 10),
                )
                for item in data
            ]
            print(f"[Database] Loaded {len(drinks)} products from {os.path.basename(file_path)}.")
            return drinks
    except Exception as e:
        print(f"[Database] Error loading products: {e}")
        return []


def save_products(drinks: List[Drink], file_path: str = PRODUCTS_FILE) -> None:
    """
    Save drink catalogue and stock levels to the products JSON database.

    :param drinks: List of Drink objects to persist.
    :param file_path: Destination JSON file path.
    """
    _ensure_data_dir()
    try:
        data = [
            {
                "drink_id": d.drink_id,
                "name": d.name,
                "price": d.price,
                "stock": d.stock,
            }
            for d in drinks
        ]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[Database] Saved {len(drinks)} products to {os.path.basename(file_path)}.")
    except Exception as e:
        print(f"[Database] Error saving products: {e}")


# 2. Member Database Functions (ข้อมูลสมาชิก)
def load_members(file_path: str = MEMBERS_FILE) -> List[LoyaltyAccount]:
    """
    Load loyalty membership accounts from the members JSON database.

    :param file_path: Path to members JSON file.
    :return: List of LoyaltyAccount objects.
    """
    _ensure_data_dir()
    if not os.path.exists(file_path):
        print(f"[Database] Members file not found at {file_path}, returning empty list.")
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            accounts = [
                LoyaltyAccount(
                    card_id=item["card_id"],
                    member_name=item["member_name"],
                    active=item.get("active", True),
                )
                for item in data
            ]
            print(f"[Database] Loaded {len(accounts)} members from {os.path.basename(file_path)}.")
            return accounts
    except Exception as e:
        print(f"[Database] Error loading members: {e}")
        return []


def save_members(accounts: List[LoyaltyAccount], file_path: str = MEMBERS_FILE) -> None:
    """
    Save loyalty membership accounts to the members JSON database.

    :param accounts: List of LoyaltyAccount objects to persist.
    :param file_path: Destination JSON file path.
    """
    _ensure_data_dir()
    try:
        data = [
            {
                "card_id": a.card_id,
                "member_name": a.member_name,
                "active": a.active,
            }
            for a in accounts
        ]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[Database] Saved {len(accounts)} members to {os.path.basename(file_path)}.")
    except Exception as e:
        print(f"[Database] Error saving members: {e}")


# 3. Transaction Database Functions (ข้อมูล Transaction)
def load_transactions(file_path: str = TRANSACTIONS_FILE) -> List[TransactionRecord]:
    """
    Load transaction history records from the transactions JSON database.

    :param file_path: Path to transactions JSON file.
    :return: List of TransactionRecord objects.
    """
    _ensure_data_dir()
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            records = []
            for item in data:
                ts_str = item.get("timestamp")
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S") if ts_str else datetime.now()
                records.append(
                    TransactionRecord(
                        drinkName=item.get("drink_name", item.get("drinkName", "")),
                        amountPaid=item.get("amount_paid", item.get("amountPaid", 0)),
                        status=item.get("status", ""),
                        timestamp=ts,
                    )
                )
            print(f"[Database] Loaded {len(records)} transaction records from {os.path.basename(file_path)}.")
            return records
    except Exception as e:
        print(f"[Database] Error loading transactions: {e}")
        return []


def save_transactions(records: List[TransactionRecord], file_path: str = TRANSACTIONS_FILE) -> None:
    """
    Save transaction history records to the transactions JSON database.

    :param records: List of TransactionRecord objects to persist.
    :param file_path: Destination JSON file path.
    """
    _ensure_data_dir()
    try:
        data = [
            {
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "drink_name": r.drinkName,
                "amount_paid": r.amountPaid,
                "status": r.status,
            }
            for r in records
        ]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[Database] Saved {len(records)} transactions to {os.path.basename(file_path)}.")
    except Exception as e:
        print(f"[Database] Error saving transactions: {e}")


# 4. Activity Log Database Functions (ข้อมูล Activity Log)
def load_activity_logs(file_path: str = ACTIVITY_LOG_FILE) -> List[Dict[str, Any]]:
    """
    Load system activity logs from the activity log JSON database.

    :param file_path: Path to activity log JSON file.
    :return: List of log dictionaries.
    """
    _ensure_data_dir()
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
            print(f"[Database] Loaded {len(logs)} activity logs from {os.path.basename(file_path)}.")
            return logs
    except Exception as e:
        print(f"[Database] Error loading activity logs: {e}")
        return []


def save_activity_logs(logs: List[Dict[str, Any]], file_path: str = ACTIVITY_LOG_FILE) -> None:
    """
    Save system activity logs to the activity log JSON database.

    :param logs: List of log dictionaries.
    :param file_path: Destination JSON file path.
    """
    _ensure_data_dir()
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        print(f"[Database] Saved {len(logs)} activity logs to {os.path.basename(file_path)}.")
    except Exception as e:
        print(f"[Database] Error saving activity logs: {e}")


def log_activity(event: str, details: str = "", file_path: str = ACTIVITY_LOG_FILE) -> None:
    """
    Append a single activity event entry to the activity log JSON database.

    :param event: Event name (e.g. 'DRINK_SELECTED', 'SALE_COMPLETED').
    :param details: Descriptive details or metadata.
    :param file_path: Destination JSON file path.
    """
    _ensure_data_dir()
    logs = load_activity_logs(file_path)
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "details": details,
    }
    logs.append(entry)
    save_activity_logs(logs, file_path)


# Combined Helpers
def load_all_databases() -> tuple[List[Drink], List[LoyaltyAccount], List[TransactionRecord], List[Dict[str, Any]]]:
    """Load all four database entities simultaneously."""
    return (
        load_products(),
        load_members(),
        load_transactions(),
        load_activity_logs(),
    )


def save_all_databases(
    drinks: Optional[List[Drink]] = None,
    members: Optional[List[LoyaltyAccount]] = None,
    transactions: Optional[List[TransactionRecord]] = None,
    activity_logs: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Save all four database entities simultaneously if provided."""
    if drinks is not None:
        save_products(drinks)
    if members is not None:
        save_members(members)
    if transactions is not None:
        save_transactions(transactions)
    if activity_logs is not None:
        save_activity_logs(activity_logs)


# ===========================================================================
# Machine State Enum
# ===========================================================================

class MachineState(Enum):
    IDLE = auto()
    DRINK_SELECTED = auto()
    AWAITING_PAYMENT = auto()
    PAYMENT_PROCESSING = auto()
    COMPLETED = auto()
    CANCELLED = auto()


# ===========================================================================
# VendingController
# ===========================================================================

class VendingController:
    """
    Controls the vending machine workflow including drink selection,
    loyalty card scanning, payment processing, dispensing, and sale completion.
    Coordinates DrinkDispenser, LoyaltyScanner, PaymentModule, Logger,
    TransactionTimer, and StockSensor as defined in the UML Class Diagram.
    Integrates with JSON database files for automated persistence.
    """

    def __init__(
        self,
        dispenser: Optional[DrinkDispenser] = None,
        loyalty_scanner: Optional[LoyaltyScanner] = None,
        payment_module: Optional[PaymentModule] = None,
        logger: Optional[Logger] = None,
        timer: Optional[TransactionTimer] = None,
        stock_sensor: Optional[StockSensor] = None,
    ):
        # UML Attributes
        self._state: MachineState = MachineState.IDLE
        self._selected_drink: Optional[Drink] = None
        self._list_price: int = 0
        self._amount_due: int = 0
        self._loyalty_applied: bool = False

        # UML Associations (1:1 with controller)
        self._dispenser: Optional[DrinkDispenser] = dispenser
        self._loyalty_scanner: Optional[LoyaltyScanner] = loyalty_scanner
        self._payment_module: Optional[PaymentModule] = payment_module
        self._logger: Optional[Logger] = logger
        self._timer: Optional[TransactionTimer] = timer
        self._stock_sensor: Optional[StockSensor] = stock_sensor

        # Record system initialization to activity log
        log_activity("SYSTEM_INIT", "VendingController initialized.")

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def selectDrink(self, drinkId: str) -> bool:
        """
        Select a drink by its ID through DrinkDispenser.

        :param drinkId: The unique identifier of the drink to select.
        :return: True if the drink was successfully selected, False otherwise.
        """
        if self._state != MachineState.IDLE:
            print(f"[selectDrink] Cannot select drink in state: {self._state.name}")
            return False

        if self._dispenser is None:
            print("[selectDrink] Error: No DrinkDispenser configured.")
            return False

        drink = self._dispenser.getDrink(drinkId)
        if drink is None:
            print(f"[selectDrink] Drink '{drinkId}' not found.")
            return False

        if not self._dispenser.isAvailable(drinkId):
            print(f"[selectDrink] Drink '{drink.name}' is currently out of stock.")
            return False

        self._selected_drink = drink
        self._list_price = drink.getPrice()
        self._amount_due = drink.getPrice()
        self._loyalty_applied = False
        self._state = MachineState.DRINK_SELECTED

        print(f"[selectDrink] Selected '{drink.name}' — price: {self._list_price}p")

        # Start transaction timer
        if self._timer is not None:
            self._timer.start()

        # Log activity
        log_activity("DRINK_SELECTED", f"Selected {drink.name} ({self._list_price}p)")

        return True

    def scanLoyalty(self, cardId: str) -> bool:
        """
        Scan a loyalty card via LoyaltyScanner to apply a discount.

        :param cardId: The loyalty card identifier.
        :return: True if the loyalty card was accepted and discount applied,
                 False otherwise.
        """
        if self._state != MachineState.DRINK_SELECTED:
            print(f"[scanLoyalty] Cannot scan loyalty card in state: {self._state.name}")
            return False

        if self._loyalty_applied:
            print("[scanLoyalty] Loyalty discount already applied.")
            return False

        if self._loyalty_scanner is None:
            print("[scanLoyalty] No LoyaltyScanner configured.")
            return False

        card_valid = self._loyalty_scanner.scan(cardId)
        if not card_valid:
            print(f"[scanLoyalty] Loyalty card '{cardId}' is invalid or inactive.")
            log_activity("LOYALTY_REJECTED", f"Card ID '{cardId}' rejected or inactive.")
            return False

        self._loyalty_applied = True
        self._amount_due = self._applyDiscount()

        print(f"[scanLoyalty] Loyalty discount applied — amount due: {self._amount_due}p")
        log_activity("LOYALTY_APPLIED", f"Card '{cardId}' applied. New amount due: {self._amount_due}p")
        return True

    def startPayment(self, method: PaymentMethod) -> None:
        """
        Initiate the payment process using the specified payment method.

        :param method: The PaymentMethod to use (CashReceiver, CardReader, etc.).
        """
        if self._state != MachineState.DRINK_SELECTED:
            print(f"[startPayment] Cannot start payment in state: {self._state.name}")
            return

        self._state = MachineState.PAYMENT_PROCESSING
        method_name = type(method).__name__
        print(
            f"[startPayment] Payment started via {method_name} "
            f"for {self._amount_due}p"
        )

        if self._payment_module is not None:
            self._payment_module._active = method

        log_activity("PAYMENT_STARTED", f"Method: {method_name}, Amount due: {self._amount_due}p")

    def onPaymentComplete(self) -> None:
        """
        Callback invoked when payment confirms a successful transaction.
        """
        if self._state != MachineState.PAYMENT_PROCESSING:
            print(f"[onPaymentComplete] Unexpected call in state: {self._state.name}")
            return

        print("[onPaymentComplete] Payment confirmed — completing sale.")
        self._completeSale()

    def onPaymentFailed(self, reason: str) -> None:
        """
        Callback invoked when payment reports a failure.

        :param reason: Human-readable description of why payment failed.
        """
        if self._state != MachineState.PAYMENT_PROCESSING:
            print(f"[onPaymentFailed] Unexpected call in state: {self._state.name}")
            return

        print(f"[onPaymentFailed] Payment failed — reason: {reason}")
        self._abortSale(reason)

    def onTimeout(self) -> None:
        """
        Callback invoked when a user interaction or payment step times out.
        """
        print(f"[onTimeout] Timeout occurred in state: {self._state.name}")
        log_activity("TIMEOUT", f"Transaction timed out in state {self._state.name}")
        self._abortSale("timeout")

    def cancel(self) -> None:
        """
        Cancel the current transaction at any point before completion.
        """
        if self._state in (MachineState.IDLE, MachineState.COMPLETED, MachineState.CANCELLED):
            print(f"[cancel] Nothing to cancel in state: {self._state.name}")
            return

        print("[cancel] Transaction cancelled by user.")
        log_activity("USER_CANCELLED", f"User cancelled transaction in state {self._state.name}")
        self._abortSale("user cancelled")

    # ------------------------------------------------------------------
    # Private methods (UML specified)
    # ------------------------------------------------------------------

    def _applyDiscount(self) -> int:
        """
        Calculate the discounted amount due using LoyaltyScanner discount rate.

        :return: The new amount due (int, in pence).
        """
        rate = self._loyalty_scanner.getDiscountRate() if self._loyalty_scanner else 0.10
        discount = int(self._list_price * rate)
        discounted_price = self._list_price - discount
        pct = int(rate * 100)
        print(f"[_applyDiscount] {pct}% discount applied: {self._list_price}p → {discounted_price}p")
        return discounted_price

    def _completeSale(self) -> None:
        """
        Finalise the sale: dispense the drink, stop timer, record log, and reset.
        Persists updated stock to products.json and transaction to transactions.json.
        """
        drink_name = self._selected_drink.name if self._selected_drink else "Unknown"
        drink_id = self._selected_drink.drink_id if self._selected_drink else ""
        amount_paid = self._amount_due

        # 1. Physically dispense drink via DrinkDispenser (reduces stock)
        if self._dispenser is not None and drink_id:
            self._dispenser.dispense(drink_id)
            # Auto-save updated stock levels to products database
            save_products(self._dispenser._slots)

        # 2. Stop transaction timer
        if self._timer is not None:
            self._timer.stop()

        # 3. Record transaction in Logger & auto-save to transactions database
        if self._logger is not None:
            self._logger.recordTransaction(
                status="SUCCESS",
                amount=amount_paid,
                drink_name=drink_name,
            )
            save_transactions(self._logger.getHistory())

        # 4. Record activity log
        log_activity("SALE_COMPLETED", f"Dispensed {drink_name} for {amount_paid}p")

        print(f"[_completeSale] Dispensing '{drink_name}'. Sale complete.")
        self._state = MachineState.COMPLETED
        self._reset()

    def _abortSale(self, reason: str) -> None:
        """
        Abort the current sale, cancel active payment, stop timer, record log, and reset.
        Persists failed/cancelled transaction to transactions.json.

        :param reason: The reason for aborting.
        """
        drink_name = self._selected_drink.name if self._selected_drink else "None"
        amount = self._amount_due

        print(f"[_abortSale] Sale aborted — reason: {reason}")

        # 1. Stop transaction timer
        if self._timer is not None:
            self._timer.stop()

        # 2. Cancel active payment method (triggers cash return / card void)
        if self._payment_module is not None:
            self._payment_module.cancelPayment()

        # 3. Record transaction in Logger & auto-save to transactions database
        if self._logger is not None:
            self._logger.recordTransaction(
                status=reason.upper(),
                amount=amount,
                drink_name=drink_name,
            )
            save_transactions(self._logger.getHistory())

        # 4. Record activity log
        log_activity("SALE_ABORTED", f"Reason: {reason}, Drink: {drink_name}, Amount: {amount}p")

        self._state = MachineState.CANCELLED
        self._reset()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reset(self) -> None:
        """Reset transient state ready for the next customer."""
        self._selected_drink = None
        self._list_price = 0
        self._amount_due = 0
        self._loyalty_applied = False
        self._state = MachineState.IDLE

    # ------------------------------------------------------------------
    # Properties (read-only UML attributes)
    # ------------------------------------------------------------------

    @property
    def state(self) -> MachineState:
        return self._state

    @property
    def selectedDrink(self) -> Optional[Drink]:
        return self._selected_drink

    @property
    def listPrice(self) -> int:
        return self._list_price

    @property
    def amountDue(self) -> int:
        return self._amount_due

    @property
    def loyaltyApplied(self) -> bool:
        return self._loyalty_applied

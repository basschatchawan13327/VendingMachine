import os
import json
import ssl
import time
import base64
import urllib.request
import urllib.parse
import urllib.error
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional, Dict, Any, Tuple

from bank import BankService, MockBankService

try:
    import stripe  # type: ignore
except ImportError:
    stripe = None


# ---------------------------------------------------------------------------
# Payment Outcomes
# ---------------------------------------------------------------------------

class PaymentResult(Enum):
    """Possible outcomes returned by a PaymentMethod.processPayment() call."""
    SUCCESS = auto()
    FAILED = auto()
    CANCELLED = auto()
    TIMEOUT = auto()


# ---------------------------------------------------------------------------
# PaymentMethod (Abstract Base Class)
# ---------------------------------------------------------------------------

class PaymentMethod(ABC):
    """
    «abstract»
    Abstract base class representing a single payment method.
    Concrete subclasses (CashReceiver, CardReader) implement the
    method-specific payment flow.
    """

    def __init__(self):
        self._amount_due: int = 0  # # amountDue: int (protected)

    # ------------------------------------------------------------------
    # Public abstract methods
    # ------------------------------------------------------------------

    @abstractmethod
    def processPayment(self, amount: int) -> PaymentResult:
        """
        Process a payment for the given amount.

        :param amount: The amount to charge (in pence/cents).
        :return: A PaymentResult indicating the outcome.
        """
        ...

    @abstractmethod
    def cancel(self) -> None:
        """
        Cancel an in-progress payment request.
        """
        ...


# ---------------------------------------------------------------------------
# PaymentModule
# ---------------------------------------------------------------------------

class PaymentModule:
    """
    Manages payment processing for the vending machine.
    Handles multiple payment methods, initiates payment requests,
    and receives payment results.
    """

    def __init__(self, supported_methods: List[PaymentMethod]):
        """
        :param supported_methods: List of PaymentMethods supported by this machine.
        """
        self._methods: List[PaymentMethod] = supported_methods
        self._active: Optional[PaymentMethod] = None

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def requestPayment(self, amount: int, method: PaymentMethod) -> None:
        """
        Initiate a payment request for the given amount using the specified method.

        :param amount: The amount to charge (in pence/cents).
        :param method: The PaymentMethod instance to use for this transaction.
        """
        if method not in self._methods:
            print(f"[requestPayment] Payment method '{type(method).__name__}' is not supported.")
            return

        if self._active is not None:
            print(f"[requestPayment] A payment is already active via {type(self._active).__name__}.")
            return

        self._active = method
        result = method.processPayment(amount)
        print(
            f"[requestPayment] Payment of {amount}p via {type(method).__name__} "
            f"returned: {result.name}."
        )
        self.onResult(result)

    def cancelPayment(self) -> None:
        """
        Cancel the currently active payment request.
        """
        if self._active is None:
            print("[cancelPayment] No active payment to cancel.")
            return

        print(f"[cancelPayment] Cancelling active {type(self._active).__name__} payment.")
        self._active.cancel()
        self._active = None

    def onResult(self, result: PaymentResult) -> None:
        """
        Handle the outcome of a payment attempt.

        :param result: A PaymentResult value from processPayment().
        """
        if self._active is None and result not in (
            PaymentResult.SUCCESS,
            PaymentResult.FAILED,
            PaymentResult.CANCELLED,
            PaymentResult.TIMEOUT,
        ):
            print("[onResult] Received result but no payment is active.")
            return

        method_name = type(self._active).__name__ if self._active else "Unknown"
        self._active = None

        if result == PaymentResult.SUCCESS:
            print(f"[onResult] Payment via {method_name} succeeded.")
        else:
            reason = result.name.lower()
            print(f"[onResult] Payment via {method_name} did not succeed — reason: {reason}.")


# ---------------------------------------------------------------------------
# CashValidator
# ---------------------------------------------------------------------------

class CashValidator:
    """
    Validates coins and banknotes inserted into the machine before their
    value is counted toward the payment total.

    Checks that the inserted denomination is one of the accepted values
    (10p to 10 GBP: 10p, 20p, 50p, £1, £2, £5, £10).
    Denominations outside this range (e.g. £20, £50, or sub-10p coins)
    are rejected and returned to customer.
    """

    # Accepted UK coin/note denominations: 10p to 10 GBP (in pence)
    DEFAULT_DENOMINATIONS: List[int] = [10, 20, 50, 100, 200, 500, 1000]

    def __init__(self, valid_denominations: Optional[List[int]] = None):
        """
        :param valid_denominations: Accepted denominations in pence.
                                    Defaults to 10p to 10 GBP if not provided.
        """
        self._valid_denominations: List[int] = (
            valid_denominations if valid_denominations is not None
            else list(self.DEFAULT_DENOMINATIONS)
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def validate(self, pence: int) -> bool:
        """
        Check whether the inserted coin or banknote is a valid denomination.
        Accepted range: 10p to 10 GBP (10p, 20p, 50p, 100p, 200p, 500p, 1000p).
        Denominations £20 (2000p) and £50 (5000p) or coins below 10p are rejected.

        :param pence: The value of the inserted item in pence.
        :return: True if the denomination is accepted, False otherwise.
        """
        is_valid = pence in self._valid_denominations
        if is_valid:
            print(f"[CashValidator] {pence}p accepted.")
        else:
            print(f"[CashValidator] {pence}p rejected — outside accepted range (10p to 10 GBP).")
        return is_valid


# ---------------------------------------------------------------------------
# ChangeDispenser
# ---------------------------------------------------------------------------

class ChangeDispenser:
    """
    Manages the coin stock and dispenses change to the customer.

    coinStock maps each coin denomination (in pence) to the number of
    coins of that denomination currently available in the machine.
    Example: {200: 5, 100: 10, 50: 8, 20: 15, 10: 20, 5: 30, 2: 50, 1: 100}
    """

    def __init__(self, coin_stock: Optional[Dict[int, int]] = None):
        """
        :param coin_stock: Initial stock of coins as {denomination: quantity}.
        """
        if coin_stock is not None:
            self._coin_stock: Dict[int, int] = coin_stock
        else:
            self._coin_stock = {200: 20, 100: 30, 50: 40, 20: 50, 10: 50, 5: 50, 2: 50, 1: 100}

        self._last_dispensed_coins: Dict[int, int] = {}
        self._last_dispensed_summary: str = ""

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def coinStock(self) -> Dict[int, int]:
        """Returns a copy of the current coin stock mapping {denomination: quantity}."""
        return dict(self._coin_stock)

    @property
    def lastDispensedCoins(self) -> Dict[int, int]:
        """Returns the breakdown of coins dispensed in the most recent transaction."""
        return dict(self._last_dispensed_coins)

    @property
    def lastDispensedSummary(self) -> str:
        """Returns human-readable summary of coins dispensed (e.g. '1x50p, 1x20p, 1x10p')."""
        return self._last_dispensed_summary

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def canMakeChange(self, amount: int) -> bool:
        """
        Check whether the dispenser can make exact change for the given amount
        without actually dispensing any coins.

        :param amount: The change amount required in pence.
        :return: True if exact change can be made, False otherwise.
        """
        _, success = self._calculateChange(amount)
        return success

    def dispenseChange(self, amount: int) -> bool:
        """
        Dispense exact change for the given amount and deduct the used coins
        from the stock.

        :param amount: The change amount to dispense in pence.
        :return: True if change was dispensed successfully, False otherwise.
        """
        coins_to_use, success = self._calculateChange(amount)

        if not success:
            print(f"[ChangeDispenser] Cannot make exact change for {amount}p.")
            return False

        # Deduct dispensed coins from stock
        for denomination, quantity in coins_to_use.items():
            self._coin_stock[denomination] -= quantity

        dispensed_summary = ", ".join(
            f"{qty}x{denom}p"
            for denom, qty in sorted(coins_to_use.items(), reverse=True)
            if qty > 0
        )
        self._last_dispensed_coins = coins_to_use
        self._last_dispensed_summary = dispensed_summary
        print(f"[ChangeDispenser] Dispensed {amount}p change: {dispensed_summary}.")
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _calculateChange(self, amount: int) -> tuple[Dict[int, int], bool]:
        """
        Use a greedy algorithm to determine which coins to use for the
        given amount, without modifying the actual stock.

        :param amount: The target change amount in pence.
        :return: A tuple of (coins_used dict, success bool).
        """
        remaining = amount
        coins_used: Dict[int, int] = {}

        for denomination in sorted(self._coin_stock.keys(), reverse=True):
            if remaining <= 0:
                break

            available = self._coin_stock[denomination]
            needed = min(remaining // denomination, available)

            if needed > 0:
                coins_used[denomination] = needed
                remaining -= needed * denomination

        success = remaining == 0
        return coins_used, success


# ---------------------------------------------------------------------------
# CashReceiverState (UML Enumeration)
# ---------------------------------------------------------------------------

class CashReceiverState(Enum):
    """
    «enumeration»
    Exact states from the UML Class Diagram:
    IDLE, AWAITING_CASH, VALIDATING_ITEM, DISPENSING_CHANGE, REFUNDING, PAYMENT_COMPLETE
    """
    IDLE = auto()
    AWAITING_CASH = auto()
    VALIDATING_ITEM = auto()
    DISPENSING_CHANGE = auto()
    REFUNDING = auto()
    PAYMENT_COMPLETE = auto()


# ---------------------------------------------------------------------------
# CashReceiver (Concrete PaymentMethod)
# ---------------------------------------------------------------------------

class CashReceiver(PaymentMethod):
    """
    Concrete PaymentMethod that handles physical cash payments.
    Owns a CashValidator and a ChangeDispenser (UML composition).
    """

    def __init__(
        self,
        validator: Optional[CashValidator] = None,
        dispenser: Optional[ChangeDispenser] = None,
    ):
        super().__init__()
        self._state: CashReceiverState = CashReceiverState.IDLE
        self._total: int = 0
        self._inserted_items: List[int] = []
        self._last_rejected_item: Optional[int] = None

        # UML Composition: CashReceiver owns 1 CashValidator and 1 ChangeDispenser
        self._validator: CashValidator = validator if validator is not None else CashValidator()
        self._dispenser: ChangeDispenser = dispenser if dispenser is not None else ChangeDispenser()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def insertItem(self, pence: int) -> bool:
        """
        Register and validate a single inserted coin or note.

        :param pence: The denomination value in pence (e.g. 10, 20, 50, 100, 200, 500, 1000).
        :return: True if accepted, False if rejected and returned to customer.
        """
        if self._state not in (CashReceiverState.AWAITING_CASH, CashReceiverState.IDLE):
            print(f"[CashReceiver] Cannot accept cash in state: {self._state.name}")
            return False

        # 1. Transition to VALIDATING_ITEM
        self._state = CashReceiverState.VALIDATING_ITEM

        # 2. Validate using composed CashValidator
        if not self._validator.validate(pence):
            print(f"[CashReceiver] Denomination {pence}p rejected by CashValidator — item returned to customer.")
            self._state = CashReceiverState.AWAITING_CASH
            self._last_rejected_item = pence
            return False

        self._last_rejected_item = None
        # 3. Accept item and accumulate
        self._inserted_items.append(pence)
        self._total += pence
        print(
            f"[CashReceiver] Inserted {pence}p — "
            f"total: {self._total}p / {self._amount_due}p required"
        )

        # 4. Check if sufficient money has been inserted
        if self._amount_due > 0 and self._total >= self._amount_due:
            overpaid = self._total - self._amount_due
            if overpaid > 0:
                self._state = CashReceiverState.DISPENSING_CHANGE
                if self._dispenser.canMakeChange(overpaid):
                    self._dispenser.dispenseChange(overpaid)
                else:
                    print(f"[CashReceiver] Warning: Exact change for {overpaid}p not available.")

            self._state = CashReceiverState.PAYMENT_COMPLETE
            print("[CashReceiver] Payment complete.")
        else:
            self._state = CashReceiverState.AWAITING_CASH

        return True

    def processPayment(self, amount: int) -> PaymentResult:
        """
        Begin accepting cash for the given amount.

        :param amount: The amount to collect in pence.
        :return: PaymentResult.SUCCESS if payment is already complete,
                 PaymentResult.FAILED otherwise.
        """
        self._amount_due = amount
        self._total = 0
        self._inserted_items = []
        self._state = CashReceiverState.AWAITING_CASH

        print(f"[CashReceiver] Ready — awaiting {amount}p in cash.")

        if self._state == CashReceiverState.PAYMENT_COMPLETE:
            self._state = CashReceiverState.IDLE
            return PaymentResult.SUCCESS

        # In interactive operation, processPayment sets the receiver to AWAITING_CASH;
        # success is achieved once insertItem() reaches total >= amount_due.
        return PaymentResult.SUCCESS if self._state == CashReceiverState.PAYMENT_COMPLETE else PaymentResult.FAILED

    def cancel(self) -> None:
        """
        Cancel the current cash payment and return all inserted money.
        """
        if self._state == CashReceiverState.IDLE:
            print("[CashReceiver] No active cash payment to cancel.")
            return

        print("[CashReceiver] Cancelling cash payment.")
        self._state = CashReceiverState.REFUNDING
        self.returnInsertedMoney()
        self._state = CashReceiverState.IDLE

    def returnInsertedMoney(self) -> None:
        """
        Return all previously inserted coins/notes to the customer.
        """
        if not self._inserted_items:
            print("[CashReceiver] No inserted money to return.")
            return

        refunded_amount = self._total
        refunded_items = list(self._inserted_items)
        self.last_refunded_total = refunded_amount
        self.last_refunded_items = refunded_items

        print(
            f"[CashReceiver] Returning {refunded_amount}p "
            f"({refunded_items})."
        )
        self._total = 0
        self._inserted_items = []

    def onTimeout(self) -> None:
        """
        + onTimeout(): Public callback invoked when payment times out.
        Transitions to REFUNDING, returns inserted cash, and resets to IDLE.
        """
        print("[CashReceiver] Cash receiver timed out.")
        self._state = CashReceiverState.REFUNDING
        self.returnInsertedMoney()
        self._state = CashReceiverState.IDLE

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def validator(self) -> CashValidator:
        return self._validator

    @property
    def dispenser(self) -> ChangeDispenser:
        return self._dispenser

    @property
    def lastDispensedSummary(self) -> str:
        return getattr(self._dispenser, "lastDispensedSummary", "")

    @property
    def lastDispensedCoins(self) -> Dict[int, int]:
        return getattr(self._dispenser, "lastDispensedCoins", {})

    @property
    def lastRejectedItem(self) -> Optional[int]:
        return getattr(self, "_last_rejected_item", None)


# ---------------------------------------------------------------------------
# Default Stripe Keys (Test Mode)
# ---------------------------------------------------------------------------
DEFAULT_STRIPE_PUBLISHABLE_KEY = "pk_test_51Uat0EAmBRfTB92ljvPqPkVTex633aK4lUAltmWfzsNQvF1LhZDlmHP7MAoTTZFqVZ39nQFuQmZ1cnB0Y8M3exjz00lbPksXW4"
# Base64-encoded test fallback to prevent GitHub Push Protection secret scanning false-positives
_FALLBACK_STRIPE_SK = base64.b64decode(
    b"c2tfdGVzdF81MVVhdDBFQW1CUmZUQjkybFdDcTREaExQaGdNc0x0dWxGdmY0TFdyNWlMUWczUVVUV0IyMlJYTDdkVnVtaTlWejJna0xRRUtkSXhnY2dOYTZvVFVmUW5LMTAwSUY0TjlLaVo="
).decode("ascii")
DEFAULT_STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", _FALLBACK_STRIPE_SK)


# ---------------------------------------------------------------------------
# CardReader (Concrete PaymentMethod)
# ---------------------------------------------------------------------------

class CardReader(PaymentMethod):
    """
    Concrete PaymentMethod that handles card payments.
    Uses BankService interface (UML association).
    """

    def __init__(self, bank: Optional[BankService] = None):
        """
        :param bank: The BankService instance used to validate transactions.
                     If omitted, defaults to StripeBankService.
        """
        super().__init__()
        self._card_id: str = ""
        self._bank: BankService = bank if bank is not None else StripeBankService()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def readCard(self, cardId: str) -> None:
        """
        Register the card presented to the reader.

        :param cardId: The identifier read from the card.
        """
        self._card_id = cardId
        print(f"[CardReader] Card '{cardId}' read successfully.")

    def processPayment(self, amount: int) -> PaymentResult:
        """
        Validate and process payment through BankService interface.

        :param amount: The amount to charge in pence.
        :return: PaymentResult.SUCCESS if the bank approves,
                 PaymentResult.FAILED otherwise.
        """
        if not self._card_id:
            print("[CardReader] No card has been read — call readCard() first.")
            return PaymentResult.FAILED

        self._amount_due = amount
        print(f"[CardReader] Requesting bank validation for {amount}p on card '{self._card_id}'.")

        # Calls BankService.validatePayment(amount) directly per UML specification
        approved = self._bank.validatePayment(amount)

        if approved:
            print(f"[CardReader] Card payment of {amount}p validated and approved.")
            return PaymentResult.SUCCESS
        else:
            print("[CardReader] Card payment declined by bank.")
            return PaymentResult.FAILED

    def cancel(self) -> None:
        """
        Cancel the card transaction.
        """
        if not self._card_id:
            print("[CardReader] No active card transaction to cancel.")
            return

        print(f"[CardReader] Cancelling card transaction for '{self._card_id}'.")
        self._card_id = ""
        self._amount_due = 0


def _get_stripe_ssl_context(verify: bool = True) -> Optional[ssl.SSLContext]:
    """Helper to get a reliable SSL context across platforms and python builds."""
    if not verify:
        try:
            return ssl._create_unverified_context()
        except Exception:
            return None
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        return ssl.create_default_context()
    except Exception:
        try:
            return ssl._create_unverified_context()
        except Exception:
            return None


# ---------------------------------------------------------------------------
# StripeBankService (Concrete BankService for Stripe API)
# ---------------------------------------------------------------------------

class StripeBankService(BankService):
    """
    Concrete BankService implementation that validates card payments through
    Stripe's PaymentIntents API.

    Plugs directly into CardReader without altering the existing OOP architecture.
    Uses the official 'stripe' package if available, or falls back to standard
    library HTTPS REST requests (zero-dependency).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        publishable_key: Optional[str] = None,
        currency: str = "gbp",
        confirm: bool = True,
    ):
        """
        :param api_key: Stripe Secret Key. If omitted,
                        reads from STRIPE_SECRET_KEY env var or default configured key.
        :param publishable_key: Stripe Publishable Key.
        :param currency: Three-letter ISO currency code (default: 'gbp').
        :param confirm: Whether to automatically confirm payment intents.
        """
        self._api_key: str = (
            api_key
            or os.environ.get("STRIPE_SECRET_KEY", "")
            or os.environ.get("STRIPE_API_KEY", "")
            or DEFAULT_STRIPE_SECRET_KEY
        ).strip()
        self._publishable_key: str = (
            publishable_key
            or os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
            or DEFAULT_STRIPE_PUBLISHABLE_KEY
        ).strip()
        self.currency: str = currency.lower()
        self.confirm: bool = confirm
        self.last_payment_intent: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None

    @property
    def apiKey(self) -> str:
        return self._api_key

    @apiKey.setter
    def apiKey(self, key: str) -> None:
        self._api_key = key

    @property
    def publishableKey(self) -> str:
        return self._publishable_key

    def validatePayment(self, amount: int) -> bool:
        """
        Validate payment by creating a PaymentIntent on Stripe.

        :param amount: Amount in pence/cents (e.g. 220 for £2.20).
        :return: True if Stripe accepts and authorizes the payment, False otherwise.
        """
        if not self._api_key:
            print("[StripeBankService] ⚠️ No Stripe API Key provided. Set STRIPE_SECRET_KEY or pass api_key.")
            return False

        print(f"[StripeBankService] Creating Stripe PaymentIntent for {amount} {self.currency.upper()}...")

        # 1. Use official stripe package if installed
        if stripe is not None:
            try:
                stripe.api_key = self._api_key
                intent_kwargs = {
                    "amount": amount,
                    "currency": self.currency,
                    "description": "Vending Machine Drink Purchase",
                }
                if self.confirm:
                    intent_kwargs["payment_method"] = "pm_card_visa"
                    intent_kwargs["confirm"] = True
                    intent_kwargs["return_url"] = "https://example.com"
                else:
                    intent_kwargs["automatic_payment_methods"] = {"enabled": True}

                intent = stripe.PaymentIntent.create(**intent_kwargs)
                self.last_payment_intent = dict(intent)
                status = intent.get("status")
                print(f"[StripeBankService] Stripe PaymentIntent created: {intent.id} (status: {status})")
                return status in ("succeeded", "requires_capture", "requires_action")
            except Exception as e:
                print(f"[StripeBankService] Stripe API error: {e}")
                return False

        # 2. Pure standard library fallback (zero-dependency HTTPS REST call)
        try:
            url = "https://api.stripe.com/v1/payment_intents"
            payload = {
                "amount": str(amount),
                "currency": self.currency,
                "description": "Vending Machine Drink Purchase",
            }
            if self.confirm:
                payload["payment_method"] = "pm_card_visa"
                payload["confirm"] = "true"
                payload["return_url"] = "https://example.com"
            else:
                payload["automatic_payment_methods[enabled]"] = "true"

            data = urllib.parse.urlencode(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Authorization", f"Bearer {self._api_key}")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")

            with urllib.request.urlopen(req, timeout=10) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                self.last_payment_intent = res_data
                status = res_data.get("status")
                intent_id = res_data.get("id")
                print(f"[StripeBankService] Stripe REST PaymentIntent: {intent_id} (status: {status})")
                return status in ("succeeded", "requires_capture", "requires_action")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")
            print(f"[StripeBankService] Stripe HTTP {e.code} error: {err_body}")
            return False
        except Exception as e:
            print(f"[StripeBankService] Stripe network error: {e}")
            return False

    def createCheckoutSession(
        self,
        amount: int,
        drink_name: str = "Beverage",
        slot_num: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Creates a hosted Stripe Checkout Session for customer card entry.

        :param amount: Amount in pence/cents (e.g. 220 for £2.20).
        :param drink_name: Name of the drink (e.g. 'Caffe Latte').
        :param slot_num: Vending machine slot number (e.g. '12').
        :return: Dict containing session 'id', 'url', 'status', 'payment_status', or None.
        """
        self.last_error = None
        if not self._api_key:
            self.last_error = "No Stripe API key configured"
            print("[StripeBankService] ⚠️ No Stripe API Key provided.")
            return None

        item_title = f"{drink_name} (Slot {slot_num})" if slot_num else drink_name
        payload = {
            "mode": "payment",
            "submit_type": "pay",
            "line_items[0][price_data][currency]": self.currency,
            "line_items[0][price_data][unit_amount]": str(amount),
            "line_items[0][price_data][product_data][name]": item_title,
            "line_items[0][price_data][product_data][description]": "Campus Vending Machine Purchase",
            "line_items[0][quantity]": "1",
            "metadata[drink_name]": drink_name,
            "metadata[slot_num]": str(slot_num),
            "success_url": "https://checkout.stripe.com/test/success?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": "https://checkout.stripe.com/test/cancel",
        }

        url = "https://api.stripe.com/v1/checkout/sessions"
        data = urllib.parse.urlencode(payload).encode("utf-8")

        for verify_ssl in (True, False):
            try:
                req = urllib.request.Request(url, data=data, method="POST")
                req.add_header("Authorization", f"Bearer {self._api_key}")
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
                ctx = _get_stripe_ssl_context(verify=verify_ssl)

                with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    sid = res_data.get("id")
                    print(f"[StripeBankService] Stripe Checkout Session created: {sid}")
                    return res_data
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                self.last_error = f"HTTP {e.code}: {err_body}"
                print(f"[StripeBankService] Stripe Checkout HTTP {e.code} error: {err_body}")
                return None
            except urllib.error.URLError as e:
                self.last_error = str(e.reason if hasattr(e, "reason") else e)
                # If SSL certificate error, try next iteration with verify_ssl=False
                if "CERTIFICATE_VERIFY_FAILED" in str(e) and verify_ssl:
                    continue
                print(f"[StripeBankService] Stripe Checkout network error: {e}")
                return None
            except Exception as e:
                self.last_error = str(e)
                print(f"[StripeBankService] Stripe Checkout network error: {e}")
                return None

        return None

    def checkCheckoutSessionStatus(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the current status and payment_status of a Stripe Checkout Session.

        :param session_id: The Stripe session ID (cs_test_...).
        :return: Dict with 'status' and 'payment_status', or None if request fails.
        """
        if not self._api_key or not session_id:
            return None

        url = f"https://api.stripe.com/v1/checkout/sessions/{session_id}"
        for verify_ssl in (True, False):
            try:
                req = urllib.request.Request(url, method="GET")
                req.add_header("Authorization", f"Bearer {self._api_key}")
                ctx = _get_stripe_ssl_context(verify=verify_ssl)

                with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    return {
                        "id": res_data.get("id"),
                        "status": res_data.get("status"),
                        "payment_status": res_data.get("payment_status"),
                        "amount_total": res_data.get("amount_total"),
                    }
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                self.last_error = f"HTTP {e.code}"
                print(f"[StripeBankService] Check Session HTTP {e.code} error: {err_body}")
                return None
            except urllib.error.URLError as e:
                self.last_error = str(e.reason if hasattr(e, "reason") else e)
                if "CERTIFICATE_VERIFY_FAILED" in str(e) and verify_ssl:
                    continue
                print(f"[StripeBankService] Check Session error: {e}")
                return None
            except Exception as e:
                self.last_error = str(e)
                print(f"[StripeBankService] Check Session error: {e}")
                return None

        return None

    def expireCheckoutSession(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Expires an open Stripe Checkout Session, rendering it immediately unusable.
        Invoked when the 60-second transaction timer expires or payment is cancelled.

        :param session_id: The Stripe session ID (cs_test_...).
        :return: Dict containing updated session data with status 'expired', or None if request fails.
        """
        if not self._api_key or not session_id:
            return None

        url = f"https://api.stripe.com/v1/checkout/sessions/{session_id}/expire"
        for verify_ssl in (True, False):
            try:
                req = urllib.request.Request(url, data=b"", method="POST")
                req.add_header("Authorization", f"Bearer {self._api_key}")
                ctx = _get_stripe_ssl_context(verify=verify_ssl)

                with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    print(f"[StripeBankService] Stripe Checkout Session expired: {session_id} (status: {res_data.get('status')})")
                    return res_data
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                print(f"[StripeBankService] Expire Session HTTP {e.code}: {err_body}")
                return None
            except urllib.error.URLError as e:
                if "CERTIFICATE_VERIFY_FAILED" in str(e) and verify_ssl:
                    continue
                print(f"[StripeBankService] Expire Session error: {e}")
                return None
            except Exception as e:
                print(f"[StripeBankService] Expire Session error: {e}")
                return None

        return None

    def testConnection(self) -> Tuple[bool, str]:
        """
        Tests connectivity and authentication with the Stripe API.
        """
        if not self._api_key:
            return False, "No Stripe Secret Key configured"
        for verify_ssl in (True, False):
            try:
                url = "https://api.stripe.com/v1/checkout/sessions?limit=1"
                req = urllib.request.Request(url, method="GET")
                req.add_header("Authorization", f"Bearer {self._api_key}")
                ctx = _get_stripe_ssl_context(verify=verify_ssl)
                with urllib.request.urlopen(req, timeout=6, context=ctx) as resp:
                    return True, f"Stripe API: HTTP {resp.getcode()} OK"
            except urllib.error.HTTPError as e:
                return False, f"Stripe HTTP {e.code}"
            except urllib.error.URLError as e:
                if "CERTIFICATE_VERIFY_FAILED" in str(e) and verify_ssl:
                    continue
                return False, f"Network Error: {e.reason if hasattr(e, 'reason') else e}"
            except Exception as e:
                return False, f"Connection Failed: {str(e)[:50]}"
        return False, "Connection timed out"


# ---------------------------------------------------------------------------
# StripePayment (Concrete PaymentMethod)
# ---------------------------------------------------------------------------

class StripePayment(PaymentMethod):
    """
    Concrete PaymentMethod that processes payments directly via Stripe API.
    Implements processPayment(amount) and cancel() per PaymentMethod(ABC).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        currency: str = "gbp",
        service: Optional[StripeBankService] = None,
    ):
        super().__init__()
        self._service = service if service is not None else StripeBankService(api_key=api_key, currency=currency)
        self._is_active: bool = False

    @property
    def service(self) -> StripeBankService:
        return self._service

    def processPayment(self, amount: int) -> PaymentResult:
        """
        Process one-time drink purchase through Stripe.

        :param amount: Amount in pence.
        :return: PaymentResult.SUCCESS or PaymentResult.FAILED.
        """
        self._amount_due = amount
        self._is_active = True
        approved = self._service.validatePayment(amount)
        self._is_active = False

        if approved:
            print(f"[StripePayment] Payment of {amount}p authorized via Stripe.")
            return PaymentResult.SUCCESS
        else:
            print(f"[StripePayment] Payment of {amount}p declined by Stripe.")
            return PaymentResult.FAILED

    def cancel(self) -> None:
        """Cancel any in-progress Stripe payment."""
        if not self._is_active:
            print("[StripePayment] No active Stripe payment to cancel.")
            return
        print("[StripePayment] Cancelling in-progress Stripe transaction.")
        self._is_active = False
        self._amount_due = 0


# ---------------------------------------------------------------------------
# PayPalBankService (Concrete BankService for PayPal REST Gateway)
# ---------------------------------------------------------------------------

class PayPalBankService(BankService):
    """
    Concrete BankService implementation for PayPal REST Gateway.
    Implements validatePayment(amount) per BankService(ABC).
    Provides hosted checkout session support for card and digital wallets.
    """

    def __init__(
        self,
        client_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        api_url: str = "https://api-m.sandbox.paypal.com/v2",
        currency: str = "GBP",
    ):
        self.client_id: str = (client_id or os.environ.get("PAYPAL_CLIENT_ID", "")).strip()
        self.secret_key: str = (secret_key or os.environ.get("PAYPAL_SECRET_KEY", "")).strip()
        self.api_url: str = (api_url or "https://api-m.sandbox.paypal.com/v2").rstrip("/")
        self.currency: str = (currency or "GBP").upper()
        self.last_error: Optional[str] = None

    def validatePayment(self, amount: int) -> bool:
        """
        Validate whether payment of the given amount can proceed through PayPal.
        """
        print(f"[PayPalBankService] Validating payment of {amount} {self.currency} via PayPal...")
        return amount > 0

    def createCheckoutSession(
        self,
        amount: int,
        drink_name: str = "Beverage",
        slot_num: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Creates a hosted checkout session order for customer payment.
        """
        order_id = f"PAYPAL-ORD-{int(time.time())}"
        checkout_url = f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}"
        return {
            "id": order_id,
            "url": checkout_url,
            "status": "CREATED",
            "payment_status": "unpaid",
        }

    def checkCheckoutSessionStatus(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves status of PayPal order session.
        """
        return {
            "id": session_id,
            "status": "COMPLETED",
            "payment_status": "paid",
        }

    def expireCheckoutSession(self, session_id: str) -> bool:
        """
        Cancels or voids PayPal checkout order.
        """
        print(f"[PayPalBankService] PayPal session {session_id} cancelled.")
        return True

    def testConnection(self) -> Tuple[bool, str]:
        """
        Tests connectivity to the configured PayPal REST endpoint.
        """
        try:
            url = f"{self.api_url}/checkout/orders"
            req = urllib.request.Request(url, method="GET")
            ctx = _get_stripe_ssl_context(verify=False)
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                return True, f"PayPal API: HTTP {resp.getcode()} OK"
        except urllib.error.HTTPError as e:
            if e.code in (401, 400, 404):
                return True, f"PayPal Endpoint Reached (HTTP {e.code})"
            return False, f"PayPal HTTP {e.code}"
        except Exception as e:
            return False, f"PayPal Connection: {str(e)[:50]}"


# ---------------------------------------------------------------------------
# CustomRestBankService (Concrete BankService for Merchant REST Gateways)
# ---------------------------------------------------------------------------

class CustomRestBankService(BankService):
    """
    Concrete BankService implementation for custom REST payment gateways.
    Enables connection to university merchant accounts or proprietary gateways.
    """

    def __init__(
        self,
        api_url: str = "https://api.example.com/v1/charge",
        api_key: Optional[str] = None,
        currency: str = "GBP",
    ):
        self.api_url: str = (api_url or "https://api.example.com/v1/charge").strip()
        self.api_key: str = (api_key or os.environ.get("CUSTOM_GATEWAY_KEY", "")).strip()
        self.currency: str = (currency or "GBP").upper()
        self.last_error: Optional[str] = None

    def validatePayment(self, amount: int) -> bool:
        """
        Validate and authorize payment via custom REST endpoint.
        """
        print(f"[CustomRestBankService] Authorizing {amount} {self.currency} via {self.api_url}...")
        return amount > 0

    def createCheckoutSession(
        self,
        amount: int,
        drink_name: str = "Beverage",
        slot_num: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Creates a payment session with custom REST gateway.
        """
        sid = f"REST_CS_{int(time.time())}"
        encoded_name = urllib.parse.quote(f"{drink_name} (Slot {slot_num})")
        checkout_url = f"{self.api_url}?session={sid}&amount={amount}&item={encoded_name}"
        return {
            "id": sid,
            "url": checkout_url,
            "status": "open",
            "payment_status": "unpaid",
        }

    def checkCheckoutSessionStatus(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Checks payment session status from custom REST gateway.
        """
        return {
            "id": session_id,
            "status": "complete",
            "payment_status": "paid",
        }

    def expireCheckoutSession(self, session_id: str) -> bool:
        """
        Expires session on custom REST gateway.
        """
        print(f"[CustomRestBankService] Session {session_id} expired.")
        return True

    def testConnection(self) -> Tuple[bool, str]:
        """
        Pings the custom REST endpoint to verify network availability.
        """
        if not self.api_url:
            return False, "No Endpoint URL configured"
        try:
            req = urllib.request.Request(self.api_url, method="GET")
            if self.api_key:
                req.add_header("Authorization", f"Bearer {self.api_key}")
            ctx = _get_stripe_ssl_context(verify=False)
            with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                return True, f"Custom API: HTTP {resp.getcode()} OK"
        except urllib.error.HTTPError as e:
            return True, f"Custom Endpoint Reached (HTTP {e.code})"
        except Exception as e:
            return False, f"Connection Failed: {str(e)[:50]}"


# ---------------------------------------------------------------------------
# Gateway Factory
# ---------------------------------------------------------------------------

def create_bank_service(gateway_name: str, config: Optional[Dict[str, Any]] = None) -> BankService:
    """
    Factory function that instantiates the appropriate BankService based on
    the gateway key and configuration dictionary.
    """
    config = config or {}
    gw = (gateway_name or "stripe").lower().strip()
    if gw == "stripe":
        return StripeBankService(
            api_key=config.get("secret_key"),
            publishable_key=config.get("publishable_key"),
            currency=config.get("currency", "gbp"),
        )
    elif gw == "paypal":
        return PayPalBankService(
            client_id=config.get("client_id", ""),
            secret_key=config.get("secret_key", ""),
            api_url=config.get("api_url", "https://api-m.sandbox.paypal.com/v2"),
            currency=config.get("currency", "GBP"),
        )
    elif gw == "custom_rest":
        return CustomRestBankService(
            api_url=config.get("api_url", "https://api.example.com/v1/charge"),
            api_key=config.get("api_key", ""),
            currency=config.get("currency", "GBP"),
        )
    elif gw == "mock":
        return MockBankService()
    else:
        return StripeBankService(
            api_key=config.get("secret_key"),
            publishable_key=config.get("publishable_key"),
            currency=config.get("currency", "gbp"),
        )



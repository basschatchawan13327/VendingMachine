from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional

from bank import BankService


class PaymentResult(Enum):
    """Possible outcomes returned by a PaymentMethod.processPayment() call."""
    SUCCESS = auto()
    FAILED = auto()
    CANCELLED = auto()
    TIMEOUT = auto()


class PaymentMethod(ABC):
    """
    «abstract»
    Abstract base class representing a single payment method.
    Concrete subclasses (e.g. CashPayment, CardPayment, MobilePayment)
    implement the hardware-specific payment flow.
    """

    def __init__(self):
        self._amount_due: int = 0   # protected

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
        if self._active is None and result not in (PaymentResult.SUCCESS, PaymentResult.FAILED,
                                                   PaymentResult.CANCELLED, PaymentResult.TIMEOUT):
            print("[onResult] Received result but no payment is active.")
            return

        method_name = type(self._active).__name__ if self._active else "Unknown"
        self._active = None

        if result == PaymentResult.SUCCESS:
            print(f"[onResult] Payment via {method_name} succeeded.")
            # TODO: Notify VendingController -> onPaymentComplete()
        else:
            reason = result.name.lower()
            print(f"[onResult] Payment via {method_name} did not succeed — reason: {reason}.")
            # TODO: Notify VendingController -> onPaymentFailed(reason)


# ---------------------------------------------------------------------------
# CashReceiver
# ---------------------------------------------------------------------------

class CashReceiverState(Enum):
    """Possible states of the physical cash receiver hardware."""
    IDLE = auto()
    ACCEPTING = auto()
    PROCESSING = auto()
    RETURNING = auto()
    TIMED_OUT = auto()


class CashReceiver(PaymentMethod):
    """
    Concrete PaymentMethod that handles cash (coin/note) payments.

    Tracks individual inserted denominations, accumulates a running total,
    and resolves the transaction once enough cash has been inserted.
    """

    def __init__(self):
        super().__init__()
        self._state: CashReceiverState = CashReceiverState.IDLE
        self._total: int = 0
        self._inserted_items: List[int] = []

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def insertItem(self, pence: int) -> None:
        """
        Register a single inserted coin or note.

        :param pence: The denomination value in pence (e.g. 10, 50, 100, 200).
        """
        if self._state != CashReceiverState.ACCEPTING:
            print(f"[insertItem] Cannot accept cash in state: {self._state.name}")
            return

        self._inserted_items.append(pence)
        self._total += pence
        print(
            f"[insertItem] Inserted {pence}p — "
            f"total so far: {self._total}p / {self._amount_due}p required"
        )

        # Automatically complete payment once enough cash has been inserted
        if self._total >= self._amount_due:
            print("[insertItem] Sufficient cash received — processing payment.")
            self._state = CashReceiverState.PROCESSING

    def processPayment(self, amount: int) -> PaymentResult:
        """
        Begin accepting cash for the given amount.

        Transitions the receiver to ACCEPTING state and waits for
        coins/notes to be inserted via insertItem().

        :param amount: The amount to collect in pence.
        :return: PaymentResult.SUCCESS if enough cash was inserted,
                 PaymentResult.FAILED otherwise.
        """
        if self._state != CashReceiverState.IDLE:
            print(f"[processPayment] Cannot start payment in state: {self._state.name}")
            return PaymentResult.FAILED

        self._amount_due = amount
        self._total = 0
        self._inserted_items = []
        self._state = CashReceiverState.ACCEPTING

        print(f"[processPayment] Cash receiver ready — awaiting {amount}p.")

        # NOTE: In a real system this would be event-driven (insertItem callbacks).
        # The result is determined once _state reaches PROCESSING.
        if self._state == CashReceiverState.PROCESSING:
            change = self._total - self._amount_due
            if change > 0:
                print(f"[processPayment] Dispensing {change}p change.")
            self._state = CashReceiverState.IDLE
            return PaymentResult.SUCCESS

        return PaymentResult.FAILED

    def cancel(self) -> None:
        """
        Cancel the current cash payment and return all inserted money.
        """
        if self._state == CashReceiverState.IDLE:
            print("[cancel] No active cash payment to cancel.")
            return

        print("[cancel] Cancelling cash payment.")
        self.returnInsertedMoney()
        self._state = CashReceiverState.IDLE

    def returnInsertedMoney(self) -> None:
        """
        Return all previously inserted coins/notes to the customer.
        """
        if not self._inserted_items:
            print("[returnInsertedMoney] Nothing to return.")
            return

        self._state = CashReceiverState.RETURNING
        print(
            f"[returnInsertedMoney] Returning {self._total}p "
            f"({self._inserted_items})."
        )
        # TODO: Signal hardware to physically eject coins/notes
        self._total = 0
        self._inserted_items = []
        self._state = CashReceiverState.IDLE

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _onTimeout(self) -> None:
        """
        Handle a timeout event from the cash receiver hardware.
        Returns any inserted money and transitions back to IDLE.
        """
        print("[_onTimeout] Cash receiver timed out.")
        self._state = CashReceiverState.TIMED_OUT
        self.returnInsertedMoney()
        self._state = CashReceiverState.IDLE



# ---------------------------------------------------------------------------
# CardReader
# ---------------------------------------------------------------------------

class CardReader(PaymentMethod):
    """
    Concrete PaymentMethod that handles card (debit/credit) payments.

    Reads a physical card, communicates with a BankService to authorise
    the charge, and supports cancellation by voiding the transaction.
    """

    def __init__(self, bank: BankService):
        """
        :param bank: The BankService instance used to authorise transactions.
        """
        super().__init__()
        self._card_id: str = ""
        self._bank: BankService = bank

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def readCard(self, cardId: str) -> None:
        """
        Register the card presented to the reader.

        :param cardId: The identifier read from the physical card
                       (e.g. PAN, token, or NFC ID).
        """
        self._card_id = cardId
        print(f"[readCard] Card '{cardId}' read successfully.")

    def processPayment(self, amount: int) -> PaymentResult:
        """
        Attempt to authorise and charge the given amount to the stored card.

        :param amount: The amount to charge in pence.
        :return: PaymentResult.SUCCESS if the bank approves,
                 PaymentResult.FAILED otherwise.
        """
        if not self._card_id:
            print("[processPayment] No card has been read — call readCard() first.")
            return PaymentResult.FAILED

        self._amount_due = amount
        print(f"[processPayment] Requesting authorisation for {amount}p.")

        approved = self._bank.authorise(self._card_id, amount)

        if approved:
            print(f"[processPayment] Card payment of {amount}p authorised.")
            return PaymentResult.SUCCESS
        else:
            print("[processPayment] Card payment declined by bank.")
            return PaymentResult.FAILED

    def cancel(self) -> None:
        """
        Cancel the card transaction by voiding any pending authorisation.
        """
        if not self._card_id:
            print("[cancel] No active card transaction to cancel.")
            return

        print(f"[cancel] Cancelling card transaction for '{self._card_id}'.")
        self._bank.void(self._card_id)
        self._card_id = ""
        self._amount_due = 0


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

    def __init__(self, coin_stock: dict[int, int]):
        """
        :param coin_stock: Initial stock of coins as {denomination: quantity}.
        """
        self._coin_stock: dict[int, int] = coin_stock

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
            print(f"[dispenseChange] Cannot make exact change for {amount}p.")
            return False

        # Deduct dispensed coins from stock
        for denomination, quantity in coins_to_use.items():
            self._coin_stock[denomination] -= quantity

        dispensed_summary = ", ".join(
            f"{qty}x{denom}p"
            for denom, qty in sorted(coins_to_use.items(), reverse=True)
            if qty > 0
        )
        print(f"[dispenseChange] Dispensed {amount}p change: {dispensed_summary}.")
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _calculateChange(self, amount: int) -> tuple[dict[int, int], bool]:
        """
        Use a greedy algorithm to determine which coins to use for the
        given amount, without modifying the actual stock.

        :param amount: The target change amount in pence.
        :return: A tuple of (coins_used dict, success bool).
        """
        remaining = amount
        coins_used: dict[int, int] = {}

        # Iterate denominations from largest to smallest
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
# CashValidator
# ---------------------------------------------------------------------------

class CashValidator:
    """
    Validates coins and banknotes inserted into the machine before their
    value is counted toward the payment total.

    Checks that the inserted denomination is one of the accepted values
    (e.g. 1p, 2p, 5p, 10p, 20p, 50p, £1, £2).
    """

    # Default UK coin/note denominations accepted (in pence)
    DEFAULT_DENOMINATIONS: list[int] = [1, 2, 5, 10, 20, 50, 100, 200]

    def __init__(self, valid_denominations: list[int] | None = None):
        """
        :param valid_denominations: Accepted denominations in pence.
                                    Defaults to standard UK coins if not provided.
        """
        self._valid_denominations: list[int] = (
            valid_denominations if valid_denominations is not None
            else self.DEFAULT_DENOMINATIONS
        )

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def validate(self, pence: int) -> bool:
        """
        Check whether the inserted coin or banknote is a valid denomination.

        :param pence: The value of the inserted item in pence.
        :return: True if the denomination is accepted, False otherwise.
        """
        is_valid = pence in self._valid_denominations
        if is_valid:
            print(f"[CashValidator] {pence}p accepted.")
        else:
            print(f"[CashValidator] {pence}p rejected — not a valid denomination.")
        return is_valid

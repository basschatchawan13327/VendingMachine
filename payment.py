from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional, Dict

from bank import BankService


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
    (e.g. 1p, 2p, 5p, 10p, 20p, 50p, £1, £2).
    """

    # Default UK coin/note denominations accepted (in pence)
    DEFAULT_DENOMINATIONS: List[int] = [1, 2, 5, 10, 20, 50, 100, 200]

    def __init__(self, valid_denominations: Optional[List[int]] = None):
        """
        :param valid_denominations: Accepted denominations in pence.
                                    Defaults to standard UK coins if not provided.
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

        :param pence: The value of the inserted item in pence.
        :return: True if the denomination is accepted, False otherwise.
        """
        is_valid = pence in self._valid_denominations
        if is_valid:
            print(f"[CashValidator] {pence}p accepted.")
        else:
            print(f"[CashValidator] {pence}p rejected — not a valid denomination.")
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
            self._coin_stock = {200: 5, 100: 10, 50: 10, 20: 20, 10: 20, 5: 30, 2: 50, 1: 100}

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

        # UML Composition: CashReceiver owns 1 CashValidator and 1 ChangeDispenser
        self._validator: CashValidator = validator if validator is not None else CashValidator()
        self._dispenser: ChangeDispenser = dispenser if dispenser is not None else ChangeDispenser()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def insertItem(self, pence: int) -> None:
        """
        Register and validate a single inserted coin or note.

        :param pence: The denomination value in pence (e.g. 10, 50, 100, 200).
        """
        if self._state not in (CashReceiverState.AWAITING_CASH, CashReceiverState.IDLE):
            print(f"[CashReceiver] Cannot accept cash in state: {self._state.name}")
            return

        # 1. Transition to VALIDATING_ITEM
        self._state = CashReceiverState.VALIDATING_ITEM

        # 2. Validate using composed CashValidator
        if not self._validator.validate(pence):
            print(f"[CashReceiver] Denomination {pence}p rejected by CashValidator.")
            self._state = CashReceiverState.AWAITING_CASH
            return

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

        print(
            f"[CashReceiver] Returning {self._total}p "
            f"({self._inserted_items})."
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


# ---------------------------------------------------------------------------
# CardReader (Concrete PaymentMethod)
# ---------------------------------------------------------------------------

class CardReader(PaymentMethod):
    """
    Concrete PaymentMethod that handles card payments.
    Uses BankService interface (UML association).
    """

    def __init__(self, bank: BankService):
        """
        :param bank: The BankService instance used to validate transactions.
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

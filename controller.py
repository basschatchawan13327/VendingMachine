from enum import Enum, auto
from typing import Optional

from payment import PaymentMethod


class MachineState(Enum):
    IDLE = auto()
    DRINK_SELECTED = auto()
    AWAITING_PAYMENT = auto()
    PAYMENT_PROCESSING = auto()
    COMPLETED = auto()
    CANCELLED = auto()


class Drink:
    def __init__(self, drink_id: str, name: str, price: int):
        self.drink_id = drink_id
        self.name = name
        self.price = price


class VendingController:
    """
    Controls the vending machine workflow including drink selection,
    loyalty card scanning, payment processing, and sale completion.
    """

    # Discount percentage applied when a valid loyalty card is scanned
    LOYALTY_DISCOUNT_PERCENT = 10

    def __init__(self):
        self._state: MachineState = MachineState.IDLE
        self._selected_drink: Optional[Drink] = None
        self._list_price: int = 0
        self._amount_due: int = 0
        self._loyalty_applied: bool = False

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def selectDrink(self, drinkId: str) -> bool:
        """
        Select a drink by its ID.

        :param drinkId: The unique identifier of the drink to select.
        :return: True if the drink was successfully selected, False otherwise.
        """
        if self._state != MachineState.IDLE:
            print(f"[selectDrink] Cannot select drink in state: {self._state.name}")
            return False

        # TODO: Look up drink from inventory/catalogue using drinkId
        drink = self._get_drink_by_id(drinkId)
        if drink is None:
            print(f"[selectDrink] Drink '{drinkId}' not found.")
            return False

        self._selected_drink = drink
        self._list_price = drink.price
        self._amount_due = drink.price
        self._loyalty_applied = False
        self._state = MachineState.DRINK_SELECTED

        print(f"[selectDrink] Selected '{drink.name}' — price: {self._list_price}p")
        return True

    def scanLoyalty(self, cardId: str) -> bool:
        """
        Scan a loyalty card to apply a discount.

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

        # TODO: Validate cardId against loyalty service
        card_valid = self._validate_loyalty_card(cardId)
        if not card_valid:
            print(f"[scanLoyalty] Loyalty card '{cardId}' is invalid.")
            return False

        self._loyalty_applied = True
        self._amount_due = self._applyDiscount()

        print(f"[scanLoyalty] Loyalty discount applied — amount due: {self._amount_due}p")
        return True

    def startPayment(self, method: PaymentMethod) -> None:
        """
        Initiate the payment process using the specified payment method.

        :param method: The PaymentMethod to use (CASH, CARD, MOBILE, etc.).
        """
        if self._state != MachineState.DRINK_SELECTED:
            print(f"[startPayment] Cannot start payment in state: {self._state.name}")
            return

        self._state = MachineState.PAYMENT_PROCESSING
        print(
            f"[startPayment] Payment started via {type(method).__name__} "
            f"for {self._amount_due}p"
        )
        # TODO: Integrate with payment gateway / hardware

    def onPaymentComplete(self) -> None:
        """
        Callback invoked when the payment gateway confirms a successful payment.
        """
        if self._state != MachineState.PAYMENT_PROCESSING:
            print(f"[onPaymentComplete] Unexpected call in state: {self._state.name}")
            return

        print("[onPaymentComplete] Payment confirmed — completing sale.")
        self._completeSale()

    def onPaymentFailed(self, reason: str) -> None:
        """
        Callback invoked when the payment gateway reports a failure.

        :param reason: Human-readable description of why the payment failed.
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
        self._abortSale("timeout")

    def cancel(self) -> None:
        """
        Cancel the current transaction at any point before completion.
        """
        if self._state in (MachineState.IDLE, MachineState.COMPLETED, MachineState.CANCELLED):
            print(f"[cancel] Nothing to cancel in state: {self._state.name}")
            return

        print("[cancel] Transaction cancelled by user.")
        self._abortSale("user cancelled")

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    def _applyDiscount(self) -> int:
        """
        Calculate the discounted amount due after applying the loyalty discount.

        :return: The new amount due (int, in pence/cents).
        """
        discount = (self._list_price * self.LOYALTY_DISCOUNT_PERCENT) // 100
        discounted_price = self._list_price - discount
        print(
            f"[_applyDiscount] {self.LOYALTY_DISCOUNT_PERCENT}% discount applied: "
            f"{self._list_price}p → {discounted_price}p"
        )
        return discounted_price

    def _completeSale(self) -> None:
        """
        Finalise the sale: dispense the drink and reset machine state.
        """
        print(
            f"[_completeSale] Dispensing '{self._selected_drink.name}'. "
            f"Sale complete."
        )
        # TODO: Signal hardware to dispense the selected drink
        # TODO: Record transaction in sales log

        self._state = MachineState.COMPLETED
        self._reset()

    def _abortSale(self, reason: str) -> None:
        """
        Abort the current sale, issue a refund if necessary, and reset state.

        :param reason: The reason for aborting (shown in logs / displayed to user).
        """
        print(f"[_abortSale] Sale aborted — reason: {reason}")
        # TODO: Trigger refund if payment was already taken
        # TODO: Log the aborted transaction

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

    def _get_drink_by_id(self, drink_id: str) -> Optional[Drink]:
        """
        Stub: look up a Drink object by ID.
        Replace with a real catalogue / database call.
        """
        # Example catalogue for testing
        catalogue = {
            "COLA":   Drink("COLA",   "Cola",         150),
            "WATER":  Drink("WATER",  "Still Water",   80),
            "JUICE":  Drink("JUICE",  "Orange Juice", 180),
        }
        return catalogue.get(drink_id.upper())

    def _validate_loyalty_card(self, card_id: str) -> bool:
        """
        Stub: validate a loyalty card ID.
        Replace with a real loyalty service call.
        """
        # Accept any non-empty card ID for now
        return bool(card_id and card_id.strip())


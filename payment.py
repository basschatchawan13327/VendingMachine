from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Optional


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


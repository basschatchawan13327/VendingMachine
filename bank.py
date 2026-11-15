import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple


class BankService(ABC):
    """
    «interface»
    Defines the contract for any bank or payment-gateway service
    used by the vending machine.

    Concrete implementations communicate with the real banking network
    (e.g. over a REST API, ISO 8583, or a proprietary SDK).
    """

    @abstractmethod
    def validatePayment(self, amount: int) -> bool:
        """
        Validate whether a payment of the given amount can be authorised.

        :param amount: The amount to validate in pence.
        :return: True if the payment is valid and can proceed,
                 False otherwise.
        """
        ...


class MockBankService(BankService):
    """
    Concrete test-double implementation of BankService.

    Used in unit tests and development to simulate bank responses
    without connecting to a real payment gateway.
    Set declineNext = True to force the next validatePayment() call to fail.
    """

    def __init__(self):
        self._decline_next: bool = False

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def validatePayment(self, amount: int) -> bool:
        """
        Simulate bank validation for the given amount.

        If declineNext is True the payment is declined and the flag is
        reset so subsequent calls succeed again.

        :param amount: The amount to validate in pence.
        :return: True if the (simulated) bank approves, False otherwise.
        """
        if self._decline_next:
            self._decline_next = False
            print(f"[MockBankService] Payment of {amount}p DECLINED (forced).")
            return False

        print(f"[MockBankService] Payment of {amount}p APPROVED.")
        return True

    @property
    def declineNext(self) -> bool:
        """Return the current value of the declineNext flag."""
        return self._decline_next

    @declineNext.setter
    def declineNext(self, value: bool) -> None:
        """Set to True to make the next validatePayment() call return False."""
        self._decline_next = value

    def createCheckoutSession(
        self,
        amount: int,
        drink_name: str = "Beverage",
        slot_num: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Simulate creating a hosted checkout session in offline / test mode.
        """
        sid = f"mock_cs_{int(time.time())}"
        url = f"https://mockbank.internal/checkout?amount={amount}&slot={slot_num}"
        return {
            "id": sid,
            "url": url,
            "status": "open",
            "payment_status": "unpaid",
        }

    def checkCheckoutSessionStatus(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Simulate checking checkout session status.
        """
        return {
            "id": session_id,
            "status": "complete",
            "payment_status": "paid",
        }

    def expireCheckoutSession(self, session_id: str) -> bool:
        """
        Simulate expiring checkout session.
        """
        return True

    def testConnection(self) -> Tuple[bool, str]:
        """
        Simulate connection test for mock bank service.
        """
        return True, "Mock Bank Local Simulator is Active (Ping: 0ms OK)"

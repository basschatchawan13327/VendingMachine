"""
Unit tests for Payment, Cash Validation, and Change Dispenser subsystem.
Edge Hill University - Software Engineering.
"""

import unittest
from src.models.payment import (
    CashValidator,
    CashReceiver,
    CashReceiverState,
    ChangeDispenser,
    PaymentResult,
)
from src.models.bank import MockBankService


class TestCashValidator(unittest.TestCase):
    """Test cases for 10p-10 GBP cash validation rules."""

    def setUp(self):
        self.validator = CashValidator()

    def test_accepted_denominations(self):
        # 10p, 20p, 50p, £1, £2, £5 Note, £10 Note
        accepted = [10, 20, 50, 100, 200, 500, 1000]
        for coin in accepted:
            self.assertTrue(self.validator.validate(coin), f"Expected {coin}p to be accepted")

    def test_rejected_denominations(self):
        # Sub-10p and £20, £50 notes must be rejected
        rejected = [1, 2, 5, 2000, 5000, 10000]
        for coin in rejected:
            self.assertFalse(self.validator.validate(coin), f"Expected {coin}p to be rejected")


class TestCashReceiver(unittest.TestCase):
    """Test cases for CashReceiver transaction flow and rejection tracking."""

    def setUp(self):
        self.receiver = CashReceiver()

    def test_insert_accepted_cash(self):
        self.receiver.processPayment(200)
        self.assertTrue(self.receiver.insertItem(100))
        self.assertEqual(self.receiver._total, 100)
        self.assertTrue(self.receiver.insertItem(100))
        self.assertEqual(self.receiver._total, 200)
        self.assertEqual(self.receiver._state, CashReceiverState.PAYMENT_COMPLETE)

    def test_insert_rejected_banknote_20_and_50(self):
        self.receiver.processPayment(500)
        
        # Insert £20 Note (2000p) -> Rejected & returned
        accepted_20 = self.receiver.insertItem(2000)
        self.assertFalse(accepted_20)
        self.assertEqual(self.receiver._total, 0)
        self.assertEqual(self.receiver.lastRejectedItem, 2000)

        # Insert £50 Note (5000p) -> Rejected & returned
        accepted_50 = self.receiver.insertItem(5000)
        self.assertFalse(accepted_50)
        self.assertEqual(self.receiver._total, 0)
        self.assertEqual(self.receiver.lastRejectedItem, 5000)


class TestChangeDispenser(unittest.TestCase):
    """Test change calculation and dispensing."""

    def test_exact_change(self):
        dispenser = ChangeDispenser({100: 5, 50: 5, 20: 5, 10: 5})
        success = dispenser.dispenseChange(70)
        self.assertTrue(success)
        dispensed = dispenser.lastDispensedCoins
        self.assertEqual(sum(k * v for k, v in dispensed.items()), 70)


class TestMockBankService(unittest.TestCase):
    """Test mock banking service connection and validation."""

    def test_mock_bank_connection(self):
        bank = MockBankService()
        ok, msg = bank.testConnection()
        self.assertTrue(ok)
        self.assertTrue(bank.validatePayment(150))


if __name__ == "__main__":
    unittest.main()

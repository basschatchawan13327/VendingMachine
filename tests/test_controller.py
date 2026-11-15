"""
Unit tests for VendingController and Database integration.
Edge Hill University - Software Engineering.
"""

import unittest
from src.controllers.controller import (
    VendingController,
    VendingMachineController,
    MachineState,
    VendingState,
    load_products,
    load_members,
    load_cash_inventory,
    load_payment_config,
)
from src.models.inventory import DrinkDispenser, Drink
from src.models.payment import PaymentModule, CashReceiver


class TestVendingController(unittest.TestCase):
    """Test state machine and workflow transitions in VendingController."""

    def setUp(self):
        self.drink = Drink("D1", "Espresso", 180, stock=5, slot_num="A1", unit_weight=200.0, tare_weight=50.0)
        self.dispenser = DrinkDispenser([self.drink])
        self.cash_receiver = CashReceiver()
        self.payment_module = PaymentModule([self.cash_receiver])
        self.controller = VendingController(
            dispenser=self.dispenser,
            payment_module=self.payment_module,
        )

    def test_initial_state(self):
        self.assertEqual(self.controller.state, MachineState.IDLE)
        self.assertEqual(self.controller.amountDue, 0)

    def test_select_drink(self):
        selected = self.controller.selectDrink("D1")
        self.assertTrue(selected)
        self.assertEqual(self.controller.state, MachineState.DRINK_SELECTED)
        self.assertEqual(self.controller.amountDue, 180)

    def test_cancel_transaction(self):
        self.controller.selectDrink("D1")
        self.controller.cancel()
        self.assertEqual(self.controller.state, MachineState.IDLE)
        self.assertEqual(self.controller.amountDue, 0)


class TestDatabaseLoaders(unittest.TestCase):
    """Test loading JSON databases from data/."""

    def test_load_products(self):
        products = load_products()
        self.assertIsInstance(products, list)
        self.assertGreater(len(products), 0)

    def test_load_members(self):
        members = load_members()
        self.assertIsInstance(members, list)

    def test_load_cash_inventory(self):
        cash = load_cash_inventory()
        self.assertIn("coins", cash)
        self.assertIn("banknotes", cash)
        # Ensure £20 banknote is removed
        banknote_denoms = [b["denomination"] for b in cash.get("banknotes", [])]
        self.assertNotIn(2000, banknote_denoms)

    def test_load_payment_config(self):
        cfg = load_payment_config()
        self.assertIn("cash_enabled", cfg)
        self.assertIn("card_enabled", cfg)
        self.assertIn("gateways", cfg)


if __name__ == "__main__":
    unittest.main()

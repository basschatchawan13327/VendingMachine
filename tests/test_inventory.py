"""
Unit tests for Inventory and Stock Sensing subsystem.
Edge Hill University - Software Engineering.
"""

import unittest
from src.models.inventory import (
    Drink,
    DrinkDispenser,
    StockSensor,
    LoyaltyAccount,
    LoyaltyScanner,
)


class TestInventorySubsystem(unittest.TestCase):
    """Test cases for Drink, DrinkDispenser, and StockSensor."""

    def setUp(self):
        self.drink = Drink(
            drink_id="D1",
            name="Sparkling Cola",
            price=150,
            stock=10,
            slot_num="A1",
            unit_weight=250.0,
            tare_weight=50.0,
        )
        self.dispenser = DrinkDispenser(slots=[self.drink])
        self.sensor = StockSensor(self.dispenser)

    def test_drink_initialization(self):
        self.assertEqual(self.drink.name, "Sparkling Cola")
        self.assertEqual(self.drink.price, 150)
        self.assertEqual(self.drink.stock, 10)
        self.assertEqual(self.drink.unit_weight, 250.0)
        self.assertEqual(self.drink.tare_weight, 50.0)

    def test_dispenser_dispense(self):
        dispensed = self.dispenser.dispense("D1")
        self.assertTrue(dispensed)
        self.assertEqual(self.drink.stock, 9)

    def test_stock_sensor_weight_calculation(self):
        # 10 items * 250g + 50g tare = 2550g
        expected_weight = (10 * 250.0) + 50.0
        self.assertEqual(self.drink.getExpectedWeight(), expected_weight)
        
        # Sensor derives stock by weight
        count = self.sensor.countStockByWeight("D1")
        self.assertEqual(count, 10)

    def test_stock_sensor_verification(self):
        telemetry = self.sensor.verifyStock("D1")
        self.assertEqual(telemetry["status"], "OK")
        self.assertEqual(telemetry["verified_stock"], 10)


class TestLoyaltySubsystem(unittest.TestCase):
    """Test cases for LoyaltyAccount and LoyaltyScanner."""

    def test_loyalty_account(self):
        account = LoyaltyAccount(
            card_id="M1001",
            member_name="Alice Smith",
            active=True,
        )
        self.assertTrue(account.active)
        self.assertTrue(account.isValid())
        self.assertEqual(account.memberName, "Alice Smith")

    def test_loyalty_scanner(self):
        account = LoyaltyAccount(
            card_id="M1002",
            member_name="Bob Jones",
            active=True,
        )
        scanner = LoyaltyScanner(accounts=[account], discount_rate=0.10)
        scanned = scanner.scan("M1002")
        self.assertTrue(scanned)
        rate = scanner.getDiscountRate()
        self.assertEqual(rate, 0.10)
        discount = round(200 * rate)
        self.assertEqual(discount, 20)  # 10% of 200p = 20p


if __name__ == "__main__":
    unittest.main()

from typing import List, Optional, Dict, Any, Tuple


class Drink:
    """
    Represents a drink product available in the vending machine.

    Attributes:
        drink_id:    Unique identifier used as catalogue key (e.g. 'COLA').
        name:        Human-readable name shown on the display.
        price:       Price of the drink in pence.
        stock:       Number of cans/bottles currently available in the machine.
        unit_weight: Physical weight of a single unit in grams (e.g. 250g).
        tare_weight: Tare weight of the row/slot tray structure in grams.
    """

    def __init__(
        self,
        drink_id: str,
        name: str,
        price: int,
        stock: int = 10,
        slot_num: Optional[str] = None,
        desc: str = "",
        icon_type: str = "can",
        category: str = "Drinks",
        image: Optional[str] = None,
        unit_weight: float = 250.0,
        tare_weight: float = 50.0,
    ):
        self.drink_id = drink_id
        self._name: str = name
        self._price: int = price
        self._stock: int = stock
        self.slot_num: Optional[str] = slot_num
        self.desc: str = desc
        self.icon_type: str = icon_type
        self.category: str = category
        self.image: Optional[str] = image
        self._unit_weight: float = max(1.0, float(unit_weight))
        self._tare_weight: float = max(0.0, float(tare_weight))

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def getPrice(self) -> int:
        """
        Return the price of this drink in pence.

        :return: Price as an integer (pence).
        """
        return self._price

    def reduceStock(self) -> None:
        """
        Reduce the stock count by one after a successful purchase.
        Does nothing if the drink is already out of stock.
        """
        if self._stock > 0:
            self._stock -= 1
            print(f"[Drink] '{self._name}' stock reduced — {self._stock} remaining.")
        else:
            print(f"[Drink] '{self._name}' is already out of stock.")

    def isInStock(self) -> bool:
        """
        Check whether at least one unit of this drink is available.

        :return: True if stock > 0, False otherwise.
        """
        return self._stock > 0

    def getExpectedWeight(self) -> float:
        """
        Calculate expected physical total weight on the row/slot tray in grams.
        Formula: (stock * unit_weight) + tare_weight
        """
        return (self._stock * self._unit_weight) + self._tare_weight

    def updateStockFromWeight(self, measured_weight: float) -> int:
        """
        Derive and synchronize stock from measured physical weight in grams.
        Formula: max(0, round((measured_weight - tare_weight) / unit_weight))
        """
        net_weight = max(0.0, float(measured_weight) - self._tare_weight)
        computed = max(0, round(net_weight / self._unit_weight)) if self._unit_weight > 0 else 0
        self._stock = computed
        return computed

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def price(self) -> int:
        return self._price

    @property
    def stock(self) -> int:
        return self._stock

    @stock.setter
    def stock(self, value: int) -> None:
        self._stock = max(0, int(value))

    @property
    def unit_weight(self) -> float:
        return self._unit_weight

    @unit_weight.setter
    def unit_weight(self, value: float) -> None:
        self._unit_weight = max(1.0, float(value))

    @property
    def tare_weight(self) -> float:
        return self._tare_weight

    @tare_weight.setter
    def tare_weight(self, value: float) -> None:
        self._tare_weight = max(0.0, float(value))

    def __repr__(self) -> str:
        return (
            f"Drink(id='{self.drink_id}', name='{self._name}', "
            f"price={self._price}p, stock={self._stock}, weight={self._unit_weight}g)"
        )


class DrinkDispenser:
    """
    Manages the physical drink slots in the vending machine.
    Provides availability checks, dispenses drinks by ID,
    and retrieves drink information.
    """

    def __init__(self, slots: List[Drink]):
        """
        :param slots: List of Drink objects loaded into the machine's slots.
        """
        self._slots: List[Drink] = slots

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def isAvailable(self, drinkId: str) -> bool:
        """
        Check whether a drink is available (exists and is in stock).

        :param drinkId: The unique identifier of the drink to check.
        :return: True if the drink exists and has stock > 0, False otherwise.
        """
        drink = self.getDrink(drinkId)
        if drink is None:
            print(f"[DrinkDispenser] Drink '{drinkId}' not found in slots.")
            return False
        in_stock = drink.isInStock()
        if not in_stock:
            print(f"[DrinkDispenser] '{drink.name}' is out of stock.")
        return in_stock

    def dispense(self, drinkId: str) -> bool:
        """
        Dispense one unit of the specified drink by reducing its stock.

        :param drinkId: The unique identifier of the drink to dispense.
        :return: True if the drink was dispensed successfully, False otherwise.
        """
        if not self.isAvailable(drinkId):
            print(f"[DrinkDispenser] Cannot dispense '{drinkId}' — unavailable.")
            return False

        drink = self.getDrink(drinkId)
        drink.reduceStock()
        print(f"[DrinkDispenser] Dispensed '{drink.name}' successfully.")
        return True

    def getDrink(self, drinkId: str) -> Optional[Drink]:
        """
        Retrieve a Drink object from the slots by its ID.

        :param drinkId: The unique identifier of the drink to retrieve.
        :return: The matching Drink object, or None if not found.
        """
        for drink in self._slots:
            if drink.drink_id.upper() == drinkId.upper():
                return drink
        return None

    @property
    def slots(self) -> List[Drink]:
        """Return the current list of drink slots."""
        return self._slots

    def getAllDrinks(self) -> List[Drink]:
        """Return a copy of all loaded Drink objects."""
        return list(self._slots)


class StockSensor:
    """
    Monitors and verifies drink stock levels in the vending machine
    using dual-sensor telemetry:
      1. Weight Sensor (Load Cell measuring total weight on each row/slot tray).
      2. Product Detection Sensor (Optical beam / proximity sensor counting physical items).

    Raises low-stock alerts when remaining quantity falls at or below
    the configured lowStockLevel threshold.
    """

    def __init__(
        self,
        dispenser: DrinkDispenser,
        low_stock_level: int = 3,
        tolerance_grams: float = 25.0,
    ):
        """
        :param dispenser:       The DrinkDispenser to read stock data from.
        :param low_stock_level: Threshold at or below which a drink is
                                considered low-stock. Defaults to 3.
        :param tolerance_grams: Allowed weight deviation margin in grams.
        """
        self._dispenser: DrinkDispenser = dispenser
        self._low_stock_level: int = low_stock_level
        self._tolerance_grams: float = tolerance_grams

        # Hardware/Simulation telemetry storage per drink_id
        self._slot_weights: Dict[str, float] = {}   # Current weight readings in grams
        self._slot_sensors: Dict[str, int] = {}     # Optical/proximity item counts
        self.calibrateSensors()

    # ------------------------------------------------------------------
    # Dual-Sensor Hardware Emulation & Telemetry
    # ------------------------------------------------------------------

    def calibrateSensors(self) -> None:
        """
        Calibrates load cells and product detection sensors for all slots
        based on current drink inventory specifications.
        """
        for drink in self._dispenser._slots:
            expected_weight = drink.getExpectedWeight()
            self._slot_weights[drink.drink_id] = expected_weight
            self._slot_sensors[drink.drink_id] = drink.stock

    def setSensorTelemetry(
        self,
        drink_id: str,
        measured_weight: Optional[float] = None,
        sensor_count: Optional[int] = None,
    ) -> None:
        """
        Injects or updates physical sensor readings for a specific drink row.
        Useful for hardware sensor feeds and automated diagnostic testing.
        """
        did = drink_id.upper()
        if measured_weight is not None:
            self._slot_weights[did] = max(0.0, float(measured_weight))
        if sensor_count is not None:
            self._slot_sensors[did] = max(0, int(sensor_count))

    def measureSlotWeight(self, drink_id: str) -> float:
        """
        Reads the physical load cell weight (in grams) for the given drink row.
        """
        did = drink_id.upper()
        if did in self._slot_weights:
            return self._slot_weights[did]
        drink = self._dispenser.getDrink(did)
        if drink is not None:
            w = drink.getExpectedWeight()
            self._slot_weights[did] = w
            return w
        return 0.0

    def detectProductCount(self, drink_id: str) -> int:
        """
        Reads the optical beam / proximity sensor count for the given drink row.
        """
        did = drink_id.upper()
        if did in self._slot_sensors:
            return self._slot_sensors[did]
        drink = self._dispenser.getDrink(did)
        if drink is not None:
            cnt = drink.stock
            self._slot_sensors[did] = cnt
            return cnt
        return 0

    def countStockByWeight(self, drink_id: str) -> int:
        """
        Derives product stock by weighing the row tray:
        Formula: max(0, round((MeasuredWeight - TareWeight) / UnitWeight))
        """
        drink = self._dispenser.getDrink(drink_id)
        if drink is None:
            return -1
        measured_w = self.measureSlotWeight(drink_id)
        net_w = max(0.0, measured_w - drink.tare_weight)
        if drink.unit_weight <= 0:
            return 0
        return max(0, round(net_w / drink.unit_weight))

    def verifyStock(self, drink_id: str) -> Dict[str, Any]:
        """
        Cross-checks weight measurement with the product detection sensor.
        Returns a comprehensive diagnostic telemetry record.
        """
        drink = self._dispenser.getDrink(drink_id)
        if drink is None:
            return {"drink_id": drink_id, "error": "Drink not found", "verified_stock": -1}

        measured_w = self.measureSlotWeight(drink_id)
        by_weight = self.countStockByWeight(drink_id)
        by_sensor = self.detectProductCount(drink_id)

        # Cross-verification
        is_consistent = (by_weight == by_sensor)
        verified_stock = by_sensor if is_consistent else by_weight

        # Check if weight matches theoretical expected weight within tolerance
        expected_w = (verified_stock * drink.unit_weight) + drink.tare_weight
        weight_diff = abs(measured_w - expected_w)
        weight_ok = weight_diff <= self._tolerance_grams

        status = "OK" if (is_consistent and weight_ok) else (
            "DISCREPANCY_ALERT" if not is_consistent else "WEIGHT_VARIANCE"
        )

        return {
            "drink_id": drink.drink_id,
            "name": drink.name,
            "slot_num": getattr(drink, "slot_num", "--"),
            "measured_weight_g": round(measured_w, 1),
            "expected_weight_g": round(expected_w, 1),
            "stock_by_weight": by_weight,
            "stock_by_sensor": by_sensor,
            "verified_stock": verified_stock,
            "is_consistent": is_consistent,
            "status": status,
        }

    def syncStockFromSensors(self, drink_id: str) -> int:
        """
        Updates the internal Drink object stock based on dual-sensor verification.
        """
        telem = self.verifyStock(drink_id)
        verified = telem.get("verified_stock", -1)
        if verified >= 0:
            drink = self._dispenser.getDrink(drink_id)
            if drink:
                drink.stock = verified
        return verified

    def getAllTelemetry(self) -> List[Dict[str, Any]]:
        """
        Gathers dual-sensor telemetry across all slots in the dispenser.
        """
        return [self.verifyStock(d.drink_id) for d in self._dispenser._slots]

    # ------------------------------------------------------------------
    # Public UML Methods
    # ------------------------------------------------------------------

    def checkStock(self, drinkId: str) -> bool:
        """
        Check whether a drink's dual-sensor stock is above the low-stock threshold.

        :param drinkId: The unique identifier of the drink to check.
        :return: True if stock is sufficient (above lowStockLevel),
                 False if stock is low or the drink does not exist.
        """
        stock = self.getStock(drinkId)
        if stock == -1:
            print(f"[StockSensor] Drink '{drinkId}' not found.")
            return False

        if stock <= self._low_stock_level:
            print(
                f"[StockSensor] ⚠️ LOW STOCK alert — '{drinkId}': "
                f"{stock} unit(s) remaining (threshold: {self._low_stock_level})."
            )
            return False

        print(f"[StockSensor] '{drinkId}' stock OK — {stock} unit(s) remaining.")
        return True

    def getStock(self, drinkId: str) -> int:
        """
        Return the current dual-sensor verified stock count for a given drink.

        :param drinkId: The unique identifier of the drink.
        :return: Current stock as an integer, or -1 if the drink is not found.
        """
        drink = self._dispenser.getDrink(drinkId)
        if drink is None:
            return -1
        # Synchronize and return verified count
        return self.syncStockFromSensors(drinkId)

    def refresh(self) -> None:
        """
        Re-scans all slots in the dispenser via weight scale and optical detection sensors.
        Prints full diagnostic telemetry, flagging any low, empty, or inconsistent slots.
        """
        print("[StockSensor] Refreshing stock levels via weight scale and optical sensors...")
        for drink in self._dispenser._slots:
            telem = self.verifyStock(drink.drink_id)
            stock = telem["verified_stock"]
            weight_g = telem["measured_weight_g"]
            sensor_cnt = telem["stock_by_sensor"]

            if not telem["is_consistent"]:
                status = f"⚠️ SENSOR MISMATCH (Weight: {telem['stock_by_weight']}, Sensor: {sensor_cnt})"
            elif stock == 0:
                status = f"❌ OUT OF STOCK ({weight_g}g)"
            elif stock <= self._low_stock_level:
                status = f"⚠️ LOW ({stock} cans | {weight_g}g)"
            else:
                status = f"✅ OK ({stock} cans | {weight_g}g)"

            print(f"  {drink.drink_id:<12} {drink.name:<20} {status}")
        print("[StockSensor] Dual-sensor refresh complete.")


class LoyaltyAccount:
    """
    Represents a registered loyalty programme member.

    Attributes:
        cardId:     Unique identifier on the physical loyalty card.
        memberName: Full name of the account holder.
        active:     Whether the account is currently active.
    """

    def __init__(self, card_id: str, member_name: str, active: bool = True):
        self._card_id: str = card_id
        self._member_name: str = member_name
        self._active: bool = active

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def isValid(self) -> bool:
        """
        Check whether this loyalty account is valid (active).

        :return: True if the account is active, False otherwise.
        """
        return self._active

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def card_id(self) -> str:
        return self._card_id

    @property
    def cardId(self) -> str:
        """Alias for UML attribute 'cardId'."""
        return self._card_id

    @property
    def member_name(self) -> str:
        return self._member_name

    @property
    def memberName(self) -> str:
        """Alias for UML attribute 'memberName'."""
        return self._member_name

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        self._active = bool(value)

    def __repr__(self) -> str:
        status = "active" if self._active else "inactive"
        return f"LoyaltyAccount(card='{self._card_id}', member='{self._member_name}', {status})"


class LoyaltyScanner:
    """
    Scans loyalty cards against a registered list of LoyaltyAccounts
    and provides the applicable discount rate for valid members.

    Uses LoyaltyAccount to validate card identity and account status.
    """

    # Default discount rate applied to valid loyalty card holders (10%)
    DEFAULT_DISCOUNT_RATE: float = 0.10

    def __init__(self, accounts: List[LoyaltyAccount], discount_rate: float = DEFAULT_DISCOUNT_RATE):
        """
        :param accounts:      List of registered LoyaltyAccount objects.
        :param discount_rate: Fractional discount applied to valid members
                              (e.g. 0.10 = 10%). Defaults to 10%.
        """
        self._accounts: List[LoyaltyAccount] = accounts
        self._discount_rate: float = discount_rate
        self._last_scanned: Optional[LoyaltyAccount] = None

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def scan(self, cardId: str) -> bool:
        """
        Scan a loyalty card and validate it against the registered accounts.

        :param cardId: The card identifier to look up.
        :return: True if the card belongs to an active account, False otherwise.
        """
        self._last_scanned = None

        for account in self._accounts:
            if account.card_id == cardId:
                if account.isValid():
                    self._last_scanned = account
                    print(
                        f"[LoyaltyScanner] Card '{cardId}' accepted — "
                        f"welcome, {account.member_name}! "
                        f"Discount: {self._discount_rate * 100:.0f}%"
                    )
                    return True
                else:
                    print(f"[LoyaltyScanner] Card '{cardId}' found but account is inactive.")
                    return False

        print(f"[LoyaltyScanner] Card '{cardId}' not recognised.")
        return False

    def getDiscountRate(self) -> float:
        """
        Return the discount rate applied to valid loyalty card holders.

        :return: Discount as a float (e.g. 0.10 for 10%).
        """
        return self._discount_rate

    @property
    def accounts(self) -> List[LoyaltyAccount]:
        """Return the list of registered accounts."""
        return self._accounts

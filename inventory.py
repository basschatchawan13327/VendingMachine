from typing import List, Optional


class Drink:
    """
    Represents a drink product available in the vending machine.

    Attributes:
        drink_id: Unique identifier used as catalogue key (e.g. 'COLA').
        name:     Human-readable name shown on the display.
        price:    Price of the drink in pence.
        stock:    Number of cans/bottles currently available in the machine.
    """

    def __init__(self, drink_id: str, name: str, price: int, stock: int = 10):
        self.drink_id = drink_id
        self._name: str = name
        self._price: int = price
        self._stock: int = stock

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

    # ------------------------------------------------------------------
    # Properties (read-only access to private attributes)
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

    def __repr__(self) -> str:
        return (
            f"Drink(id='{self.drink_id}', name='{self._name}', "
            f"price={self._price}p, stock={self._stock})"
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


class StockSensor:
    """
    Monitors drink stock levels in the vending machine.
    Raises low-stock alerts when a drink's remaining quantity
    falls at or below the configured lowStockLevel threshold.
    """

    def __init__(self, dispenser: DrinkDispenser, low_stock_level: int = 3):
        """
        :param dispenser:       The DrinkDispenser to read stock data from.
        :param low_stock_level: Threshold at or below which a drink is
                                considered low-stock. Defaults to 3.
        """
        self._dispenser: DrinkDispenser = dispenser
        self._low_stock_level: int = low_stock_level

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def checkStock(self, drinkId: str) -> bool:
        """
        Check whether a drink's stock is above the low-stock threshold.

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
        Return the current stock count for a given drink.

        :param drinkId: The unique identifier of the drink.
        :return: Current stock as an integer, or -1 if the drink is not found.
        """
        drink = self._dispenser.getDrink(drinkId)
        if drink is None:
            return -1
        return drink.stock

    def refresh(self) -> None:
        """
        Re-scan all slots in the dispenser and print the current
        stock status for every drink, flagging any that are low or empty.
        """
        print("[StockSensor] Refreshing stock levels...")
        for drink in self._dispenser._slots:
            stock = drink.stock
            if stock == 0:
                status = "❌ OUT OF STOCK"
            elif stock <= self._low_stock_level:
                status = f"⚠️  LOW ({stock})"
            else:
                status = f"✅ OK ({stock})"
            print(f"  {drink.drink_id:<10} {drink.name:<20} {status}")
        print("[StockSensor] Refresh complete.")


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

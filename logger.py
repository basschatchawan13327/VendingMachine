from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class TransactionRecord:
    """
    Represents a single vending machine transaction entry.

    Attributes:
        timestamp:  The date/time the transaction was recorded.
        drinkName:  Name of the drink selected in this transaction.
        amountPaid: The amount paid by the customer (in pence).
        status:     Outcome of the transaction (e.g. 'SUCCESS', 'FAILED',
                    'CANCELLED', 'TIMEOUT').
    """
    drinkName: str
    amountPaid: int
    status: str
    timestamp: datetime = field(default_factory=datetime.now)

    def toString(self) -> str:
        """
        Return a human-readable summary of this transaction record.

        :return: Formatted string with timestamp, drink, amount and status.
        """
        return (
            f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] "
            f"drink='{self.drinkName}' "
            f"amount={self.amountPaid}p "
            f"status={self.status}"
        )

    def __str__(self) -> str:
        return self.toString()


class Logger:
    """
    Records vending machine transactions and provides a history log.

    Each call to recordTransaction() appends a TransactionRecord to
    the internal list, preserving a full audit trail for the session.
    """

    def __init__(self):
        self._records: List[TransactionRecord] = []

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def recordTransaction(self, status: str, amount: int, drink_name: str = "") -> None:
        """
        Append a new transaction entry to the log.

        :param status:     The outcome of the transaction
                           (e.g. 'SUCCESS', 'FAILED', 'CANCELLED').
        :param amount:     The transaction amount in pence.
        :param drink_name: Name of the drink involved in the transaction.
        """
        record = TransactionRecord(drinkName=drink_name, amountPaid=amount, status=status)
        self._records.append(record)
        print(f"[Logger] Recorded transaction — {record.toString()}")

    def getHistory(self) -> List[TransactionRecord]:
        """
        Return all recorded transactions in chronological order.

        :return: A list of TransactionRecord objects.
        """
        return list(self._records)


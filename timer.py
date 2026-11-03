import time


class TransactionTimer:
    """
    Tracks the duration of a vending machine transaction and detects
    when the configured timeout has been exceeded.

    Typical usage:
        timer = TransactionTimer(timeout_seconds=30)
        timer.start()
        ...
        if timer.hasExpired():
            controller.onTimeout()
        timer.stop()
    """

    def __init__(self, timeout_seconds: int = 30):
        """
        :param timeout_seconds: Number of seconds before the transaction
                                is considered timed out. Defaults to 30 s.
        """
        self._timeout_seconds: int = timeout_seconds
        self._running: bool = False
        self._start_time: float | None = None

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start (or restart) the transaction timer.
        Records the current monotonic time as the start reference.
        """
        self._start_time = time.monotonic()
        self._running = True
        print(f"[TransactionTimer] Started — timeout in {self._timeout_seconds}s.")

    def stop(self) -> None:
        """
        Stop the timer and clear the start reference.
        After calling stop(), hasExpired() will always return False.
        """
        self._running = False
        self._start_time = None
        print("[TransactionTimer] Stopped.")

    def hasExpired(self) -> bool:
        """
        Check whether the timeout period has elapsed since start() was called.

        :return: True if the timer is running and the elapsed time exceeds
                 timeoutSeconds, False otherwise.
        """
        if not self._running or self._start_time is None:
            return False

        elapsed = time.monotonic() - self._start_time
        expired = elapsed >= self._timeout_seconds

        if expired:
            print(
                f"[TransactionTimer] Expired — "
                f"{elapsed:.1f}s elapsed (limit: {self._timeout_seconds}s)."
            )
        return expired


"""
Three-state Circuit Breaker for resilient cloud provider routing and recovery.
States: CLOSED (normal), OPEN (cloud bypassed), HALF_OPEN (probing recovery).
"""
import time
import logging
import threading
from typing import Optional, Callable
from .schemas import CircuitState

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """Manages failure tracking and recovery state for Cloud AI Provider."""

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_success_threshold: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_success_threshold = half_open_success_threshold
        self._lock = threading.Lock()

        self.state: CircuitState = CircuitState.CLOSED
        self.consecutive_failures: int = 0
        self.consecutive_successes: int = 0
        self.last_state_change: float = time.time()
        self.last_failure_time: float = 0.0

    def can_attempt_cloud(self) -> bool:
        """Evaluate whether cloud requests should be dispatched based on current state."""
        with self._lock:
            now = time.time()
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                if now - self.last_state_change >= self.recovery_timeout:
                    logger.info(f"CircuitBreaker: Recovery timeout ({self.recovery_timeout}s) expired. Transitioning OPEN -> HALF_OPEN.")
                    self.state = CircuitState.HALF_OPEN
                    self.consecutive_successes = 0
                    self.last_state_change = now
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                # Allow canary trial requests
                return True

            return False

    def record_success(self) -> None:
        """Register a successful cloud interaction."""
        with self._lock:
            now = time.time()
            self.consecutive_failures = 0
            if self.state == CircuitState.HALF_OPEN:
                self.consecutive_successes += 1
                logger.info(f"CircuitBreaker: Canary success #{self.consecutive_successes}/{self.half_open_success_threshold}.")
                if self.consecutive_successes >= self.half_open_success_threshold:
                    logger.info("CircuitBreaker: Success threshold reached. Transitioning HALF_OPEN -> CLOSED (Full Cloud Recovery).")
                    self.state = CircuitState.CLOSED
                    self.consecutive_successes = 0
                    self.last_state_change = now
            elif self.state == CircuitState.CLOSED:
                self.consecutive_successes += 1

    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Register a cloud communication failure."""
        with self._lock:
            now = time.time()
            self.last_failure_time = now
            self.consecutive_failures += 1
            self.consecutive_successes = 0

            if self.state == CircuitState.CLOSED:
                logger.warning(f"CircuitBreaker: Recorded cloud failure #{self.consecutive_failures}/{self.failure_threshold}: {error}")
                if self.consecutive_failures >= self.failure_threshold:
                    logger.error(f"CircuitBreaker: Failure threshold reached. Transitioning CLOSED -> OPEN (Bypassing Cloud for {self.recovery_timeout}s).")
                    self.state = CircuitState.OPEN
                    self.last_state_change = now
            elif self.state == CircuitState.HALF_OPEN:
                logger.error(f"CircuitBreaker: Canary request failed during HALF_OPEN. Tripping back to OPEN: {error}")
                self.state = CircuitState.OPEN
                self.last_state_change = now

    def reset(self) -> None:
        """Explicitly reset circuit breaker to healthy CLOSED state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.consecutive_failures = 0
            self.consecutive_successes = 0
            self.last_state_change = time.time()

    def force_state(self, new_state: CircuitState) -> None:
        """Force circuit breaker to a specific state for testing."""
        with self._lock:
            self.state = new_state
            self.last_state_change = time.time()

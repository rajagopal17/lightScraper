import logging
import time
from functools import wraps

from . import config

logger = logging.getLogger(__name__)


def with_retry(func=None, *, max_attempts: int | None = None, base_delay: float | None = None):
    """Retries a flaky step with exponential backoff. Re-raises the last
    exception if all attempts fail, so the caller can treat it as a genuine
    failure.

    Usable as a plain decorator (`@with_retry`, using the browser-step
    defaults from config) or parameterized (`with_retry(max_attempts=2,
    base_delay=1)`), which the OpenAI call uses to keep retries -- and the
    token spend they cost -- much smaller than the free browser retries.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            attempts = max_attempts if max_attempts is not None else config.RETRY_MAX_ATTEMPTS
            delay = base_delay if base_delay is not None else config.RETRY_BASE_DELAY_SECONDS
            last_exc = None
            for attempt in range(1, attempts + 1):
                try:
                    return f(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 - deliberately broad, retried
                    last_exc = exc
                    logger.warning(
                        "%s failed (attempt %d/%d): %s",
                        f.__name__,
                        attempt,
                        attempts,
                        exc,
                    )
                    if attempt < attempts:
                        time.sleep(delay * (2 ** (attempt - 1)))
            raise last_exc

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator

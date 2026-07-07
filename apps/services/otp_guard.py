"""Cache-backed guards for the Atmos OTP payment flow.

All state lives in Django's cache (see ``CACHES`` in settings). These guards make
the OTP-send endpoint idempotent (double-tap / retry safe), rate-limit sends and
verifications, and lock a user out after too many wrong codes.

IMPORTANT (deploy): with the default ``LocMemCache`` and several gunicorn
workers these counters/locks are PER-PROCESS, so a duplicate request routed to a
different worker would not see the lock. Use the DB cache or Redis in production
so all workers share one cache. See the deploy notes in the task summary.
"""

import time

from django.core.cache import cache

# ── tunables ─────────────────────────────────────────────────────────────
SEND_LOCK_TTL = 10          # seconds a single in-flight send holds the lock
SEND_MAX = 3                # max OTP sends (initial + resend) per window
SEND_WINDOW = 10 * 60       # 10 minutes
VERIFY_MAX_ATTEMPTS = 5     # wrong OTP tries before a transaction is burned
VERIFY_BLOCK = 10 * 60      # 10 minutes lockout after too many wrong tries
IDEMPOTENT_WINDOW = 60      # reuse a fresh transaction created within 60s
OTP_TTL_SECONDS = 120       # how long an Atmos OTP stays valid (for the UI hint)


def _k(*parts):
    return "otp:" + ":".join(str(p) for p in parts)


# ── in-flight lock (idempotency across double-tap / quick retries) ─────────
def acquire_send_lock(user_id) -> bool:
    """True if we grabbed the lock; False if another send is already running."""
    return cache.add(_k("lock", user_id), 1, timeout=SEND_LOCK_TTL)


def release_send_lock(user_id):
    cache.delete(_k("lock", user_id))


# ── send/resend rate limit: SEND_MAX per SEND_WINDOW ───────────────────────
def send_rate_status(user_id):
    """Return ``(allowed, retry_after)`` without consuming a slot."""
    now = time.time()
    stamps = [t for t in (cache.get(_k("send", user_id)) or []) if t > now - SEND_WINDOW]
    if len(stamps) >= SEND_MAX:
        retry_after = int(SEND_WINDOW - (now - min(stamps))) + 1
        return False, max(retry_after, 1)
    return True, 0


def record_send(user_id):
    """Consume one send slot for the current window."""
    now = time.time()
    key = _k("send", user_id)
    stamps = [t for t in (cache.get(key) or []) if t > now - SEND_WINDOW]
    stamps.append(now)
    cache.set(key, stamps, timeout=SEND_WINDOW)


# ── verify attempts / lockout ──────────────────────────────────────────────
def verify_block_status(user_id):
    """Return ``(blocked, retry_after)`` for OTP verification."""
    until = cache.get(_k("vblock", user_id))
    if until and until > time.time():
        return True, int(until - time.time()) + 1
    return False, 0


def record_wrong_attempt(user_id, payment_id):
    """Count one wrong OTP for this transaction.

    Returns ``(attempts_used, remaining, locked)``. ``locked=True`` means the
    limit was hit: the transaction is burned and the user is temporarily blocked
    from verifying (caller should invalidate the payment and require a new code).
    """
    key = _k("vattempt", payment_id)
    attempts = (cache.get(key) or 0) + 1
    cache.set(key, attempts, timeout=VERIFY_BLOCK)
    if attempts >= VERIFY_MAX_ATTEMPTS:
        cache.set(_k("vblock", user_id), time.time() + VERIFY_BLOCK, timeout=VERIFY_BLOCK)
        cache.delete(key)
        return attempts, 0, True
    return attempts, VERIFY_MAX_ATTEMPTS - attempts, False


def reset_verify_attempts(user_id, payment_id):
    """Clear attempt counter + any lockout (called on a successful payment)."""
    cache.delete(_k("vattempt", payment_id))
    cache.delete(_k("vblock", user_id))

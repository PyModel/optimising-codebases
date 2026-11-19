from uuid import uuid4


def charge(gateway, amount_cents):
    """Submit one charge. The gateway deduplicates requests by idempotency key."""
    for attempt in range(2):
        try:
            return gateway.charge(amount_cents, idempotency_key=uuid4().hex)
        except TimeoutError:
            if attempt == 1:
                raise

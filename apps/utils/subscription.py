def has_active_subscription(user) -> bool:
	sub = getattr(user, 'subscription', None)
	return bool(sub and sub.is_valid)
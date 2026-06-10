import random
import string


def generate_share_token(length: int = 8) -> str:
    """Return a random uppercase-alphanumeric token of the given length."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))

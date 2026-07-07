"""
Atmos payment gateway helpers.

Reference: https://docs.atmos.uz

The only piece needed to *receive* money is the result/callback request that
Atmos POSTs to ATMOS_CALLBACK_URL once a transaction is confirmed. Atmos sends:

    {
        "store_id": "1234",
        "transaction_id": "999",
        "transaction_time": "1700000000000",
        "amount": "5000000",          # in tiyin (1 UZS = 100 tiyin)
        "invoice": "42",              # the reference we passed on create (= Payment.id)
        "sign": "<md5 hash>"
    }

and expects a JSON answer:  {"status": 1, "message": "..."}  on success,
                            {"status": 0, "message": "..."}  on failure.

The signature is:  md5(store_id + transaction_id + invoice + amount + api_key)
"""

import base64
import hashlib
import time

import requests
from django.conf import settings

# Fields that must be present in a callback for us to even try to verify it.
REQUIRED_CALLBACK_KEYS = ('store_id', 'transaction_id', 'account', 'amount', 'sign')


def validate_callback_signature(data: dict, api_key: str) -> bool:
	"""Return True iff the `sign` in `data` matches the expected md5 hash."""
	if not all(key in data for key in REQUIRED_CALLBACK_KEYS):
		return False

	sign_string = "".join((
		str(data['store_id']),
		str(data['transaction_id']),
		str(data['account']),
		str(data['amount']),
		api_key,
	))
	calculated = hashlib.md5(sign_string.encode()).hexdigest()
	return calculated == data['sign']


def callback_response(success: bool, message: str = "") -> dict:
	"""Build the JSON body Atmos expects in the result/callback response."""
	return {
		"status": 1 if success else 0,
		"message": message or ("Success" if success else "Error"),
	}


# ───────────────────────── Merchant API client ─────────────────────────

class AtmosError(Exception):
	"""Raised when the Atmos API returns a non-OK result or fails to respond."""

	def __init__(self, message, code=None):
		super().__init__(message)
		self.code = code
		self.message = message


# ── apply()-error classification ────────────────────────────────────────────
# Our own enum for what went wrong when confirming (apply) a transaction. Only
# WRONG_OTP should consume an OTP attempt; the rest are payment problems whose
# code was fine.
class ApplyError:
	INSUFFICIENT_FUNDS = "insufficient_funds"
	WRONG_OTP = "wrong_otp"
	OTP_EXPIRED = "otp_expired"
	CARD_ERROR = "card_error"
	OTHER = "other"


# Known Atmos result codes → our enum (extend as real codes are confirmed in prod
# logs). Codes are matched first; message text is the fallback.
_ATMOS_CODE_MAP = {
	# e.g. "STPIMS-ERR-098": ApplyError.INSUFFICIENT_FUNDS,
}

# Message-text keywords (RU / UZ / EN), checked in priority order. Insufficient
# funds is checked before generic "card" words because its text also mentions the
# card ("Недостаточно средств на балансе карты").
_MESSAGE_RULES = (
	(ApplyError.INSUFFICIENT_FUNDS, (
		"недостаточно", "yetarli emas", "mablag", "insufficient", "not enough", "balance",
	)),
	(ApplyError.OTP_EXPIRED, (
		"срок", "истек", "истёк", "expired", "muddat", "vaqti", "tugadi", "amal qilish muddati",
	)),
	(ApplyError.WRONG_OTP, (
		"неверный", "неправильн", "wrong", "incorrect", "invalid", "код", "kod",
		"otp", "parol", "sms", "одноразов", "noto'g'ri", "notog'ri",
	)),
	(ApplyError.CARD_ERROR, (
		"карт", "card", "karta", "заблокирован", "blocked", "bloklangan", "expire",
	)),
)


def classify_apply_error(code, message) -> str:
	"""Map an Atmos apply rejection to our ApplyError enum.

	Prefers the Atmos result code when it's a known one; otherwise matches the
	human description text across RU/UZ/EN. Falls back to OTHER.
	"""
	if code is not None:
		mapped = _ATMOS_CODE_MAP.get(str(code).upper())
		if mapped:
			return mapped

	text = (message or "").lower()
	for kind, keywords in _MESSAGE_RULES:
		if any(kw in text for kw in keywords):
			return kind
	return ApplyError.OTHER


class AtmosClient:
	"""Minimal client for the Atmos merchant payment API.

	Card-charge flow (one card, one transaction):
		1. create_transaction(amount_tiyin, account) -> transaction_id
		2. pre_apply(transaction_id, card_number, expiry)  -> sends OTP SMS
		3. apply(transaction_id, otp)                      -> confirms payment

	Config comes from settings (ATMOS_API_URL / ATMOS_CONSUMER_KEY /
	ATMOS_CONSUMER_SECRET / ATMOS_STORE_ID). The async result/callback that
	confirms the charge out-of-band is handled separately by the callback view.
	"""

	def __init__(self, base_url=None, consumer_key=None, consumer_secret=None,
	             store_id=None, language="ru", timeout=30):
		self.base_url = (base_url or settings.ATMOS_API_URL).rstrip("/")
		self.consumer_key = consumer_key or settings.ATMOS_CONSUMER_KEY
		self.consumer_secret = consumer_secret or settings.ATMOS_CONSUMER_SECRET
		self.store_id = store_id or settings.ATMOS_STORE_ID
		self.language = language
		self.timeout = timeout
		self._token = None
		self._token_expires_at = 0

	# ---- auth ----
	def _basic_auth(self):
		raw = f"{self.consumer_key}:{self.consumer_secret}".encode()
		return "Basic " + base64.b64encode(raw).decode()

	def _ensure_token(self):
		if self._token and time.time() < self._token_expires_at:
			return self._token
		try:
			resp = requests.post(
				f"{self.base_url}/token",
				headers={
					"Content-Type": "application/x-www-form-urlencoded",
					"Authorization": self._basic_auth(),
				},
				data={"grant_type": "client_credentials"},
				timeout=self.timeout,
			)
		except requests.RequestException as exc:
			raise AtmosError(f"Atmos token request failed: {exc}")
		if resp.status_code != 200:
			raise AtmosError(f"Atmos auth failed: {resp.text}")
		data = resp.json()
		self._token = data["access_token"]
		# refresh a minute early
		self._token_expires_at = time.time() + int(data.get("expires_in", 3600)) - 60
		return self._token

	# ---- low-level request ----
	def _post(self, endpoint, payload):
		token = self._ensure_token()
		try:
			resp = requests.post(
				f"{self.base_url}{endpoint}",
				headers={
					"Content-Type": "application/json",
					"Authorization": f"Bearer {token}",
				},
				json=payload,
				timeout=self.timeout,
			)
		except requests.RequestException as exc:
			raise AtmosError(f"Atmos request to {endpoint} failed: {exc}")
		try:
			data = resp.json()
		except ValueError:
			raise AtmosError(f"Atmos returned a non-JSON response from {endpoint}: {resp.text}")
		result = data.get("result") or {}
		if result.get("code") != "OK":
			raise AtmosError(result.get("description") or "Atmos error", code=result.get("code"))
		return data

	# ---- API methods ----
	def create_transaction(self, amount_tiyin: int, account: str, details: str = None) -> int:
		"""Create a transaction. Returns the Atmos transaction_id."""
		payload = {
			"amount": int(amount_tiyin),
			"account": str(account),
			"store_id": self.store_id,
			"lang": self.language,
		}
		if details:
			payload["details"] = details
		data = self._post("/merchant/pay/create", payload)
		return data.get("transaction_id")

	def pre_apply(self, transaction_id: int, card_number: str, expiry: str) -> bool:
		"""Send the card to Atmos; this triggers the OTP SMS. `expiry` is YYMM."""
		self._post("/merchant/pay/pre-apply", {
			"transaction_id": transaction_id,
			"card_number": card_number,
			"expiry": expiry,
			"store_id": self.store_id,
		})
		return True

	def apply(self, transaction_id: int, otp: str) -> dict:
		"""Confirm the transaction with the OTP. Returns the full response dict."""
		return self._post("/merchant/pay/apply", {
			"transaction_id": transaction_id,
			"otp": str(otp),
			"store_id": self.store_id,
		})

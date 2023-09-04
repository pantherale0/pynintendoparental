# pylint: disable=line-too-long
"""Static values."""

CLIENT_ID = "54789befb391a838"
GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer-session-token"

REDIRECT_URI = f"npf{CLIENT_ID}://auth"
SCOPE = "openid+user+user.mii+moonUser:administration+moonDevice:create+moonOwnedDevice:administration+moonParentalControlSetting+moonParentalControlSetting:update+moonParentalControlSettingState+moonPairingState+moonSmartDevice:administration+moonDailySummary+moonMonthlySummary"

AUTHORIZE_URL = "https://accounts.nintendo.com/connect/1.0.0/authorize?{}"
SESSION_TOKEN_URL = "https://accounts.nintendo.com/connect/1.0.0/api/session_token"
TOKEN_URL = "https://accounts.nintendo.com/connect/1.0.0/api/token"

RESPONSE_TOKEN_REGEXP = rf"npf{CLIENT_ID}:\/\/auth#session_state=(.*?)&session_token_code=(.*?)&state=(.*)"

ACCOUNT_API_BASE = "https://api.accounts.nintendo.com/2.0.0"
MY_ACCOUNT_ENDPOINT = f"{ACCOUNT_API_BASE}/users/me"

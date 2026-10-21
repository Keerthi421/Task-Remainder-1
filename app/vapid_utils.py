"""Generate and cache VAPID keys for Web Push notifications.

Keys are stored in vapid_keys.json at the project root on first run.
Both the public key (shared with the browser) and the private key
(used by pywebpush to sign push requests) live here.
"""
import base64
import json
import os
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

_KEYS_FILE = "vapid_keys.json"


def _load_or_generate() -> dict:
    if os.path.exists(_KEYS_FILE):
        with open(_KEYS_FILE) as f:
            return json.load(f)
    priv = ec.generate_private_key(ec.SECP256R1())
    pub_bytes = priv.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    priv_pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    data = {
        "private_key": priv_pem,
        "public_key":  base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode(),
    }
    with open(_KEYS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"LOG: VAPID keys generated → {_KEYS_FILE}")
    return data


_keys      = _load_or_generate()
PRIVATE_KEY = _keys["private_key"]   # PEM string for pywebpush
PUBLIC_KEY  = _keys["public_key"]    # base64url string for the browser

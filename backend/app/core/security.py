import hashlib
import os
import secrets
import json
import base64
import time
from typing import Optional, Dict, Any

SALT_SIZE = 16
HASH_ITERATIONS = 100_000

def hash_password(password: str) -> str:
    """Hashes a password securely using PBKDF2 with SHA-256 and unique salt."""
    salt = os.urandom(SALT_SIZE)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        HASH_ITERATIONS
    )
    # Format: salt_hex$key_hex
    return f"{salt.hex()}${key.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password against the stored salt$hash format."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 2:
            return False
        salt = bytes.fromhex(parts[0])
        expected_key = bytes.fromhex(parts[1])
        actual_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            HASH_ITERATIONS
        )
        return secrets.compare_digest(expected_key, actual_key)
    except Exception:
        return False

# Simple secure signed token generator (zero external JWT dependencies)
def create_access_token(data: Dict[str, Any], secret_key: str, expires_delta_seconds: int = 86400 * 7) -> str:
    payload = data.copy()
    payload["exp"] = int(time.time()) + expires_delta_seconds
    payload["iat"] = int(time.time())
    
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    
    signature = hashlib.sha256(f"{header_b64}.{payload_b64}.{secret_key}".encode()).hexdigest()
    return f"{header_b64}.{payload_b64}.{signature}"

def decode_access_token(token: str, secret_key: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            
        header_b64, payload_b64, signature = parts
        
        expected_sig = hashlib.sha256(f"{header_b64}.{payload_b64}.{secret_key}".encode()).hexdigest()
        if not secrets.compare_digest(signature, expected_sig):
            
        # Pad payload base64 if needed
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += "=" * (4 - rem)
            
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()).decode())
        if payload.get("exp", 0) < int(time.time()):
            return None # Expired
            
        return payload
    except Exception:
        
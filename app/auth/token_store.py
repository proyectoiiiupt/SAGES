from datetime import datetime, timedelta

# Simple in-memory token store for recovery codes.
# Maps lowercased email -> { code: str, expires_at: datetime }
_tokens = {}


def set_token(email: str, code: str, minutes: int = 5):
    key = email.lower()
    _tokens[key] = {
        'code': code,
        'expires_at': datetime.utcnow() + timedelta(minutes=minutes),
        'attempts': 0
    }


def verify_token(email: str, code: str) -> bool:
    """Consume and verify token."""
    key = email.lower()
    entry = _tokens.get(key)
    if not entry:
        return False
    if entry['code'] != code:
        return False
    if datetime.utcnow() > entry['expires_at']:
        # expired
        _tokens.pop(key, None)
        return False
    # consume token
    _tokens.pop(key, None)
    return True


def validate_token_attempt(email: str, code: str, max_attempts: int = 3) -> str:
    """Check token validity, increment attempts if incorrect."""
    key = email.lower()
    entry = _tokens.get(key)
    if not entry:
        return 'EXPIRED'
    
    if datetime.utcnow() > entry['expires_at']:
        _tokens.pop(key, None)
        return 'EXPIRED'

    if entry.get('attempts', 0) >= max_attempts:
        _tokens.pop(key, None)
        return 'BLOCKED'

    if entry['code'] != code:
        entry['attempts'] = entry.get('attempts', 0) + 1
        if entry['attempts'] >= max_attempts:
            _tokens.pop(key, None)
            return 'BLOCKED'
        return 'INVALID'

    return 'VALID'


def get_remaining_seconds(email: str) -> int:
    key = email.lower()
    entry = _tokens.get(key)
    if not entry:
        return 0
    remaining = entry['expires_at'] - datetime.utcnow()
    return max(0, int(remaining.total_seconds()))

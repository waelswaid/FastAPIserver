import json
import logging
import time

from fastapi import HTTPException, Request
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 3600

_LUA_SCRIPT = """
local prev_key = KEYS[1]
local curr_key = KEYS[2]
local max_requests = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local window_id = math.floor(now / window)
local window_start = window_id * window
local elapsed = now - window_start
local fraction = elapsed / window

local prev_count = tonumber(redis.call('GET', prev_key) or '0') or 0
local curr_count = tonumber(redis.call('GET', curr_key) or '0') or 0

local weighted = prev_count * (1 - fraction) + curr_count

if weighted >= max_requests then
    local reset_at = window_start + window
    return {0, math.ceil(weighted), reset_at}
end

redis.call('INCR', curr_key)
redis.call('EXPIRE', curr_key, window * 2)

return {1, math.ceil(weighted + 1), window_start + window}
"""


# rate limiter flow
"""
● Client sends: POST /api/auth/login {"email": "user@example.com", "password": "..."}
                                          │                                                                                                  
                                          ▼                                                                                                                  FastAPI sees: Depends(login_limiter)
                Calls: login_limiter(request)  ←── this triggers __call__                                                                    
                                          │                                                                                                  
                                          ▼                                                                                                                        __call__ starts                                                                                                        
                      ─────────────────────────────                                                                                          
                      body_bytes = await request.body()                                                                                                            → b'{"email": "user@example.com", "password": "..."}'
                                          │                                                                                                  
                                          ▼                                                                                                                        _build_client_key(request, body_bytes)
                      → ip = "192.168.1.5"                                                                                                   
                      → use_email_key=True, so parse body                                                                                    
                      → email = "user@example.com"                                                                                                                 → returns "192.168.1.5:user@example.com"                                                                               
                                          │                                                                                                                                            ▼
                      get_redis()                                                                                                            
                      → returns client? continue                                                                                                                   → returns None? return (fail open, request proceeds)
                                          │                                                                                                                                            ▼
                      _redis_keys("192.168.1.5:user@example.com", 1742486520.0)                                                              
                      → window_id = 483468                                                                                                   
                      → prev_id = 483467                                                                                                                           → returns:                                                                                                             
                        "ratelimit:login:483467:192.168.1.5:user@example.com"                                                                
                        "ratelimit:login:483468:192.168.1.5:user@example.com"                                                                
                                          │                                                                                                                                            ▼                                                                                                  
                      r.eval(LUA_SCRIPT, keys, args)                                                                                         
                      → Lua runs atomically on Redis                                                                                         
                      → returns [1, 5, 1742490000]                                                                                           
                         allowed=1, count=5, reset_at=1742490000                                                                             
                                          │                                                                                                                                            ▼                                                                                                  
                      allowed=1 (yes)                                                                                                        
                      → store metadata on request.state
                      → return (request proceeds to route handler)                                                                                                                     │
                                          ▼                                                                                                  
                                route_login_request() runs normally                                                                          
                                                                                                                                                                                                                                                                                          
            ─── OR if allowed=0 ───                                                                                                          

                      allowed=0 (blocked)                                                                                                                          → raise HTTPException(429)
                      → client gets: "Too many requests. Please try again later."                                                            
                        with Retry-After, X-RateLimit-* headers                                                                              
                      → route handler never runs 
"""

class RateLimiter:

    def __init__(self, name: str, max_requests: int, window_seconds: int = WINDOW_SECONDS, use_email_key: bool = False):
        self.name = name
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.use_email_key = use_email_key
        self._script_sha: str | None = None

    # Identifies who's making the request
    def _build_client_key(self, request: Request, body_bytes: bytes) -> str:
        ip = request.client.host if request.client else "unknown"
        if self.use_email_key:
            try:
                data = json.loads(body_bytes)
                email = data.get("email", "")
            except (json.JSONDecodeError, UnicodeDecodeError):
                email = ""
            return f"{ip}:{email}"
        return ip



    # returns keys for the previous and current window
    """
    window_id = int(now // self.window_seconds)

  Divides the timestamp by the window size (3600) and drops the decimal. This gives a number that stays the same for an
  entire hour, then increments:                                                                                                                 
  12:00:00 → 1742486400 // 3600 = 483468                                                                                                     
  12:30:00 → 1742488200 // 3600 = 483468  ← same window                                                                                      
  13:00:00 → 1742490000 // 3600 = 483469  ← new window 
    """
    def _redis_keys(self, client_key: str, now: float) -> tuple[str, str]:
        window_id = int(now // self.window_seconds)
        prev_id = window_id - 1
        prefix = f"ratelimit:{self.name}"
        return f"{prefix}:{prev_id}:{client_key}", f"{prefix}:{window_id}:{client_key}"

    # The actual rate check (runs on every request)
    async def __call__(self, request: Request) -> None:
        """
    Reads the raw request body. 
    Needs await because FastAPI streams the body over the network. 
    This is needed in case _build_client_key needs
    to parse the email from it.
        """
        body_bytes = await request.body()
        client_key = self._build_client_key(request, body_bytes) # Gets the identifier — IP or IP+email.

        r = get_redis()
        if r is None:
            # Fail open — no Redis available
            return

        now = time.time()
        # Builds the two Redis keys for the sliding window.
        prev_key, curr_key = self._redis_keys(client_key, now)

        try:
            result = await r.eval( # Sends the Lua script to Redis to execute atomically
                _LUA_SCRIPT,
                2, # number of keys being passed (prev and curr)
                prev_key,
                curr_key,
                self.max_requests, # argv[1] in lua
                self.window_seconds, # argv[2]
                int(now), #argv[3]
            )

            """
            The Lua script returns three values:
            allowed — 1 (ok) or 0 (blocked)
            count — current weighted request count
            reset_at — timestamp when the window resets
            """
            allowed, count, reset_at = int(result[0]), int(result[1]), int(result[2])

            # Store metadata on request.state for the middleware to pick up
            request.state.rate_limit_limit = self.max_requests
            request.state.rate_limit_remaining = max(0, self.max_requests - count)
            request.state.rate_limit_reset = reset_at

            if not allowed:
                retry_after = max(1, reset_at - int(now))
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again later.",
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(self.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_at),
                    },
                )
        except RedisError:
            logger.warning("Redis error during rate limiting — failing open", exc_info=True)



class AccountLockout:
    def __init__(self):
        self.max_attempts : int = settings.MAX_ATTEMPTS_UNTILL_LOCKOUT
        self.lockout_seconds : int = settings.LOCKOUT_TIME_SECONDS


    async def __call__(self, request : Request):
        body_bytes = await request.body()
        try:
            data = json.loads(body_bytes)
            email = data.get("email")
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if not email:
            return
        r = get_redis()
        if r is None:
            return
        try:
            current_count = await r.get(f"lockout:{email}")
            if current_count is not None and int(current_count) >= self.max_attempts:
                logger.warning("audit: event=account_locked_out email=%s", email)
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again later.",
                    headers={
                        "Retry-After": str(self.lockout_seconds),
                        "X-RateLimit-Limit": str(self.max_attempts),
                        "X-RateLimit-Remaining": "0",
                    },
                )
        except RedisError:
            logger.warning("Redis error during lockout check — failing open", exc_info=True)

    async def record_failure(self, email : str):
        r = get_redis()
        if not r:
            return
        try:
            count = await r.incr(f"lockout:{email}")
            if count == 1:
                await r.expire(f"lockout:{email}", self.lockout_seconds)
        except RedisError:
            return


    async def clear(self, email : str):
        r = get_redis()
        if not r:
            return
        try:
           await r.delete(f"lockout:{email}")
        except RedisError:
            return




# --- Limiter instances ---

forgot_password_limiter = RateLimiter(
    name="forgot_password",
    max_requests=settings.RATE_LIMIT_FORGOT_PASSWORD,
    use_email_key=True,
)
resend_verification_limiter = RateLimiter(
    name="resend_verification",
    max_requests=settings.RATE_LIMIT_RESEND_VERIFICATION,
    use_email_key=True,
)
reset_password_limiter = RateLimiter(
    name="reset_password",
    max_requests=settings.RATE_LIMIT_RESET_PASSWORD,
)
login_limiter = RateLimiter(
    name="login",
    max_requests=settings.RATE_LIMIT_LOGIN,
    use_email_key=True,
)
login_global_limiter = RateLimiter(
    name="login_global",
    max_requests=settings.RATE_LIMIT_LOGIN_GLOBAL,
)
registration_limiter = RateLimiter(
    name="registration",
    max_requests=settings.RATE_LIMIT_REGISTRATION,
)
refresh_limiter = RateLimiter(
    name="refresh",
    max_requests=settings.RATE_LIMIT_REFRESH,
)
verify_email_limiter = RateLimiter(
    name="verify_email",
    max_requests=settings.RATE_LIMIT_VERIFY_EMAIL,
)
validate_reset_code_limiter = RateLimiter(
    name="validate_reset_code",
    max_requests=settings.RATE_LIMIT_VALIDATE_RESET_CODE,
)
change_password_limiter = RateLimiter(
    name="change_password",
    max_requests=settings.RATE_LIMIT_CHANGE_PASSWORD,
)
delete_account_limiter = RateLimiter(
    name="delete_account",
    max_requests=settings.RATE_LIMIT_DELETE_ACCOUNT,
)

lockout_limiter = AccountLockout()
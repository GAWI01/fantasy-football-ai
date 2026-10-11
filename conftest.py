import os

# The per-client API limit (backend/rate_limit.py) would trip on test suites
# that make hundreds of requests from one client; its own tests enable it.
os.environ.setdefault("FPL_AI_RATE_LIMIT_PER_MINUTE", "0")

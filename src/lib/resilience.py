import logging
import httpx
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log, RetryError
from postgrest.exceptions import APIError

# Setup logger
logger = logging.getLogger("resilience")

def retry_with_backoff(retries=3, min_delay=1.0, max_delay=10.0):
    """
    Decorator to retry functions with exponential backoff.
    Catches common network and API errors.
    """
    
    # Define exceptions to retry on
    retry_exceptions = (
        httpx.ConnectTimeout, 
        httpx.ReadTimeout, 
        httpx.ConnectError,
        APIError, # Supabase/Postgrest errors
        ConnectionError, 
        TimeoutError,
        OSError
    )

    return retry(
        stop=stop_after_attempt(retries),
        wait=wait_exponential(multiplier=1, min=min_delay, max=max_delay),
        retry=retry_if_exception_type(retry_exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )

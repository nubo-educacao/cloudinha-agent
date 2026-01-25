import traceback
import functools
import datetime
import asyncio
import inspect
from src.lib.supabase import supabase

def safe_execution(error_type="generic_error", default_return=None, re_raise=False):
    """
    Decorator to safely execute a function (sync, async, or async generator), 
    log errors to Supabase, and optionally return a default value or re-raise.
    
    Args:
        error_type (str): Category of the error (e.g., 'tool_error', 'agent_loop_error').
        default_return (Any): Value to return if an exception occurs (if re_raise is False).
                              Ignored for Async Generators (they just stop iteration).
        re_raise (bool): Whether to re-raise the exception after logging.
    """
    def decorator(func):
        # Capture original signature and annotations to re-apply
        sig = inspect.signature(func)
        
        if inspect.isasyncgenfunction(func):
            @functools.wraps(func)
            async def async_gen_wrapper(*args, **kwargs):
                try:
                    async for item in func(*args, **kwargs):
                        yield item
                except Exception as e:
                    _handle_error(e, func.__name__, error_type, default_return, re_raise)
            
            async_gen_wrapper.__signature__ = sig
            return async_gen_wrapper

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                return _handle_error(e, func.__name__, error_type, default_return, re_raise)
        
        async_wrapper.__signature__ = sig

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return _handle_error(e, func.__name__, error_type, default_return, re_raise)
        
        sync_wrapper.__signature__ = sig

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator

def _handle_error(e, func_name, error_type, default_return, re_raise):
    error_msg = str(e)
    tb = traceback.format_exc()
    print(f"[{error_type}] Error executing {func_name}: {error_msg}")
    print(tb)
    
    try:
        # Log to Supabase 'agent_errors' table
        error_data = {
            "error_type": error_type,
            "function_name": func_name,
            "error_message": error_msg,
            "traceback": tb,
            "timestamp": datetime.datetime.now().isoformat()
        }
        # Fire and forget (or await if async, but this is sync for now)
        # Note: synchronous tools might block on this.
        supabase.table("agent_errors").insert(error_data).execute()
    except Exception as db_e:
        print(f"CRITICAL: Failed to log error to Supabase: {db_e}")
    
    if re_raise:
        raise e
    return default_return

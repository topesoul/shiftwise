# /workspace/shiftwise/subscriptions/middleware.py

import logging
import time
from threading import Thread

from django.core import management
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SubscriptionSyncMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Cache keys for different types of checks
        self.last_sync_key = "last_subscription_sync"
        self.expiration_check_key = "last_expiration_check"

    def __call__(self, request):
        # Handle the current request first
        response = self.get_response(request)

        current_time = time.time()
        
        # Check expired subscriptions more frequently (every 2 hours)
        last_expiration_check = cache.get(self.expiration_check_key)
        if not last_expiration_check or (current_time - last_expiration_check) > 7200:  # 2 hours
            try:
                # Use background thread to prevent blocking the response
                thread = Thread(target=self._run_expiration_check)
                thread.daemon = True
                thread.start()
                
                # Update timestamp immediately (cache for 4 hours)
                cache.set(self.expiration_check_key, current_time, 14400)
                logger.info("Subscription expiration check started in background")
            except Exception as e:
                logger.exception(f"Failed to start subscription expiration check: {e}")

        # Daily full sync check - comparing current time with last sync time
        last_sync = cache.get(self.last_sync_key)
        if not last_sync or (current_time - last_sync) > 86400:  # 24 hours
            try:
                # Use background thread to prevent blocking the response
                thread = Thread(target=self._run_sync_command)
                thread.daemon = True
                thread.start()

                # Update timestamp immediately (cache for 2 days)
                cache.set(self.last_sync_key, current_time, 86400 * 2)
                logger.info("Full subscription sync started in background")
            except Exception as e:
                logger.exception(f"Failed to start subscription sync: {e}")

        return response

    def _run_sync_command(self):
        try:
            # Execute the Django management command for full sync
            management.call_command("sync_all_subscriptions")
            logger.info("Full subscription sync completed")
        except Exception as e:
            logger.exception(f"Subscription sync failed: {e}")
            
    def _run_expiration_check(self):
        try:
            # Only run the expiration check part of the sync
            management.call_command("sync_all_subscriptions", check_expired=True)
            logger.info("Subscription expiration check completed")
        except Exception as e:
            logger.exception(f"Subscription expiration check failed: {e}")

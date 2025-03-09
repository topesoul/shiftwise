# /workspace/shiftwise/subscriptions/middleware.py

import logging
import time
from django.core.cache import cache
from django.core import management
from threading import Thread

logger = logging.getLogger(__name__)

class SubscriptionSyncMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Handle the current request first
        response = self.get_response(request)
        
        # Daily sync check - comparing current time with last sync time
        last_sync = cache.get('last_subscription_sync')
        current_time = time.time()
        
        # Run sync if never run before or more than 24 hours has passed
        if not last_sync or (current_time - last_sync) > 86400:
            try:
                # Use background thread to prevent blocking the response
                thread = Thread(target=self._run_sync_command)
                thread.daemon = True
                thread.start()
                
                # Update timestamp immediately (cache for 2 days)
                cache.set('last_subscription_sync', current_time, 86400 * 2)
                logger.info("Subscription sync started in background")
            except Exception as e:
                logger.exception(f"Failed to start subscription sync: {e}")
        
        return response
    
    def _run_sync_command(self):
        try:
            # Execute the Django management command
            management.call_command('sync_all_subscriptions')
            logger.info("Subscription sync completed")
        except Exception as e:
            logger.exception(f"Subscription sync failed: {e}")
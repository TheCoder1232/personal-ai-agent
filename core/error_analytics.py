# file: core/error_analytics.py

import asyncio
import traceback
import hashlib
import time
import logging
from typing import Dict, Any, Optional, Tuple
from utils.error_reporter import BaseErrorReporter

logger = logging.getLogger(__name__)

class ErrorAnalytics:
    """
    Analyzes error patterns to identify recurring issues and trigger reports.
    
    This class is thread-safe and async-safe.
    """
    
    def __init__(self, config: Dict[str, Any], reporter: BaseErrorReporter):
        self.config = config.get("pattern_analysis", {})
        self.reporter = reporter
        
        # In-memory store for error patterns
        # key = pattern_hash
        # value = { "timestamps": [float], "last_reported": float, "details": dict }
        self.error_patterns: Dict[str, Dict[str, Any]] = {}
        
        # Get settings from config
        self.threshold_count = self.config.get("threshold_count", 5)
        self.threshold_span = self.config.get("threshold_timespan_seconds", 3600)
        self.cooldown = self.config.get("report_cooldown_seconds", 86400)
        
        # Async lock to protect access to self.error_patterns
        self._lock = asyncio.Lock()
        logger.info("ErrorAnalytics service initialized.")

    def _identify_pattern(self, error: Exception, context: Optional[dict] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Identifies a unique, repeatable pattern from an error.
        Returns a (pattern_hash, basic_details) tuple.
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        try:
            # Extract the most relevant stack frame
            tb = traceback.extract_tb(error.__traceback__)
            if not tb:
                # No traceback, use error type and message
                relevant_frame = ("<unknown>", 0, "<unknown_function>")
                pattern_base = f"{error_type}:{error_msg}"
            else:
                # Use the top-most frame (where the error was raised)
                top_frame = tb[-1]
                relevant_frame = (top_frame.filename, top_frame.lineno, top_frame.name)
                # Create a pattern based on Type, File, and Function Name
                pattern_base = f"{error_type}:{relevant_frame[0]}:{relevant_frame[2]}"

            # Hash the pattern string for a stable key
            pattern_hash = hashlib.md5(pattern_base.encode('utf-8')).hexdigest()
            
            details = {
                "error_type": error_type,
                "error_message": error_msg,
                "file": relevant_frame[0],
                "line": relevant_frame[1],
                "function": relevant_frame[2],
                "context": context or {},
                "full_traceback": traceback.format_exc() # For the report
            }
            return pattern_hash, details

        except Exception as e:
            # Fallback for any error during analysis
            logger.warning(f"Error during error pattern analysis: {e}")
            pattern_base = f"{error_type}:{error_msg}"
            pattern_hash = hashlib.md5(pattern_base.encode('utf-8')).hexdigest()
            details = {"error_type": error_type, "error_message": error_msg, "context": f"Analysis Error: {e}"}
            return pattern_hash, details

    async def analyze_error(self, error: Exception, context: Optional[dict] = None):
        """
        Analyzes an error, logs its pattern, and triggers a report if it's
        a recurring issue.
        """
        pattern_hash, details = self._identify_pattern(error, context)
        now = time.time()
        
        reporter_task = None
        
        async with self._lock:
            if pattern_hash not in self.error_patterns:
                self.error_patterns[pattern_hash] = {
                    "timestamps": [now],
                    "last_reported": 0.0,
                    "details": details  # Store details from first occurrence
                }
                return  # Not recurring yet

            # Update pattern info
            pattern_data = self.error_patterns[pattern_hash]
            pattern_data["last_seen"] = now
            pattern_data["timestamps"].append(now)
            
            # Prune old timestamps that are outside the analysis window
            cutoff_time = now - self.threshold_span
            pattern_data["timestamps"] = [t for t in pattern_data["timestamps"] if t > cutoff_time]
            
            # Check if thresholds are met
            is_recurring = len(pattern_data["timestamps"]) >= self.threshold_count
            is_on_cooldown = (now - pattern_data.get("last_reported", 0)) < self.cooldown
            
            if is_recurring and not is_on_cooldown:
                logger.info(f"Recurring error pattern detected: {pattern_hash}. Triggering report.")
                # It's a problem! Report it.
                pattern_data["last_reported"] = now
                
                # Prepare details for the report
                report_details = pattern_data["details"] # Use details from first occurrence
                report_details["count_in_timespan"] = len(pattern_data["timestamps"])
                report_details["timespan_seconds"] = self.threshold_span
                
                # We release the lock before calling the reporter
                # to avoid blocking other analyses during I/O.
                reporter_task = self.reporter.report_issue(pattern_hash, report_details)
        
        # Run the (potentially slow) reporting I/O outside the lock
        if reporter_task:
            # Run as a background task so it doesn't block the caller
            asyncio.create_task(reporter_task)
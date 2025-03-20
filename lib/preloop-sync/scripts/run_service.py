#!/usr/bin/env python
"""
Script to run the SpaceSync tracker update service.

This script starts the tracker update service manager,
which creates update services for all active trackers
in the database.
"""

import sys
import time
import signal
import argparse
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from spacesync.config import logger, SERVICE_POLL_INTERVAL
from spacesync.services.manager import TrackerUpdateServiceManager
from spacemodels.db.session import get_db_session


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the SpaceSync tracker update service."
    )
    parser.add_argument(
        "--foreground", 
        action="store_true",
        help="Run in foreground (don't daemonize)"
    )
    parser.add_argument(
        "--reload-interval", 
        type=int, 
        default=300,
        help="Interval (in seconds) to reload tracker list"
    )
    parser.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level"
    )
    
    return parser.parse_args()


def setup_logging(log_level):
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def main():
    """Run the service."""
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    
    # Create database session
    db = next(get_db_session())
    
    # Create and start service manager
    manager = TrackerUpdateServiceManager(
        db=db,
        reload_interval=args.reload_interval
    )
    manager.start()
    
    logger.info("Tracker update service started")
    
    # Keep main thread alive if running in foreground
    if args.foreground:
        try:
            while manager.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down...")
            manager.stop()


if __name__ == "__main__":
    sys.exit(main())

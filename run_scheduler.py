#!/usr/bin/env python3
"""
Local Scheduler — Runs the ingestion pipeline with comprehensive logging.

This script triggers the full ingestion pipeline (Phase 4.0-4.3) locally
and logs all activities to a file for tracking and debugging.

Usage:
    python3 run_scheduler.py
"""

import logging
import os
import sys
from datetime import datetime, timezone

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# Configure logging to both console and file
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(
    LOG_DIR,
    f"ingestion_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.log"
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Run the ingestion pipeline with comprehensive logging."""
    logger.info("=" * 60)
    logger.info("Starting local scheduler for ingestion pipeline")
    logger.info("=" * 60)
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"Environment variables loaded from .env")
    
    # Check required environment variables
    required_vars = ["CHROMA_API_KEY", "CHROMA_TENANT", "CHROMA_DATABASE"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please ensure these are set in your .env file")
        sys.exit(1)
    
    logger.info("All required environment variables are present")
    logger.info("CHROMA_API_KEY: ✓")
    logger.info(f"CHROMA_TENANT: {os.getenv('CHROMA_TENANT')}")
    logger.info(f"CHROMA_DATABASE: {os.getenv('CHROMA_DATABASE')}")
    
    try:
        # Import and run the pipeline
        logger.info("Importing ingestion pipeline...")
        from src.ingestion.run_pipeline import main as run_pipeline
        
        logger.info("Starting ingestion pipeline...")
        run_pipeline()
        
        logger.info("=" * 60)
        logger.info("Ingestion pipeline completed successfully")
        logger.info("=" * 60)
        logger.info(f"Full log available at: {LOG_FILE}")
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"Ingestion pipeline failed with error: {e}")
        logger.error("=" * 60)
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Main entry point for the Coventry University Research Publications Crawler.
"""

import sys
import traceback
from pathlib import Path
import signal
import argparse

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.crawler import CoventryPublicationsCrawler
from src.utils import setup_logging
from config.settings import LOG_FILE, API_ENDPOINT


def main():
    """Main function to run the crawler."""
    try:
        # Prevent BrokenPipeError noise when piping output
        try:
            signal.signal(signal.SIGPIPE, signal.SIG_DFL)
        except Exception:
            pass
        
        # CLI args
        parser = argparse.ArgumentParser(description="Coventry Publications Crawler")
        parser.add_argument("--save-csv", action="store_true", help="Enable CSV saving to data/publications.csv (development mode)")
        args = parser.parse_args()
        
        # Setup logging
        setup_logging()
        
        # Create crawler instance
        crawler = CoventryPublicationsCrawler(save_csv=args.save_csv)
        
        # Run the crawler
        crawler.run()
        
        print(f"\nCrawling completed successfully!")
        print(f"Results sent to API: {API_ENDPOINT}")
        print(f"Logs saved to: {LOG_FILE}")
        
    except KeyboardInterrupt:
        print("\nCrawling interrupted by user")
        sys.exit(1)
        
    except Exception as e:
        print(f"\nCrawling failed with error: {e}")
        print(f"Check the log file for details: {LOG_FILE}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Main entry point for the Coventry University Research Publications Crawler.
"""

import sys
import traceback
from pathlib import Path
import signal
import argparse
from datetime import datetime

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.crawler import CoventryPublicationsCrawler
from src.utils import setup_logging
from config.settings import LOG_FILE, API_ENDPOINT


def main():
    """Main function to run the crawler."""
    program_start_time = datetime.now()
    program_start_timestamp = program_start_time.strftime("%Y-%m-%d %H:%M:%S")
    
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
        
        print(f"\n{'='*60}")
        print(f"COVENTRY UNIVERSITY PUBLICATIONS CRAWLER")
        print(f"{'='*60}")
        print(f"Program Start Time: {program_start_timestamp}")
        print(f"CSV Save Mode: {'Enabled' if args.save_csv else 'Disabled'}")
        print(f"{'='*60}")
        
        # Setup logging
        setup_logging()
        
        # Create crawler instance
        crawler = CoventryPublicationsCrawler(save_csv=args.save_csv)
        
        # Run the crawler
        crawler.run()
        
        # Calculate total program time
        program_end_time = datetime.now()
        program_end_timestamp = program_end_time.strftime("%Y-%m-%d %H:%M:%S")
        program_total_duration = program_end_time - program_start_time
        
        print(f"\n{'='*60}")
        print(f"PROGRAM EXECUTION SUMMARY")
        print(f"{'='*60}")
        print(f"Program Start: {program_start_timestamp}")
        print(f"Program End: {program_end_timestamp}")
        print(f"Total Program Duration: {program_total_duration}")
        print(f"Total Program Duration (seconds): {program_total_duration.total_seconds():.2f}")
        print(f"Results sent to API: {API_ENDPOINT}")
        print(f"Logs saved to: {LOG_FILE}")
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        program_end_time = datetime.now()
        program_end_timestamp = program_end_time.strftime("%Y-%m-%d %H:%M:%S")
        program_total_duration = program_end_time - program_start_time
        
        print(f"\n{'='*60}")
        print(f"PROGRAM INTERRUPTED BY USER")
        print(f"{'='*60}")
        print(f"Program Start: {program_start_timestamp}")
        print(f"Program End: {program_end_timestamp}")
        print(f"Duration before interruption: {program_total_duration}")
        print(f"{'='*60}")
        
        sys.exit(1)
        
    except Exception as e:
        program_end_time = datetime.now()
        program_end_timestamp = program_end_time.strftime("%Y-%m-%d %H:%M:%S")
        program_total_duration = program_end_time - program_start_time
        
        print(f"\n{'='*60}")
        print(f"PROGRAM FAILED")
        print(f"{'='*60}")
        print(f"Program Start: {program_start_timestamp}")
        print(f"Program End: {program_end_timestamp}")
        print(f"Duration before failure: {program_total_duration}")
        print(f"Error: {e}")
        print(f"Check the log file for details: {LOG_FILE}")
        print(f"{'='*60}")
        
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

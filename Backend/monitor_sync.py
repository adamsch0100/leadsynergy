#!/usr/bin/env python3
"""
Monitor the force sync progress and provide periodic updates
"""
import sys
import os
import time
from datetime import datetime

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_latest_log_lines(log_file, n=5):
    """Get last N lines from log file"""
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            return lines[-n:] if lines else []
    except FileNotFoundError:
        return []

def extract_progress(log_lines):
    """Extract current progress from log lines"""
    for line in reversed(log_lines):
        if '[LEAD' in line and 'Processing:' in line:
            # Extract lead number
            if '[LEAD ' in line:
                parts = line.split('[LEAD ')[1].split(']')[0]
                if '/' in parts:
                    current, total = parts.split('/')
                    return int(current), int(total)
    return None, None

def main():
    log_file = 'force_sync_output.log'
    check_interval = 60  # Check every 60 seconds

    print("="*80)
    print("SYNC MONITOR - Tracking your lead updates")
    print("="*80)
    print(f"Started monitoring at: {datetime.now().strftime('%I:%M %p')}")
    print(f"Log file: {log_file}")
    print()
    print("Press Ctrl+C to stop monitoring (sync will continue in background)")
    print("-"*80)
    print()

    last_progress = None
    updates_count = 0

    try:
        while True:
            # Get recent log lines
            log_lines = get_latest_log_lines(log_file, 20)

            # Extract progress
            current, total = extract_progress(log_lines)

            if current and total:
                progress = (current / total) * 100

                # Only print if progress changed
                if last_progress != (current, total):
                    timestamp = datetime.now().strftime('%I:%M %p')
                    print(f"[{timestamp}] Lead {current}/{total} ({progress:.1f}% complete)")

                    # Check for completion
                    if current == total:
                        print()
                        print("="*80)
                        print("SOURCE COMPLETE!")
                        print("Moving to next source...")
                        print("="*80)
                        print()

                    last_progress = (current, total)
                    updates_count += 1

            # Check for final completion
            recent_text = ''.join(log_lines)
            if 'SYNC COMPLETE - SUMMARY' in recent_text or 'Completed at:' in recent_text:
                print()
                print("="*80)
                print("ALL SOURCES COMPLETE!")
                print("="*80)
                print()

                # Show summary
                print("Final results:")
                summary_lines = get_latest_log_lines(log_file, 30)
                for line in summary_lines:
                    if 'Total leads' in line or 'OK ' in line or 'ERROR' in line or 'WARNING' in line:
                        print(f"  {line.strip()}")

                break

            # Wait before next check
            time.sleep(check_interval)

    except KeyboardInterrupt:
        print()
        print("-"*80)
        print("Monitoring stopped (sync continues in background)")
        print(f"Check {log_file} for progress")
        print("-"*80)
        return

if __name__ == "__main__":
    main()

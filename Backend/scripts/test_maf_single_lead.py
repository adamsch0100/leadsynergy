#!/usr/bin/env python3
"""Test MAF date setting with a single lead"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from app.referral_scrapers.my_agent_finder.my_agent_finder_service import MyAgentFinderService

# Organization ID
ORG_ID = "cfde8fec-3b87-4558-b20f-5fe25fdcf149"

# Configuration
NURTURE_DAYS_OFFSET = 180  # 6 months

# Just one test lead
TEST_LEAD = {"name": "Mark Pelletier", "uuid": "c0c4fbbc-157e-11f0-9779-41743377c0e0"}


def main():
    print("=" * 60)
    print("TEST MAF SINGLE LEAD DATE SETTING")
    print("=" * 60)

    # Calculate target date
    future_date = datetime.now() + timedelta(days=NURTURE_DAYS_OFFSET)
    target_date_str = future_date.strftime("%m/%d/%Y")

    print(f"\n[CONFIG] Target date: {target_date_str} ({NURTURE_DAYS_OFFSET} days out)")

    # Initialize service
    service = MyAgentFinderService(
        nurture_days_offset=NURTURE_DAYS_OFFSET,
        organization_id=ORG_ID
    )

    try:
        print("\n[STEP 1] Logging in...")
        if not service.login():
            print("[ERROR] Login failed!")
            return
        print("[OK] Login successful!")

        lead = TEST_LEAD
        driver = service.driver_service.driver
        wis = service.wis

        print(f"\n[STEP 2] Processing {lead['name']}...")

        # Navigate to lead's page
        url = f"https://app.myagentfinder.com/opp/{lead['uuid']}"
        print(f"  Navigating to: {url}")
        driver.get(url)
        wis.human_delay(3, 4)

        # Scroll to Keep Us Informed section
        try:
            keep_informed = driver.find_element(By.XPATH, "//*[contains(text(), 'Keep Us Informed')]")
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", keep_informed)
            wis.human_delay(1, 2)
        except:
            driver.execute_script("window.scrollBy(0, 300);")
            wis.human_delay(1, 2)

        # STEP 1: Select nurture status
        print(f"  Step 1: Selecting nurture status...")
        nurture_status = "I'm nurturing this client (long term)"
        status_selected = service._select_status_for_overdue(nurture_status)
        if status_selected:
            print(f"  [OK] Status selected")
        else:
            print(f"  [WARN] Status selection may have failed")
        wis.human_delay(1, 2)

        # STEP 2: Add detail note
        print(f"  Step 2: Adding detail note...")
        service._add_detail_for_update()
        print(f"  [OK] Detail added")
        wis.human_delay(0.5, 1)

        # STEP 3: Set date
        print(f"  Step 3: Setting date to {target_date_str}...")
        date_set = service._set_overdue_lead_date(target_date_str)
        if date_set:
            print(f"  [OK] Date set to {target_date_str}")
        else:
            print(f"  [WARN] Date may not have been set correctly")

        # Take final screenshot before clicking Update
        service._take_screenshot("test_before_update")

        # STEP 4: Click Update button
        print(f"  Step 4: Clicking Update...")
        update_clicked = service._click_update_button()
        if update_clicked:
            print(f"  [SUCCESS] {lead['name']} updated!")
        else:
            print(f"  [FAILED] Could not click Update")

        # Take screenshot after update
        wis.human_delay(2, 3)
        service._take_screenshot("test_after_update")

        print("\n[DONE] Check screenshots to verify date was set correctly")

    finally:
        # Auto-close after a brief pause
        import time
        time.sleep(2)
        service.close()


if __name__ == "__main__":
    main()

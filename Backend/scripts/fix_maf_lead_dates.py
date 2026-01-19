#!/usr/bin/env python3
"""
Fix MyAgentFinder Lead Dates - Targeted Script
Uses the service's _set_overdue_lead_date method which has proper date-finding logic.
Order: Select status → Add detail → Set date LAST → Click Update
"""

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

# The 14 leads that need to be fixed
LEADS_TO_FIX = [
    {"name": "Mark Pelletier", "uuid": "c0c4fbbc-157e-11f0-9779-41743377c0e0"},
    {"name": "Brianna Lund", "uuid": "61ddfbfe-2f4a-11f0-a63b-c9e6efc100f1"},
    {"name": "Cristian Guzman", "uuid": "3a8848cc-40cd-11f0-b89a-0d02db6b4f40"},
    {"name": "Sady Swanson", "uuid": "93826826-418c-11f0-9e79-b15a8cf7317f"},
    {"name": "Serenity Hidalgo", "uuid": "aaac30cc-4aec-11f0-b7dd-6b1fb3be9af6"},
    {"name": "Crystal Mullins", "uuid": "bea3f626-61e1-11f0-9d3c-ed47a9a1f5b5"},
    {"name": "Autumn Ruiz", "uuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},  # Placeholder - will search
    {"name": "Mary Kinney", "uuid": "13123ebc-2fe8-11ee-adb8-237b8b408ad1"},
    {"name": "Cassie Felts", "uuid": "8b307a58-4e27-11f0-be01-779dc8cb15c6"},
    {"name": "Cody Samora", "uuid": "7562cd38-d76d-11ef-be2b-c345788b7f2b"},
    {"name": "Aaron Redmond", "uuid": "e2bf191a-bbcd-11ef-8d2a-850ef2d4d627"},
    {"name": "Tristen Thompson", "uuid": "48d9caa4-927b-11f0-9f24-e9073c7dbe61"},
    {"name": "Larry Brasier", "uuid": "1e01bd36-08de-11f0-b6cd-177a23a8aa37"},
    {"name": "Brendan Klover", "uuid": "944f1750-6409-11f0-a2d8-4fff9109baf1"},
]


def find_lead_uuid_by_name(driver, wis, name):
    """Find a lead by name in the active list and return their UUID"""
    try:
        driver.get("https://app.myagentfinder.com/referral/active")
        wis.human_delay(3, 4)

        first_name = name.split()[0]
        links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/opp/']")
        for link in links:
            if first_name.lower() in link.text.lower():
                href = link.get_attribute("href") or ""
                if "/opp/" in href:
                    uuid = href.split("/opp/")[-1].split("?")[0]
                    print(f"  Found {name} with UUID: {uuid}")
                    return uuid
        return None
    except Exception as e:
        print(f"  Error searching: {e}")
        return None


def fix_lead(service, lead, target_date_str):
    """Fix a single lead's date using service methods"""
    driver = service.driver_service.driver
    wis = service.wis

    print(f"\n[PROCESSING] {lead['name']}")

    uuid = lead.get('uuid')

    # If UUID looks like placeholder, search for it
    if not uuid or "a1b2c3d4" in uuid:
        print(f"  Searching for lead UUID...")
        uuid = find_lead_uuid_by_name(driver, wis, lead['name'])
        if not uuid:
            print(f"  [ERROR] Could not find {lead['name']}")
            return False

    # Navigate to lead's page
    url = f"https://app.myagentfinder.com/opp/{uuid}"
    print(f"  Navigating to: {url}")
    driver.get(url)
    wis.human_delay(3, 4)

    # Verify navigation
    if uuid not in driver.current_url:
        print(f"  [ERROR] Navigation failed")
        return False

    # Scroll to Keep Us Informed section
    try:
        keep_informed = driver.find_element(By.XPATH, "//*[contains(text(), 'Keep Us Informed')]")
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", keep_informed)
        wis.human_delay(1, 2)
    except:
        driver.execute_script("window.scrollBy(0, 300);")
        wis.human_delay(1, 2)

    # STEP 1: Select nurture status (triggers date picker to appear)
    print(f"  Step 1: Selecting nurture status...")
    nurture_status = "I'm nurturing this client (long term)"
    status_selected = service._select_status_for_overdue(nurture_status)
    if status_selected:
        print(f"  [OK] Status selected")
    else:
        print(f"  [WARN] Status selection may have failed")
    wis.human_delay(1, 2)

    # STEP 2: Add detail note FIRST (before setting date)
    print(f"  Step 2: Adding detail note...")
    service._add_detail_for_update()
    print(f"  [OK] Detail added")
    wis.human_delay(0.5, 1)

    # STEP 3: Set date LAST (right before clicking Update)
    print(f"  Step 3: Setting date to {target_date_str}...")
    date_set = service._set_overdue_lead_date(target_date_str)
    if date_set:
        print(f"  [OK] Date set to {target_date_str}")
    else:
        print(f"  [WARN] Date may not have been set correctly")

    # STEP 4: Click Update button immediately
    print(f"  Step 4: Clicking Update...")
    update_clicked = service._click_update_button()
    if update_clicked:
        print(f"  [SUCCESS] {lead['name']} updated!")
        return True
    else:
        print(f"  [FAILED] Could not click Update")
        return False


def main():
    print("=" * 60)
    print("FIX MYAGENTFINDER LEAD DATES")
    print("Order: Status -> Detail -> Date -> Update")
    print("=" * 60)

    # Calculate target date
    future_date = datetime.now() + timedelta(days=NURTURE_DAYS_OFFSET)
    target_date_str = future_date.strftime("%m/%d/%Y")

    print(f"\n[CONFIG] Target date: {target_date_str} ({NURTURE_DAYS_OFFSET} days out)")
    print(f"[CONFIG] Leads to fix: {len(LEADS_TO_FIX)}")

    # Initialize service
    service = MyAgentFinderService(
        nurture_days_offset=NURTURE_DAYS_OFFSET,
        organization_id=ORG_ID
    )

    results = {"success": [], "failed": []}

    try:
        print("\n[STEP 1] Logging in...")
        if not service.login():
            print("[ERROR] Login failed!")
            return
        print("[OK] Login successful!")

        print(f"\n[STEP 2] Processing {len(LEADS_TO_FIX)} leads...")

        for lead in LEADS_TO_FIX:
            try:
                success = fix_lead(service, lead, target_date_str)
                if success:
                    results["success"].append(lead["name"])
                else:
                    results["failed"].append(lead["name"])
            except Exception as e:
                print(f"  [ERROR] {lead['name']}: {e}")
                results["failed"].append(lead["name"])

        # Summary
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Successful: {len(results['success'])}")
        print(f"Failed: {len(results['failed'])}")
        print("=" * 60)

        for name in results["success"]:
            print(f"  [OK] {name} -> {target_date_str}")
        for name in results["failed"]:
            print(f"  [FAIL] {name}")

        print("\n[DONE]")

    finally:
        service.close()


if __name__ == "__main__":
    main()

"""Simple My Agent Finder login and exploration test"""
import os
import sys
import time

os.environ["SELENIUM_HEADLESS"] = "false"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.referral_scrapers.utils.driver_service import DriverService
from selenium.webdriver.common.by import By

EMAIL = os.getenv("MY_AGENT_FINDER_EMAIL")
PASSWORD = os.getenv("MY_AGENT_FINDER_PASSWORD")

print("=" * 60)
print("MY AGENT FINDER - LOGIN TEST")
print("=" * 60)
print(f"Email: {EMAIL[:5] if EMAIL else 'NOT SET'}...")

driver_service = DriverService()

try:
    driver_service.initialize_driver()
    driver = driver_service.driver

    # Login
    print("\n[1] Going to login page...")
    driver.get("https://app.myagentfinder.com/login")
    time.sleep(3)

    print("[2] Entering credentials...")
    email_field = driver.find_element(By.CSS_SELECTOR, 'input[type="email"]')
    email_field.send_keys(EMAIL)
    time.sleep(0.5)

    pass_field = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    pass_field.send_keys(PASSWORD)
    time.sleep(0.5)

    print("[3] Clicking Sign In...")
    time.sleep(2)  # Wait for page to fully load

    # Try multiple selectors for the button
    btn = None
    btn_selectors = [
        "//button[contains(text(), 'Sign In')]",
        "//button[contains(text(), 'Sign in')]",
        "//button[contains(text(), 'Login')]",
        "//button[contains(text(), 'Log in')]",
        "button[type='button']",
        "button[type='submit']",
    ]

    for selector in btn_selectors:
        try:
            if selector.startswith('//'):
                btn = driver.find_element(By.XPATH, selector)
            else:
                btn = driver.find_element(By.CSS_SELECTOR, selector)
            if btn and btn.is_displayed():
                print(f"    Found button: '{btn.text}' with selector: {selector}")
                break
        except:
            continue

    if btn:
        driver.execute_script("arguments[0].click();", btn)
    else:
        # Try pressing Enter
        from selenium.webdriver.common.keys import Keys
        pass_field.send_keys(Keys.RETURN)
        print("    Pressed Enter to submit")

    time.sleep(5)

    print(f"[4] Current URL: {driver.current_url}")
    driver.save_screenshot("maf_after_login.png")

    if "login" not in driver.current_url.lower():
        print("[SUCCESS] Login successful!")

        print("\n[5] Going to All Active referrals...")
        driver.get("https://app.myagentfinder.com/referral/active/allactive")
        time.sleep(3)
        driver.save_screenshot("maf_allactive.png")
        print(f"    URL: {driver.current_url}")

        # Look for referral cards/rows
        print("\n[6] Analyzing page structure...")

        # Print page text (first part)
        body = driver.find_element(By.TAG_NAME, 'body').text
        print("\nPage content (first 1500 chars):")
        print("-" * 40)
        print(body[:1500].encode('ascii', 'replace').decode('ascii'))
        print("-" * 40)

        # Look for clickable elements
        links = driver.find_elements(By.TAG_NAME, 'a')
        print(f"\nLinks found: {len(links)}")
        for link in links[:15]:
            href = link.get_attribute('href') or ''
            text = link.text.strip()[:40]
            if text and '/referral/' in href:
                print(f"  - '{text}' -> {href}")

        # Look for table rows or cards
        rows = driver.find_elements(By.CSS_SELECTOR, 'tr, [class*="card"], [class*="item"]')
        print(f"\nRows/cards found: {len(rows)}")

        print("\n[7] Browser staying open for 120s - explore manually...")
        print("    Check for: status dropdowns, update buttons, lead details")
        time.sleep(120)
    else:
        print("[FAILED] Still on login page")
        print("Page text:", driver.find_element(By.TAG_NAME, 'body').text[:500])

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

finally:
    print("\nClosing browser...")
    driver_service.close()

import os
import time
from app.referral_scrapers.utils.driver_service import DriverService

print(f"SELENIUM_HEADLESS = {os.getenv('SELENIUM_HEADLESS', 'NOT SET')}")

# Create driver service
driver_service = DriverService()

print("Initializing driver...")
if driver_service.initialize_driver():
    print("Driver initialized successfully")
    print("Opening Google...")
    driver_service.get_page("https://www.google.com")
    print("Page loaded, waiting 10 seconds so you can see the browser...")
    time.sleep(10)
    driver_service.close()
    print("Browser closed")
else:
    print("Failed to initialize driver")


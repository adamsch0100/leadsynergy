import time

from selenium.common import TimeoutException

from app.referral_scrapers.utils.generate_undetected_driver import gen_driver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
import time
from app.referral_scrapers.utils.web_interaction_simulator import WebInteractionSimulator as wis

USERNAME = "online@saahomes.com"
PASSWORD = "SAA$quad#1Rank"
LOGIN_URL = "https://www.homelight.com/client/sign-in"
DASHBOARD_URL = "https://agent.homelight.com/referrals/page/1"
wis = wis()



def main():
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.140 Safari/537.36"
    chrome_options = Options()
    # chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument(f"user-agent={user_agent}")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        # Login
        driver.get(LOGIN_URL)
        email_field = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "email-field-input")))
        email_field.send_keys(USERNAME + Keys.ENTER)

        password_field = wait.until(EC.presence_of_element_located((By.ID, "user_password")))
        password_field.send_keys(PASSWORD + Keys.ENTER)

        # Wait for login to complete
        time.sleep(5)
        # Navigate to Homelight referral page
        driver.get(DASHBOARD_URL)

        # Wait for the page to fully load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)

        try:
            wait.until(EC.presence_of_element_located((By.ID, "navbar-search-input")))
            print("Search bar found")
            success= homelight_search_and_select(driver, "Jessica")
            
            if success:
                print("Search completed successfully")                
            else:
                print("Search failed")

            # success.click()
            result_link = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a[href*='/referrals/page/1?referralId']"))
            )
            wis.human_delay(1, 2)
            print("Search result found")
            result_link.click()

            # Wait for referral details page to load
            details_element = wait.until(
                EC.presence_of_element_located((By.ID, "__next"))
            )
            print("Referral details loaded")
            
            # Updating the status of the lead
            update_lead_status(driver, "ACTIVE_LISTING")
            
            # Click done button
            done_button = wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "sc-bcb8e3d2-1 kcByuW"))
            )
            wis.human_delay(2, 4)
            done_button.click()

            # Keep the browser open for inspection
            input("Press Enter to close the browser...")
        except TimeoutException as e:
            print(f"Failed to find search bar: {e}")
            print(f"Current URL: {driver.current_url}")
    finally:
        driver.quit()



def homelight_search_and_select(driver, search_text, result_selector="a[href*='/referrals/page/1?referralId']", timeout=10, debug=True):
    """
    Complete function to search on HomeLight and select a result from the dynamic dropdown.
    Uses WebInteractionSimulator for human-like interactions.
    
    Parameters:
    - driver: Selenium WebDriver instance
    - search_text: Text to search for
    - result_selector: CSS selector for the result link to click (default: referral links)
    - timeout: Maximum time to wait for results (seconds)
    - debug: Enable detailed logging
    
    Returns:
    - True if search and selection successful, False otherwise
    """
    import time
    import random
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException    
    
    # Create a simulator instance for human-like interactions
    simulator = wis
    
    def log(message):
        if debug:
            print(f"[HomeLight Search] {message}")
    
    try:
        # Make sure we're on the homepage if not already
        if "homelight.com" not in driver.current_url:
            driver.get("https://www.homelight.com")
            log("Navigated to homepage")
        
        # Wait for basic page load with human-like delay
        simulator.human_delay(2, 3)
        
        # Find the search input element
        log("Locating search input element...")
        try:
            search_input = driver.find_element(By.ID, "navbar-search-input")
        except NoSuchElementException:
            # Fallback to data-test attribute if ID not found
            search_input = driver.find_element(By.CSS_SELECTOR, "[data-test='navbar-search-input']")
        
        # Add random mouse movement
        simulator.random_mouse_movement(driver)
        
        # Scroll element into view
        log("Scrolling element into view...")
        driver.execute_script("arguments[0].scrollIntoView(true);", search_input)
        simulator.human_delay(0.5, 1.0)
        
        # Move mouse to the search input with slight randomness
        simulator.random_mouse_movement(driver, search_input)
        
        # Focus and clear
        log("Focusing on search input...")
        search_input.click()
        simulator.human_delay(0.2, 0.5)
        search_input.clear()
        simulator.human_delay(0.3, 0.7)
        
        # Type with human-like delays
        log(f"Typing search text with human-like timing: '{search_text}'")
        simulator.simulated_typing(search_input, search_text, min_delay=0.05, max_delay=0.15)
        
        # Wait for search results to appear - first wait for the container
        log("Waiting for search results to appear...")
        try:
            results_container = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='navbar-search-results-overlay-mobile']"))
            )
            log("Search results container found")
            
            # Short delay to allow results to fully populate
            simulator.human_delay(0.8, 1.5)
            
            # Now look for the specific result link to click
            log(f"Looking for result link matching: {result_selector}")
            wait = WebDriverWait(driver, timeout)
            result_link = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, result_selector))
            )
            
            log("Search result found, preparing to click...")
            
            # Move mouse to the result with human-like motion
            simulator.human_delay(0.2, 0.4)
            
            # Scroll the result into view to ensure it's clickable
            # driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", result_link)
            # simulator.human_delay(0.3, 0.6)
            
            # Click the result
            # log("Clicking on search result...")
            # result_link.click()
            # log("Clicked on search result")
            
            # Wait for page navigation to complete with human-like pause
            # simulator.human_delay(2, 4)
            
            return True
            
        except TimeoutException:
            log(f"No search results found matching '{result_selector}' within {timeout} seconds")
            # Add some random movement before giving up
            simulator.random_mouse_movement(driver)
            
            # Try to take a screenshot to see what's on the page
            try:
                screenshot_path = f"homelight_search_debug_{int(time.time())}.png"
                driver.save_screenshot(screenshot_path)
                log(f"Debug screenshot saved to {screenshot_path}")
            except Exception as ss_err:
                log(f"Failed to save debug screenshot: {str(ss_err)}")
            return False
    
    except Exception as e:
        log(f"Error during search and select: {str(e)}")
        return False


def update_lead_status(driver, db_status):
    """
    Updates a lead's status on HomeLight based on your database status
    
    Args:
        driver: Selenium WebDriver instance
        lead_id: ID of the lead in HomeLight
        db_status: Status from your database (will be mapped to HomeLight status)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        STATUS_MAPPING = {
            # Your database value : HomeLight dropdown text
            "LEFT_VOICEMAIL": "Agent Left Voicemail",
            "MADE_CONTACT": "Connected",
            "SCHEDULED_MEETING": "Meeting Scheduled",
            "MET_CLIENT": "Met With Person",
            "LISTING_SOON": "Coming Soon",
            "ACTIVE_LISTING": "Listing",
            "IN_CONTRACT": "In Escrow", 
            "LOST_DEAL": "Failed"
        }
        # Navigate to the lead details page (example URL structure)
        # driver.get(f"https://www.homelight.com/referrals/page/1?referralId={lead_id}")
        
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='referralDetailsModal-stageUpdateOptions']"))
        )
        
        # Map our database status to HomeLight's dropdown option text
        if db_status in STATUS_MAPPING:
            homelight_status = STATUS_MAPPING[db_status]
            print(f"Mapped database status '{db_status}' to HomeLight status '{homelight_status}'")
            
            # Use our dropdown selection function to select the right option
            success = select_dropdown_option(
                driver, 
                option_text_to_select=homelight_status,
                dropdown_selector="[data-test='referralDetailsModal-stageUpdateOptions']"
            )
            
            if success:
                # print(f"Successfully updated lead {lead_id} to {homelight_status}")
                return True
            else:
                print(f"Failed to update lead status")
                return False
        else:
            print(f"ERROR: Unknown database status '{db_status}'. Not found in mapping.")
            print(f"Available mappings: {STATUS_MAPPING}")
            return False
            
    except Exception as e:
        print(f"Error updating lead status: {str(e)}")
        return False


# Util Functions
def select_dropdown_option(driver, option_text_to_select, dropdown_selector="[data-test='referralDetailsModal-stageUpdateOptions']", timeout=10, debug=True):
    """
    Function to interact with a HomeLight dropdown menu and select a specific option.
    """
    import time
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    
    def log(message):
        if debug:
            print(f"[Dropdown Selector] {message}")
            
    def human_delay(min_time=0.5, max_time=1.5):
        """Add a human-like delay"""
        import random
        time.sleep(random.uniform(min_time, max_time))
            
    try:
        log(f"Looking for dropdown element: {dropdown_selector}")
        
        # Make sure the dropdown is in view first
        dropdown = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, dropdown_selector))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
        human_delay(1, 2)
        
        # Get the currently selected value if possible
        try:
            selected_item = dropdown.find_element(By.CSS_SELECTOR, "[data-test='select-selected-item']")
            current_value = selected_item.text
            log(f"Current selected value: '{current_value}'")
            
            if current_value == option_text_to_select:
                log(f"Option '{option_text_to_select}' is already selected. No action needed.")
                return True
        except Exception as e:
            log(f"Could not get current value: {str(e)}")
        
        # CRITICAL CHANGE: Check if dropdown options are ALREADY visible
        # (sometimes clicking isn't needed if the dropdown is already open)
        try:
            option_list = driver.find_element(By.CSS_SELECTOR, "[data-test='select-option-list']")
            is_dropdown_already_open = option_list.is_displayed()
            log(f"Dropdown is {'already open' if is_dropdown_already_open else 'closed'}")
        except:
            is_dropdown_already_open = False
        
        # Only try to open the dropdown if it's not already open
        if not is_dropdown_already_open:
            # Try THREE different click strategies with retries
            for click_strategy in ["standard", "action_chain", "javascript"]:
                log(f"Trying to open dropdown with {click_strategy} click...")
                
                if click_strategy == "standard":
                    try:
                        dropdown.click()
                    except Exception as e:
                        log(f"Standard click failed: {str(e)}")
                        continue
                        
                elif click_strategy == "action_chain":
                    try:
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(driver).move_to_element(dropdown).click().perform()
                    except Exception as e:
                        log(f"Action chain click failed: {str(e)}")
                        continue
                        
                elif click_strategy == "javascript":
                    try:
                        driver.execute_script("arguments[0].click();", dropdown)
                    except Exception as e:
                        log(f"JavaScript click failed: {str(e)}")
                        continue
                
                # Longer wait after attempting to open
                human_delay(2, 3)
                
                # Check if dropdown opened
                try:
                    option_list = driver.find_element(By.CSS_SELECTOR, "[data-test='select-option-list']")
                    if option_list.is_displayed():
                        log(f"Successfully opened dropdown with {click_strategy} click")
                        break
                    else:
                        log(f"Dropdown not visible after {click_strategy} click, trying next method")
                except:
                    log(f"Could not find dropdown options after {click_strategy} click")
                    continue
        
        # Direct selection approach - locate the desired option in the DOM
        # whether the dropdown is visibly open or not
        log("Attempting direct option selection...")
        
        # Use the value attribute from your HTML example:
        # <li value="listing" role="option" data-test="select-option-item" class="sc-eed32623-3 hkSoOm">Listing</li>
        target_value = None
        
        # Map common values based on your provided HTML
        value_map = {
            "agent left voicemail": "agent_left_vm",
            "connected": "connected",
            "meeting scheduled": "meeting_scheduled",
            "met with person": "met_in_person", 
            "met in person": "met_in_person",
            "coming soon": "coming_soon",
            "listing": "listing",
            "in escrow": "in_escrow",
            "failed": "failed"
        }
        
        # Try to get the mapped value
        target_value = value_map.get(option_text_to_select.lower())
        log(f"Mapped '{option_text_to_select}' to value attribute: '{target_value}'")
        
        if target_value:
            # Now find and click directly by value attribute
            try:
                option_selector = f"[data-test='select-option-item'][value='{target_value}']"
                log(f"Looking for option with selector: {option_selector}")
                
                # Wait a bit then try to find the option
                human_delay(1, 2)
                
                # First try finding it within the option list (in case dropdown is open)
                try:
                    option_list = driver.find_element(By.CSS_SELECTOR, "[data-test='select-option-list']")
                    target_option = option_list.find_element(By.CSS_SELECTOR, f"[value='{target_value}']")
                    log("Found target option within visible dropdown")
                except:
                    # If that fails, try finding it in the entire document
                    target_option = driver.find_element(By.CSS_SELECTOR, option_selector)
                    log("Found target option in document")
                
                # Scroll and click using JavaScript
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_option)
                human_delay(1, 2)
                driver.execute_script("arguments[0].click();", target_option)
                log(f"Clicked option with value='{target_value}'")
                human_delay(2, 3)
                
                return True
            except Exception as e:
                log(f"Error selecting option by value: {str(e)}")
                # Continue to fallback approach
        
        # FALLBACK: If we reach here, we need to try different strategies
        # This is a last-resort method using direct DOM manipulation
        log("Attempting fallback with JavaScript DOM manipulation...")
        try:
            # Try to set the value directly using JavaScript
            js_script = f"""
            // Find the dropdown element
            var dropdown = document.querySelector("{dropdown_selector}");
            
            // Find the displayed value element
            var displayElement = dropdown.querySelector("[data-test='select-selected-item']");
            
            // Set the display text
            if (displayElement) {{
                displayElement.textContent = "{option_text_to_select}";
                displayElement.innerText = "{option_text_to_select}";
                
                // Create and dispatch a change event
                var event = new Event('change', {{ bubbles: true }});
                dropdown.dispatchEvent(event);
                
                return true;
            }}
            return false;
            """
            result = driver.execute_script(js_script)
            if result:
                log("Successfully set value using JavaScript DOM manipulation")
                return True
        except Exception as e:
            log(f"JavaScript manipulation failed: {str(e)}")
        
        # If we get here, all approaches failed
        log("All selection approaches failed")
        return False
        
    except Exception as e:
        log(f"ERROR: Unexpected error during dropdown selection: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return False


if __name__ == '__main__':
    main()
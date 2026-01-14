import undetected_chromedriver as uc
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium_stealth import stealth
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from typing import Optional, List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.remote.webelement import WebElement
import logging
from webdriver_manager.chrome import ChromeDriverManager
import os
import platform


class DriverService:
    def __init__(self, organization_id: str = None) -> None:
        self.logger = None
        self._setup_logging()
        self.driver = None
        self.wait = None
        self.organization_id = organization_id
        self.proxy_config = None
        
        # Check if proxy usage is enabled via environment variable
        self.use_proxy = os.getenv("USE_PROXY", "false").lower() in ["true", "1", "yes"]
        
        # Initialize proxy configuration if organization_id is provided and proxy is enabled
        if self.organization_id and self.use_proxy:
            self._setup_proxy_config()
        else:
            if not self.use_proxy:
                self.logger.info("Proxy usage is disabled via USE_PROXY environment variable")
            if not self.organization_id:
                self.logger.info("No organization ID provided - running without proxy")

    def _setup_logging(self) -> None:
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _setup_proxy_config(self) -> None:
        """Setup proxy configuration for the organization"""
        try:
            from app.service.proxy_service import ProxyServiceSingleton
            
            proxy_service = ProxyServiceSingleton.get_instance()
            self.proxy_config = proxy_service.get_proxy_for_selenium(self.organization_id)
            
            if self.proxy_config:
                self.logger.info(f"Proxy configuration loaded for organization {self.organization_id}")
            else:
                self.logger.warning(f"No proxy configuration found for organization {self.organization_id}")
                
        except Exception as e:
            self.logger.error(f"Error setting up proxy config: {str(e)}")
            self.proxy_config = None

    def initialize_driver(self) -> bool:
        try:
            # Get the Chrome options with proxy configuration only if proxy is enabled
            chrome_options = setup_chrome_options(self.proxy_config if self.use_proxy else None)

            service = Service(ChromeDriverManager().install())

            # Initialize the driver with the options and service
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # Initialize the wait object with the correct driver
            self.wait = WebDriverWait(self.driver, 10)  # Use self.driver here

            # Now apply stealth settings after driver is properly initialized
            self._apply_stealth_settings()

            proxy_status = "with proxy" if (self.use_proxy and self.proxy_config) else "without proxy"
            self.logger.info(f'Driver initialized successfully {proxy_status}')
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize driver: {e}")
            return False

    def _apply_stealth_settings(self) -> None:
        if self.driver:
            try:
                # Temporarily disable stealth settings to troubleshoot
                self.logger.info("Skipping stealth settings for troubleshooting")
                # stealth(
                #     self.driver,
                #     languages=['en-US', 'en'],
                #     vendor='Google Inc.',
                #     platform='Win32',
                #     webgl_vendor='Intel Inc.',
                #     renderer='Intel Iris OpenGL Engine',
                #     fix_hairline=True
                # )
                # self.logger.info("Applied stealth settings to driver")
            except Exception as e:
                self.logger.error(f"Failed to apply stealth settings: {e}")
        else:
            self.logger.error("Cannot apply stealth settings - driver is None")

    def get_page(self, url: str) -> bool:
        try:
            self.driver.get(url)
            return True
        except Exception as e:
            self.logger.error(f"Failed to navigate to {url}: {e}")
            return False

    def find_element(self, by: By, value: str, timeout: int = 10) -> Optional[WebElement]:
        try:
            # Direct approach - first wait for element to be present
            self.wait.until(EC.presence_of_element_located((by, value)))

            # Then find the element directly
            result = self.driver.find_element(by, value)

            # Add extensive debugging
            self.logger.info(f"Found element {value}")
            self.logger.info(f"Type: {type(result)}")
            self.logger.info(f"Is list: {isinstance(result, list)}")

            # Ensure we return a single element, not a list
            if isinstance(result, list):
                if len(result) > 0:
                    self.logger.warning(f"Result was a list, returning first element")
                    return result[0]
                else:
                    self.logger.warning(f"Result was an empty list")
                    return None

            return result
        except Exception as e:
            self.logger.error(f"Failed to find element {value}: {e}")
            self.logger.error(f"Exception type: {type(e)}")
            return None

    def find_elements(self, by: By, value: str, timeout: int = 10) -> List[WebElement]:
        """Find elements with explicit wait."""
        try:
            # Wait until at least one element is present
            self.wait.until(EC.presence_of_element_located((by, value)))

            # Then find all matching elements
            elements = self.driver.find_elements(by, value)

            self.logger.info(f"Found {len(elements)} elements for {value}")
            return elements
        except Exception as e:
            self.logger.error(f"Failed to find elements {value}: {e}")
            return []

    def find_clickable_element(self, by: By, value: str, timeout: int = 10) -> Optional[any]:
        try:
            return self.wait.until(EC.element_to_be_clickable((by, value)))
        except Exception as e:
            self.logger.error(f"Failed to find clickable element {value}: {e}")
            return None

    def safe_click(self, element) -> bool:
        if element is None:
            self.logger.error("Cannot click None element")
            return False

        try:
            try:
                element.click()
            except:
                self.driver.execute_script('arguments[0].click();', element)
            return True
        except Exception as e:
            self.logger.error(f"Failed to click element: {e}")
            return False

    def scroll_into_view(self, element) -> bool:
        """Scroll an element into view safely."""
        if element is None:
            self.logger.error("Cannot scroll None element into view")
            return False

        try:
            # More reliable JavaScript approach
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
            return True
        except Exception as e:
            self.logger.error(f"Failed to scroll element into view: {e}")
            return False

    def get_current_url(self) -> str:
        return self.driver.current_url

    def close(self) -> None:
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                self.wait = None
                self.logger.info("Driver closed successfully")

        except Exception as e:
            self.logger.error(f"Error closing driver: {e}")

    def __enter__(self):
        self.initialize_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        try:
            if hasattr(self, 'logger') and self.logger:
                self.close()
        except:
            pass  # Ignore errors during cleanup


def setup_chrome_options(proxy_config=None):
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.140 Safari/537.36"
    chrome_options = webdriver.ChromeOptions()

    # Detect the operating system
    current_os = platform.system()

    if current_os == "Windows":
        print("Setting chromedriver for Windows")
    elif current_os == "Linux":
        chrome_options.binary_location = '/usr/bin/chromium-browser'
        print("Setting chromedriver for Linux")
    else:
        # macOS or other OS configuration
        chrome_options.binary_location = '/usr/local/bin/chromedriver'
        print(f"Setting default chromedriver for OS: {current_os}")

    # Add proxy configuration if provided
    if proxy_config:
        proxy_host = proxy_config.get("host")
        proxy_port = proxy_config.get("port")
        proxy_username = proxy_config.get("username")
        proxy_password = proxy_config.get("password")
        
        if proxy_host and proxy_port:
            # Set up proxy for Chrome
            chrome_options.add_argument(f'--proxy-server=http://{proxy_host}:{proxy_port}')
            
            # If authentication is required, we need to handle it via extension
            if proxy_username and proxy_password:
                print(f"Setting up proxy with authentication: {proxy_username}@{proxy_host}:{proxy_port}")
                # Create a simple proxy auth extension
                proxy_auth_extension = create_proxy_auth_extension(
                    proxy_host, proxy_port, proxy_username, proxy_password
                )
                if proxy_auth_extension:
                    chrome_options.add_extension(proxy_auth_extension)
            else:
                print(f"Setting up proxy without authentication: {proxy_host}:{proxy_port}")

    # Add common Chrome options that apply to all platforms
    headless_enabled = os.getenv("SELENIUM_HEADLESS", "true").lower() in ["true", "1", "yes"]
    if headless_enabled:
        chrome_options.add_argument('--headless=new')  # Use new headless mode for better compatibility
        print("Running Chrome in headless mode")
    else:
        print("Running Chrome in headed mode (SELENIUM_HEADLESS disabled)")
    chrome_options.add_argument(f"user-agent={user_agent}")
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')  # Helpful for headless mode
    chrome_options.add_argument('--window-size=1920,1080')

    # Temporarily disable potentially problematic options for troubleshooting
    # chrome_options.add_argument('--remote-debugging-port=9222')
    # chrome_options.add_argument('--disable-extensions')
    # chrome_options.add_argument('--disable-features=VizDisplayCompositor')

    chrome_options.add_argument('--disable-dev-shm-usage')

    return chrome_options


def create_proxy_auth_extension(proxy_host, proxy_port, proxy_username, proxy_password):
    """
    Create a Chrome extension for proxy authentication
    """
    try:
        import tempfile
        import zipfile
        import json
        
        # Create extension manifest
        manifest_json = {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Proxy Auth",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version": "22.0.0"
        }

        # Background script for proxy authentication
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{proxy_host}",
                    port: parseInt({proxy_port})
                }},
                bypassList: ["localhost"]
            }}
        }};

        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

        function callbackFn(details) {{
            return {{
                authCredentials: {{
                    username: "{proxy_username}",
                    password: "{proxy_password}"
                }}
            }};
        }}

        chrome.webRequest.onAuthRequired.addListener(
            callbackFn,
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        """

        # Create temporary directory and files
        temp_dir = tempfile.mkdtemp()
        
        # Write manifest
        with open(f"{temp_dir}/manifest.json", "w") as f:
            json.dump(manifest_json, f)
        
        # Write background script
        with open(f"{temp_dir}/background.js", "w") as f:
            f.write(background_js)
        
        # Create zip file
        extension_path = f"{temp_dir}/proxy_auth_extension.zip"
        with zipfile.ZipFile(extension_path, 'w') as zip_file:
            zip_file.write(f"{temp_dir}/manifest.json", "manifest.json")
            zip_file.write(f"{temp_dir}/background.js", "background.js")
        
        return extension_path
        
    except Exception as e:
        print(f"Error creating proxy auth extension: {str(e)}")
        return None
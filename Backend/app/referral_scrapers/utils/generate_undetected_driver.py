import undetected_chromedriver as uc
from selenium_stealth import stealth


def gen_driver():
    try:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.6167.140 Safari/537.36"
        chrome_options = uc.ChromeOptions()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument(f"user-agent={user_agent}")
        chrome_options.binary_location = "chromedriver.exe"
        driver = uc.Chrome(options=chrome_options)
        stealth(
            driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Inter Iris OpenGL Engine",
            fix_hairline=True
        )
        return driver
    except Exception as e:
        print(f"Error in driver: {e}")

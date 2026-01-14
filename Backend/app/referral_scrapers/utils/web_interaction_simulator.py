import time
import random
from typing import Any
from selenium.webdriver.remote.webelement import WebElement

class WebInteractionSimulator:
    """
    Class for simulating human-like interactions with web elements.
    Provides methods to make automated browser interactions appear more natural
    and help avoid detection by anti-bot systems.
    """
    
    @staticmethod
    def human_delay(min_time: float = 1, max_time: float = 3) -> None:
        """
        Pause for a random time between actions to simulate human behavior.
        
        Args:
            min_time: Minimum delay time in seconds
            max_time: Maximum delay time in seconds
        """
        time.sleep(random.uniform(min_time, max_time))
    
    @staticmethod
    def simulated_typing(element: WebElement, text: str, min_delay: float = 0.1, max_delay: float = 0.3) -> None:
        """
        Simulate human-like typing by sending one character at a time with random delays.

        Args:
            element: The web element to type into
            text: The text to type
            min_delay: Minimum delay between keystrokes in seconds
            max_delay: Maximum delay between keystrokes in seconds

        Raises:
            ValueError: If text is None or empty
        """
        if text is None:
            raise ValueError("Cannot type None value - credentials may not be configured")
        if not text:
            return  # Empty string, nothing to type
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(min_delay, max_delay))
    
    @staticmethod
    def random_mouse_movement(driver: Any, element: Any = None) -> None:
        """
        Simulate random mouse movement to appear more human-like.
        Can target a specific element or just move randomly.
        
        Args:
            driver: The WebDriver instance
            element: Optional element to move towards
        """
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            
            actions = ActionChains(driver)
            
            if element:
                # Move to element with some random offset
                x_offset = random.randint(-10, 10)
                y_offset = random.randint(-10, 10)
                actions.move_to_element_with_offset(element, x_offset, y_offset)
            else:
                # Random movement within viewport
                viewport_width = driver.execute_script("return window.innerWidth;")
                viewport_height = driver.execute_script("return window.innerHeight;")
                
                x = random.randint(0, viewport_width)
                y = random.randint(0, viewport_height)
                actions.move_by_offset(x, y)
                
            actions.perform()
            time.sleep(random.uniform(0.1, 0.5))
        except Exception as e:
            # Fail silently - mouse movement is nice-to-have, not critical
            pass 
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

from selenium.webdriver import Keys
from selenium.webdriver.common.by import By

from app.models.lead import Lead
from app.referral_scrapers.base_referral_service import BaseReferralService
from app.referral_scrapers.utils.driver_service import DriverService
from app.referral_scrapers.utils.web_interaction_simulator import WebInteractionSimulator as wis
from app.service.lead_service import LeadServiceSingleton
from app.utils.constants import Credentials

CREDS = Credentials()


class HomelightService(BaseReferralService):
    def __init__(self, lead: Lead, status: str, driver_service=None, organization_id: str = None, same_status_note: str = None, min_sync_interval_hours: int = 24, update_all_matches: bool = True) -> None:
        super().__init__(lead, organization_id=organization_id)
        self.base_url = "https://www.homelight.com/client/sign-in"
        self.status = status
        self.update_all_matches = update_all_matches  # If True, update ALL matching referrals (buyer + seller)
        # Credentials are loaded by BaseReferralService._setup_credentials() from database
        # Fallback to environment variables if not in database
        if not hasattr(self, 'email') or not self.email:
            self.email = CREDS.HOMELIGHT_EMAIL
        if not hasattr(self, 'password') or not self.password:
            self.password = CREDS.HOMELIGHT_PASSWORD
        self.lead_service = LeadServiceSingleton.get_instance()
        self.lead = lead
        self.wis = wis()
        self.same_status_note = same_status_note or "Same as previous update. Continuing to communicate and assist the referral as best as possible."
        self.min_sync_interval_hours = min_sync_interval_hours

        # Use provided driver service, or create our own (for backwards compatibility)
        if driver_service:
            self.driver_service = driver_service
            self.owns_driver = False
            # For shared driver services, check if already logged in by looking at driver state
            self.is_logged_in = self._check_if_logged_in()
        else:
            self.owns_driver = True
            self.is_logged_in = False

    def _check_if_logged_in(self) -> bool:
        """Check if the shared driver is already logged into HomeLight"""
        try:
            current_url = self.driver_service.get_current_url()
            # If we're on a homelight page and not on login, assume logged in
            if current_url and "homelight.com" in current_url and "signin" not in current_url and "login" not in current_url:
                return True
        except Exception:
            pass
        return False

    def update_active_lead(self, lead: Lead, status: str):
        """Update the active lead and status for this service instance"""
        self.lead = lead
        self.status = status

    @staticmethod
    def _normalize_status_text(value: Optional[str]) -> str:
        if not value:
            return ""
        return " ".join(value.strip().lower().split())

    def _parse_target_status(self, status_to_select: str) -> Tuple[Optional[str], Optional[str]]:
        sub_status = None
        if isinstance(status_to_select, (list, tuple)):
            primary = status_to_select[0] if status_to_select else None
            if len(status_to_select) > 1:
                sub_status = status_to_select[1]
        else:
            primary = status_to_select
            if isinstance(primary, str) and "::" in primary:
                parts = [part.strip() for part in primary.split("::", 1)]
                primary = parts[0]
                sub_status = parts[1] if len(parts) > 1 else None

        primary = primary.strip() if isinstance(primary, str) else primary
        sub_status = sub_status.strip() if isinstance(sub_status, str) else sub_status
        return primary, sub_status

    def _find_first_element(self, selectors: List[Tuple[By, str]]):
        for by, value in selectors:
            element = self.driver_service.find_element(by, value)
            if element:
                return element
        return None

    def _select_stage_option(self, stage_name: str) -> bool:
        stage_name_norm = self._normalize_status_text(stage_name)
        if not stage_name_norm:
            print("No stage name provided for selection")
            return False

        # Find the stage dropdown - must EXCLUDE the assigned agent dropdown
        # Assigned agent: data-test="referralDetailsModal-assignedAgent"
        # Stage dropdown: data-test="select-selected-item" (but NOT referralDetailsModal-assignedAgent)

        stage_dropdown = None

        try:
            # BEST APPROACH: Find stage dropdown by its parent container's data-test attribute
            # Stage dropdown is inside: div[data-test="referralDetailsModal-stageUpdateOptions"]
            # Assigned agent is: div[data-test="referralDetailsModal-assignedAgent"]
            
            stage_selectors = [
                # Method 1: Most reliable - find by parent container data-test
                (By.XPATH, "//div[@data-test='referralDetailsModal-stageUpdateOptions']//div[@role='button' and @data-test='select-selected-item']"),
                # Method 2: Find all select-selected-item and filter by parent
                (By.XPATH, "//div[@role='button' and @data-test='select-selected-item']"),
            ]

            for selector_type, selector_value in stage_selectors:
                try:
                    candidates = self.driver_service.find_elements(selector_type, selector_value)
                    print(f"Found {len(candidates)} candidate(s) with selector: {selector_value}")

                    for candidate in candidates:
                        try:
                            candidate_text_raw = candidate.text.strip()
                            # Clean Unicode characters that can't be encoded to Windows console
                            candidate_text = candidate_text_raw.encode('ascii', 'replace').decode('ascii').replace('?', '')
                            candidate_text_lower = candidate_text.lower()
                            candidate_data_test = candidate.get_attribute('data-test') or ''

                            try:
                                print(f"  Checking candidate: text='{candidate_text}', data-test='{candidate_data_test}'")
                            except:
                                print(f"  Checking candidate: data-test='{candidate_data_test}'")

                            # EXCLUDE: Check if this is the assigned agent dropdown
                            is_assigned_agent = False

                            # Check 1: data-test contains assigned agent identifier
                            if 'referralDetailsModal-assignedAgent' in candidate_data_test or candidate_data_test == 'referralDetailsModal-assignedAgent':
                                print(f"    SKIPPING: Has assigned agent data-test: '{candidate_data_test}'")
                                is_assigned_agent = True
                            # Check 2: Text content is "Unassigned" or "Assigned"
                            elif candidate_text_lower in ['unassigned', 'assigned']:
                                try:
                                    print(f"    SKIPPING: Matches assigned agent text: '{candidate_text}'")
                                except:
                                    print(f"    SKIPPING: Matches assigned agent text")
                                is_assigned_agent = True
                            # Check 3: Check parent chain for assigned agent wrapper
                            try:
                                parent = candidate
                                for i in range(5):  # Check up to 5 levels up
                                    parent = parent.find_element(By.XPATH, "./..")
                                    parent_data_test = parent.get_attribute('data-test') or ''
                                    if 'referralDetailsModal-assignedAgent' in parent_data_test:
                                        print(f"    SKIPPING: Parent has assigned agent data-test: '{parent_data_test}'")
                                        is_assigned_agent = True
                                        break
                                    # Also check if parent is the stage container (this is good!)
                                    if 'referralDetailsModal-stageUpdateOptions' in parent_data_test:
                                        print(f"    [OK] Confirmed: Parent is stage container: '{parent_data_test}'")
                                        break
                            except:
                                pass

                            if is_assigned_agent:
                                continue

                            # VALIDATE: Must have stage keywords in text (assigned agent won't have these)
                            # Include all possible HomeLight stages to ensure detection
                            stage_keywords = [
                                'agent left', 'agent right', 'voicemail', 'connected', 'meeting',
                                'listing', 'escrow', 'closed', 'left voicemail', 'right voicemail',
                                'vm/email', 'vm', 'met', 'met with', 'buyer', 'seller', 'person',
                                'showing', 'scheduled', 'appointment', 'consulting', 'pre-approval',
                                'offer', 'pending', 'active', 'new', 'qualified', 'nurture',
                                'dead', 'lost', 'not interested', 'unresponsive', 'working'
                            ]
                            has_stage_keyword = any(keyword in candidate_text_lower for keyword in stage_keywords)
                            
                            if not has_stage_keyword:
                                try:
                                    print(f"    SKIPPING: No stage keywords in text: '{candidate_text}'")
                                except:
                                    print(f"    SKIPPING: No stage keywords in text")
                                continue

                            # FOUND: This should be the stage dropdown
                            try:
                                print(f"    [FOUND] Stage dropdown - text='{candidate_text}', data-test='{candidate_data_test}'")
                            except:
                                print(f"    [FOUND] Stage dropdown - data-test='{candidate_data_test}'")
                            stage_dropdown = candidate
                            break

                        except Exception as e:
                            error_msg = str(e).encode('ascii', 'replace').decode('ascii')
                            print(f"    Error checking candidate: {error_msg}")
                            continue

                    if stage_dropdown:
                        break

                except Exception as e:
                    print(f"Error with selector {selector_value}: {e}")
                    continue

        except Exception as e:
            print(f"Error in dropdown search: {e}")
            import traceback
            traceback.print_exc()

        if not stage_dropdown:
            print("Could not locate stage dropdown. Available buttons on page:")
            self._log_available_buttons_for_debug()
            return False

        # Final validation: Make sure we didn't accidentally get the assigned agent dropdown
        try:
            final_data_test = stage_dropdown.get_attribute('data-test') or ''
            final_text_raw = stage_dropdown.text.strip()
            final_text = final_text_raw.encode('ascii', 'replace').decode('ascii').replace('?', '').lower()

            if 'referralDetailsModal-assignedAgent' in final_data_test:
                try:
                    print(f"ERROR: Found assigned agent dropdown instead of stage dropdown: '{final_text}'")
                except:
                    print(f"ERROR: Found assigned agent dropdown instead of stage dropdown")
                return False

            if final_text in ['unassigned', 'assigned']:
                try:
                    print(f"ERROR: Found assigned agent dropdown (by text) instead of stage dropdown: '{final_text}'")
                except:
                    print(f"ERROR: Found assigned agent dropdown (by text) instead of stage dropdown")
                return False

            try:
                print(f"Confirmed stage dropdown: '{final_text}' (data-test: '{final_data_test}')")
            except:
                print(f"Confirmed stage dropdown (data-test: '{final_data_test}')")
        except Exception as e:
            error_msg = str(e).encode('ascii', 'replace').decode('ascii')
            print(f"Warning: Could not validate dropdown: {error_msg}")

        print(f"Found stage dropdown, clicking to open...")
        self.driver_service.safe_click(stage_dropdown)
        self.wis.human_delay(1.5, 2.5)  # Wait for dropdown to open

        # Wait for options to appear
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        option_selectors = [
            (By.XPATH, "//li[contains(@role,'option')]") ,
            (By.XPATH, "//div[contains(@role,'option')]") ,
            (By.XPATH, "//button[contains(@role,'menuitem')]") ,
            (By.XPATH, "//span[contains(@class,'option')]") ,
        ]

        options: List[Any] = []
        wait = WebDriverWait(self.driver_service.driver, 10)
        
        # Wait for at least one option to appear
        for selector in option_selectors:
            try:
                wait.until(EC.presence_of_element_located(selector))
                options = self.driver_service.find_elements(*selector)
                if options:
                    break
            except:
                continue

        if not options:
            print("No stage options found after opening dropdown")
            try:
                self.driver_service.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            except:
                pass
            return False

        try:
            print(f"Looking for stage: '{stage_name}' (normalized: '{stage_name_norm}')")
        except:
            print(f"Looking for stage: '{stage_name_norm}'")
        print(f"Found {len(options)} available options:")
        
        # Extract key words from stage name for fuzzy matching
        stage_words = set(word.lower() for word in stage_name_norm.split() if len(word) > 2)
        
        best_match = None
        best_match_score = 0
        
        for i, option in enumerate(options):
            try:
                option_text_raw = option.text.strip()
                # Clean Unicode characters
                option_text = option_text_raw.encode('ascii', 'replace').decode('ascii').replace('?', '')
                option_norm = self._normalize_status_text(option_text)
                try:
                    print(f"  {i}: '{option_text}' (normalized: '{option_norm}')")
                except:
                    print(f"  {i}: (normalized: '{option_norm}')")

                # Try multiple matching strategies
                match_score = 0
                
                # Exact match (highest priority)
                if option_norm == stage_name_norm:
                    match_score = 100
                # Contains match
                elif stage_name_norm in option_norm or option_norm in stage_name_norm:
                    match_score = 80
                # Word overlap match
                elif stage_words:
                    option_words = set(word.lower() for word in option_norm.split() if len(word) > 2)
                    overlap = len(stage_words & option_words)
                    if overlap > 0:
                        match_score = 60 + (overlap * 10)
                
                if match_score > best_match_score:
                    best_match_score = match_score
                    best_match = (option, option_text, match_score)
                    
            except Exception as error:
                print(f"Error while evaluating stage option {i}: {error}")
                continue
        
        # If we found a match, use it
        if best_match and best_match_score >= 60:
            option, option_text, score = best_match
            print(f"Selecting stage option: '{option_text}' (match score: {score})")
            self.driver_service.safe_click(option)
            self.wis.human_delay(2, 3)  # Wait for dropdown to close and page to update
            return True
        elif best_match:
            # Try the best match even if score is lower (fallback)
            option, option_text, score = best_match
            print(f"Using best available match: '{option_text}' (match score: {score})")
            self.driver_service.safe_click(option)
            self.wis.human_delay(2, 3)
            return True

        print(f"Could not find matching stage option for '{stage_name}'")
        print(f"Available options were: {[opt.text.strip() for opt in options]}")
        try:
            self.driver_service.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except:
            pass
        return False

    def _log_available_buttons_for_debug(self) -> None:
        try:
            buttons = self.driver_service.find_elements(By.TAG_NAME, "button")
            for idx, button in enumerate(buttons[:20]):
                try:
                    print(f"Button[{idx}]: text='{button.text.strip()}' aria-label='{button.get_attribute('aria-label')}' role='{button.get_attribute('role')}' data-test='{button.get_attribute('data-test')}'")
                except Exception:
                    continue
        except Exception as error:
            print(f"Unable to enumerate buttons: {error}")

    def _fill_additional_fields(self, primary_stage: str) -> bool:
        metadata = getattr(self.lead, 'metadata', {}) or {}
        stage_norm = self._normalize_status_text(primary_stage)

        if stage_norm == "meeting scheduled":
            return self._fill_meeting_scheduled_fields(metadata)
        if stage_norm == "coming soon":
            return self._fill_coming_soon_fields(metadata)
        if stage_norm == "listing":
            return self._fill_listing_fields(metadata)
        if stage_norm == "in escrow":
            return self._fill_in_escrow_fields(metadata)
        return True

    def _open_add_note_form(self) -> bool:
        # First check if the note textarea is already available
        note_textarea = self.driver_service.find_element(By.CSS_SELECTOR, "textarea[data-test='connected-notes']")
        if note_textarea:
            print("Note textarea is already available")
            return True

        # If not, try to find and click an "Add Note" button
        add_note_selectors = [
            (By.XPATH, "//button[contains(text(), 'Add Another Note')]") ,
            (By.XPATH, "//button[contains(text(), 'Add Note')]") ,
        ]

        add_note_button = self._find_first_element(add_note_selectors)
        if not add_note_button:
            note_buttons = self.driver_service.find_elements(By.XPATH, "//button[contains(text(), 'Note')]")
            if note_buttons:
                add_note_button = note_buttons[0]

        if not add_note_button:
            print("Could not find a button to add a note, but checking if textarea exists...")
            # Double-check if textarea appeared after stage selection
            note_textarea = self.driver_service.find_element(By.CSS_SELECTOR, "textarea[data-test='connected-notes']")
            if note_textarea:
                print("Note textarea found after stage selection")
                return True
            return False

        self.driver_service.safe_click(add_note_button)
        self.wis.human_delay(1, 2)
        return True

    def _check_recent_activity_on_page(self, min_sync_interval_hours: int) -> bool:
        """
        Check if there's a recent activity on the HomeLight page.
        Returns True if a recent update was found (within min_sync_interval_hours), False otherwise.

        This checks the actual update history in the activity section:
        - Looks for ANY activity (not just HomeLight AI - any activity means it was updated)
        - Parses dates like "Oct 08, 2025" and times like "08:47 AM MDT"
        - Calculates if the activity is within min_sync_interval_hours
        """
        try:
            from datetime import datetime, timezone, timedelta
            import re

            print(f"[ACTIVITY CHECK] Checking for recent activity on page (min interval: {min_sync_interval_hours}h)...")

            # Wait for page to load
            self.wis.human_delay(2, 3)

            # Find the activity section using the specific ID
            activity_section = None
            activity_selectors = [
                (By.ID, "referral-detail-modal-past-activity-section"),
                (By.XPATH, "//div[@id='referral-detail-modal-past-activity-section']"),
                (By.XPATH, "//section[contains(@class, 'sc-9d82c18d-7')]"),  # Fallback to class
            ]

            for selector_type, selector_value in activity_selectors:
                try:
                    activity_section = self.driver_service.find_element(selector_type, selector_value)
                    if activity_section:
                        print(f"[ACTIVITY CHECK] Found activity section with selector: {selector_value}")
                        break
                except:
                    continue

            if not activity_section:
                print(f"[ACTIVITY CHECK] Could not find activity section - proceeding with update")
                return False

            # Get all activity articles
            try:
                activity_articles = activity_section.find_elements(By.XPATH, ".//article[contains(@class, 'sc-9d82c18d-8')]")
                print(f"[ACTIVITY CHECK] Found {len(activity_articles)} activity article(s)")
            except Exception as e:
                print(f"[ACTIVITY CHECK] Could not find activity articles: {e}")
                return False

            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(hours=min_sync_interval_hours)
            most_recent_datetime = None
            most_recent_activity_text = None

            # Parse each activity entry
            month_map = {
                'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
            }

            current_date = None  # Track the current date header

            for article in activity_articles:
                try:
                    article_text = article.text
                    article_text_lower = article_text.lower()

                    # Check if this is a date header (e.g., "Oct 08, 2025")
                    date_header = article.find_elements(By.XPATH, ".//p[contains(@class, 'kehpyJ')]")
                    if date_header and date_header[0].text.strip():
                        date_match = re.match(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2}),\s+(\d{4})', date_header[0].text.strip())
                        if date_match:
                            month_str, day_str, year_str = date_match.groups()
                            month = month_map.get(month_str, 1)
                            day = int(day_str)
                            year = int(year_str)
                            current_date = datetime(year, month, day, tzinfo=timezone.utc)
                            print(f"[ACTIVITY CHECK] Found date header: {month_str} {day_str}, {year_str}")
                            continue

                    # Check for ANY activity (not just HomeLight AI - any activity means it was updated)
                    # Skip date headers - they don't count as activity
                    if not date_header or not date_header[0].text.strip():
                        # This is an activity entry (not a date header)
                        # Extract time from article (e.g., "08:47 AM MDT")
                        time_elements = article.find_elements(By.XPATH, ".//p[contains(@class, 'bAYubZ')]")
                        activity_time = None
                        
                        if time_elements:
                            for time_elem in time_elements:
                                time_text = time_elem.text.strip()
                                # Match patterns like "08:47 AM MDT" or "09:59 PM MDT"
                                time_match = re.match(r'(\d{1,2}):(\d{2})\s+(AM|PM)\s+([A-Z]{3})', time_text)
                                if time_match:
                                    hour_str, minute_str, am_pm, tz_str = time_match.groups()
                                    hour = int(hour_str)
                                    minute = int(minute_str)
                                    
                                    # Convert to 24-hour format
                                    if am_pm == 'PM' and hour != 12:
                                        hour += 12
                                    elif am_pm == 'AM' and hour == 12:
                                        hour = 0
                                    
                                    # Parse timezone (MDT, MST, PST, EST, etc.)
                                    # For simplicity, assume MDT is UTC-6, adjust as needed
                                    tz_offset_hours = 0
                                    if tz_str == 'MDT':
                                        tz_offset_hours = -6
                                    elif tz_str == 'MST':
                                        tz_offset_hours = -7
                                    elif tz_str == 'PST':
                                        tz_offset_hours = -8
                                    elif tz_str == 'EST':
                                        tz_offset_hours = -5
                                    # Add more timezone mappings as needed
                                    
                                    # Create datetime with current_date (or today if not set)
                                    if current_date:
                                        activity_datetime = datetime(
                                            current_date.year, current_date.month, current_date.day,
                                            hour, minute, 0,
                                            tzinfo=timezone(timedelta(hours=tz_offset_hours))
                                        )
                                        # Convert to UTC
                                        activity_datetime = activity_datetime.astimezone(timezone.utc)
                                        activity_time = activity_datetime
                                        print(f"[ACTIVITY CHECK] Found activity: '{article_text[:100]}...' at {time_text} -> {activity_datetime} (UTC)")
                                    
                                    break
                        
                        # If no time found but we have a date, use the date (midnight of that day)
                        if not activity_time and current_date:
                            activity_time = current_date
                            print(f"[ACTIVITY CHECK] Found activity: '{article_text[:100]}...' on {current_date.date()} (no time)")
                        
                        # Track the most recent activity (ANY activity)
                        if activity_time:
                            if most_recent_datetime is None or activity_time > most_recent_datetime:
                                most_recent_datetime = activity_time
                                most_recent_activity_text = article_text[:300]
                                print(f"[ACTIVITY CHECK] Updated most recent activity: {activity_time} - '{most_recent_activity_text[:100]}'")

                except Exception as e:
                    print(f"[ACTIVITY CHECK] Error parsing activity article: {e}")
                    continue

            if most_recent_datetime is None:
                print(f"[ACTIVITY CHECK] No recent activity found - proceeding with update")
                return False

            # Check if the most recent activity is within the interval
            hours_ago = (now - most_recent_datetime).total_seconds() / 3600
            print(f"[ACTIVITY CHECK] Most recent activity found:")
            print(f"[ACTIVITY CHECK]   Text: {most_recent_activity_text[:150]}")
            print(f"[ACTIVITY CHECK]   Datetime: {most_recent_datetime}")
            print(f"[ACTIVITY CHECK]   Hours ago: {hours_ago:.1f}")
            print(f"[ACTIVITY CHECK]   Cutoff time: {cutoff_time}")
            print(f"[ACTIVITY CHECK]   Current time: {now}")

            if most_recent_datetime > cutoff_time:
                print(f"[ACTIVITY CHECK] SKIPPING: Recent activity found ({hours_ago:.1f}h ago) - within {min_sync_interval_hours}h interval")
                return True
            else:
                print(f"[ACTIVITY CHECK] NOT SKIPPING: Most recent activity is {hours_ago:.1f}h ago (outside {min_sync_interval_hours}h interval) - proceeding")
                return False

        except Exception as e:
            print(f"[ACTIVITY CHECK] Error checking activity: {e}")
            import traceback
            traceback.print_exc()
            # If there's an error, don't skip - proceed with update
            return False

    def _add_sync_note(self, primary_stage: str, sub_stage: Optional[str]) -> bool:
        try:
            # Try the specific selector first
            note_field = self.driver_service.find_element(By.CSS_SELECTOR, 'textarea[data-test="connected-notes"]')
            if not note_field:
                # Fallback to the placeholder selector
                note_field = self.driver_service.find_element(By.CSS_SELECTOR, 'textarea[placeholder*="Add an optional note"]')
            if not note_field:
                print("Could not locate note field to add sync note")
                return False

            # Use the same status note from lead source settings
            note_text = self.same_status_note

            note_field.click()
            note_field.clear()
            self.wis.simulated_typing(note_field, note_text.strip())
            self.wis.human_delay(1, 2)
            return True
        except Exception as error:
            print(f"Could not add sync note: {error}")
            return False

    def login_once(self) -> bool:
        """Login to HomeLight once and keep session active"""
        if self.is_logged_in:
            return True

        print("Initializing driver...")
        if not self.driver_service.initialize_driver():
            print("Failed to initialize driver")
            return False

        try:
            print("Navigating to HomeLight login page...")
            self.driver_service.get_page(self.base_url)
            self.wis.human_delay(2, 5)

            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            wait = WebDriverWait(self.driver_service.driver, 30)

            print("Finding email field...")
            email_field = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".email-field-input"))
            )
            print(f"Email field found, typing: {self.email}")
            self.wis.simulated_typing(email_field, self.email)
            self.wis.human_delay(1, 2)

            # Check if password field is already on the page (same page login)
            password_field = None
            password_selectors = [
                (By.ID, "user_password"),
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "input[placeholder*='Password']"),
                (By.CSS_SELECTOR, "input[placeholder*='password']"),
                (By.NAME, "password"),
                (By.XPATH, "//input[@type='password']"),
                (By.XPATH, "//input[contains(@placeholder, 'Password')]"),
                (By.XPATH, "//input[contains(@placeholder, 'password')]")
            ]
            
            # Try to find password field immediately (same page)
            for selector_type, selector_value in password_selectors:
                try:
                    password_field = self.driver_service.driver.find_element(selector_type, selector_value)
                    if password_field and password_field.is_displayed():
                        print(f"Found password field on same page with selector: {selector_value}")
                        break
                except:
                    continue
            
            # If password field not found, try clicking Continue (separate page flow)
            if not password_field:
                print("Password field not found on same page, trying separate page flow...")
                try:
                    continue_button = self.driver_service.find_element(By.LINK_TEXT, "Continue")
                    continue_button.click()
                    print("Clicked Continue, waiting for password page...")
                    self.wis.human_delay(3, 5)
                    
                    # Wait for password field to appear
                    for selector_type, selector_value in password_selectors:
                        try:
                            password_field = wait.until(
                                EC.presence_of_element_located((selector_type, selector_value))
                            )
                            if password_field:
                                password_field = wait.until(
                                    EC.element_to_be_clickable((selector_type, selector_value))
                                )
                                print(f"Found password field with selector: {selector_value}")
                                break
                        except:
                            continue
                except Exception as e:
                    print(f"Could not find Continue button or password field: {e}")
            
            if not password_field:
                print("ERROR: Could not find password field with any selector")
                current_url = self.driver_service.get_current_url()
                print(f"Current URL: {current_url}")
                return False
            
            print("Typing password...")
            self.wis.simulated_typing(password_field, self.password)
            self.wis.human_delay(2, 4)
            print("Clicking sign in...")
            self.driver_service.find_element(By.NAME, "commit").click()

            print("Waiting for login completion...")
            self.wis.human_delay(8, 12)  # Give even more time for login and page load

            print("Checking current URL...")
            current_url = self.driver_service.get_current_url()
            print(f"Current URL after login: {current_url}")

            # Wait for login to complete by checking URL change
            max_wait = 30  # Maximum wait time in seconds
            wait_count = 0
            login_complete = False
            
            while wait_count < max_wait:
                try:
                    current_url = self.driver_service.get_current_url()
                    print(f"Waiting for login... Current URL: {current_url}")

                    # Check if we're past the login page
                    if "login" not in current_url.lower() and "signin" not in current_url.lower():
                        login_complete = True
                        print("Login appears complete - navigating directly to referrals")
                        break
                except Exception as e:
                    print(f"Error checking page status: {e}")

                self.wis.human_delay(2, 3)
                wait_count += 5

            if not login_complete:
                print("Timeout waiting for login completion")
                return False

            # Navigate directly to referrals page instead of trying to find link
            try:
                print("Navigating directly to referrals page...")
                self.driver_service.get_page("https://agent.homelight.com/referrals/page/1")
                self.wis.human_delay(3, 5)  # Wait for referrals page to load
                
                # Verify we're on referrals page
                current_url = self.driver_service.get_current_url()
                if "referrals" in current_url.lower():
                    print(f"Successfully navigated to referrals page: {current_url}")
                    self.is_logged_in = True
                    return True
                else:
                    print(f"Warning: Expected referrals page but got: {current_url}")
                    # Still mark as logged in if we're not on login page
                    if "login" not in current_url.lower() and "signin" not in current_url.lower():
                        self.is_logged_in = True
                        return True
                    return False
            except Exception as e:
                print(f"Error navigating to referrals page: {e}")
                # Still mark as logged in if we got past login
                current_url = self.driver_service.get_current_url()
                if "login" not in current_url.lower() and "signin" not in current_url.lower():
                    self.is_logged_in = True
                    print("Login successful, but couldn't navigate to referrals (will navigate on next operation)")
                    return True
                return False
        except Exception as e:
            print(f"There is an error logging into HomeLight: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def logout(self):
        """Logout and close the session"""
        if self.owns_driver and self.driver_service:
            self.driver_service.close()
        self.is_logged_in = False

    def _click_urgent_filter(self) -> bool:
        """Click the Urgent filter button to show only urgent referrals"""
        try:
            print("[URGENT] Clicking Urgent filter to show urgent referrals...")

            # First make sure we're on the referrals page
            self._ensure_on_referrals_page()
            self.wis.human_delay(1, 2)

            # Find and click the Urgent filter button
            urgent_button = self.driver_service.find_element(
                By.CSS_SELECTOR,
                'button[data-test="referralsList-filterOption-urgent"]'
            )

            if urgent_button:
                # Check if it's already active (has some indicator like aria-pressed or class)
                button_classes = urgent_button.get_attribute('class') or ''
                aria_pressed = urgent_button.get_attribute('aria-pressed') or ''

                print(f"[URGENT] Found Urgent button, clicking...")
                urgent_button.click()
                self.wis.human_delay(2, 3)

                # Wait for the filter to be applied and results to load
                try:
                    from selenium.webdriver.support.ui import WebDriverWait
                    wait = WebDriverWait(self.driver_service.driver, 10)
                    wait.until(
                        lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")) > 0 or
                        "no results" in driver.page_source.lower()
                    )
                except:
                    self.wis.human_delay(2, 3)

                print("[URGENT] Urgent filter applied")
                return True
            else:
                print("[URGENT] Urgent filter button not found")
                return False

        except Exception as e:
            print(f"[URGENT] Error clicking urgent filter: {e}")
            return False

    def _clear_urgent_filter(self) -> bool:
        """Clear the urgent filter by clicking 'All' or refreshing the referrals page"""
        try:
            print("[URGENT] Clearing urgent filter...")

            # Try to click "All" filter option
            all_button = self.driver_service.find_element(
                By.CSS_SELECTOR,
                'button[data-test="referralsList-filterOption-all"]'
            )

            if all_button:
                all_button.click()
                self.wis.human_delay(1, 2)
                print("[URGENT] Clicked 'All' filter to clear urgent filter")
                return True
            else:
                # Fallback: navigate to referrals page directly
                referrals_link = self.driver_service.find_element(By.LINK_TEXT, "Referrals")
                if referrals_link:
                    referrals_link.click()
                    self.wis.human_delay(2, 3)
                    print("[URGENT] Navigated to referrals to clear filter")
                    return True

        except Exception as e:
            print(f"[URGENT] Error clearing urgent filter: {e}")

        return False

    def _process_urgent_sweep(self, leads_data: List[Tuple[Lead, str]], results: Dict[str, Any], tracker=None, sync_id: str = None) -> Dict[str, Any]:
        """
        Process all urgent referrals as a final sweep after regular processing.
        This catches any leads that might be in urgent status but weren't found via normal search.

        Args:
            leads_data: Original list of leads being processed
            results: Current results dictionary to update
            tracker: Optional tracker for progress updates
            sync_id: Optional sync ID for tracker

        Returns:
            Updated results dictionary
        """
        try:
            print("\n" + "="*60)
            print("[URGENT SWEEP] Starting urgent referrals sweep...")
            print("="*60)

            # Click the urgent filter
            if not self._click_urgent_filter():
                print("[URGENT SWEEP] Could not access urgent filter, skipping sweep")
                return results

            # Get all urgent referrals
            referral_rows = self.driver_service.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")
            urgent_count = len(referral_rows)
            print(f"[URGENT SWEEP] Found {urgent_count} urgent referrals to check")

            if urgent_count == 0:
                print("[URGENT SWEEP] No urgent referrals found - all clear!")
                self._clear_urgent_filter()
                return results

            # Create a lookup of lead names for matching
            lead_lookup = {}
            for lead, status in leads_data:
                full_name = f"{lead.first_name} {lead.last_name}".lower()
                first_name = lead.first_name.lower()
                last_name = lead.last_name.lower()
                lead_lookup[full_name] = (lead, status)
                # Also store by first+last for flexible matching
                lead_lookup[(first_name, last_name)] = (lead, status)

            urgent_updated = 0
            urgent_skipped = 0
            urgent_not_in_list = 0

            # Process each urgent referral
            for i, row in enumerate(referral_rows):
                try:
                    row_text = row.text.strip()
                    row_lower = row_text.lower()
                    print(f"\n[URGENT SWEEP] Checking urgent referral {i+1}/{urgent_count}: {row_text[:60]}...")

                    # Try to match this urgent referral to one of our leads
                    matched_lead = None
                    matched_status = None

                    for lead, status in leads_data:
                        full_name = f"{lead.first_name} {lead.last_name}".lower()
                        first_name = lead.first_name.lower()
                        last_name = lead.last_name.lower()

                        if full_name in row_lower or (first_name in row_lower and last_name in row_lower):
                            matched_lead = lead
                            matched_status = status
                            print(f"[URGENT SWEEP] Matched to lead: {lead.first_name} {lead.last_name}")
                            break

                    if not matched_lead:
                        print(f"[URGENT SWEEP] No matching lead in our list - skipping")
                        urgent_not_in_list += 1
                        continue

                    # Click the referral to open it
                    row.click()
                    self.wis.human_delay(2, 3)

                    # Check if this lead should be skipped due to recent activity
                    should_skip = False
                    try:
                        should_skip = self._check_recent_activity_on_page(self.min_sync_interval_hours)
                        if should_skip:
                            print(f"[URGENT SWEEP] Skipping - recent activity found")
                            urgent_skipped += 1
                    except Exception as e:
                        print(f"[URGENT SWEEP] Error checking activity: {e}")

                    if not should_skip:
                        # Update with the mapped status
                        print(f"[URGENT SWEEP] Updating with status: {matched_status}")
                        self.update_active_lead(matched_lead, matched_status)
                        success = self.update_customers(matched_status)

                        if success:
                            print(f"[URGENT SWEEP] Successfully updated!")
                            urgent_updated += 1

                            # Update metadata
                            try:
                                from datetime import datetime, timezone
                                if not matched_lead.metadata:
                                    matched_lead.metadata = {}
                                matched_lead.metadata["homelight_last_updated"] = datetime.now(timezone.utc).isoformat()
                                from app.service.lead_service import LeadServiceSingleton
                                lead_service = LeadServiceSingleton.get_instance()
                                lead_service.update(matched_lead)
                            except Exception as e:
                                print(f"[URGENT SWEEP] Warning: Could not update metadata: {e}")

                            # Update results - increment successful, potentially decrement failed
                            # Check if this lead was previously marked as failed
                            for detail in results.get("details", []):
                                if detail.get("lead_id") == matched_lead.id and detail.get("status") == "failed":
                                    detail["status"] = "success"
                                    detail["note"] = "Updated via urgent sweep"
                                    results["successful"] = results.get("successful", 0) + 1
                                    results["failed"] = max(0, results.get("failed", 0) - 1)
                                    break
                        else:
                            print(f"[URGENT SWEEP] Update failed")

                    # Navigate back to urgent list
                    self._navigate_back_to_referrals()
                    self.wis.human_delay(1, 2)

                    # Re-click urgent filter to refresh the list
                    self._click_urgent_filter()
                    self.wis.human_delay(1, 2)

                    # Re-get the list (it may have changed)
                    referral_rows = self.driver_service.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")

                except Exception as e:
                    print(f"[URGENT SWEEP] Error processing urgent referral: {e}")
                    try:
                        self._navigate_back_to_referrals()
                        self._click_urgent_filter()
                        referral_rows = self.driver_service.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")
                    except:
                        pass
                    continue

            # Clear the urgent filter when done
            self._clear_urgent_filter()

            print("\n" + "="*60)
            print("[URGENT SWEEP] Completed!")
            print(f"[URGENT SWEEP] Updated: {urgent_updated}")
            print(f"[URGENT SWEEP] Skipped (recent activity): {urgent_skipped}")
            print(f"[URGENT SWEEP] Not in our lead list: {urgent_not_in_list}")
            print("="*60 + "\n")

            # Update tracker if provided
            if tracker and sync_id:
                tracker.update_progress(
                    sync_id,
                    message=f"Urgent sweep: {urgent_updated} updated, {urgent_skipped} skipped"
                )

            return results

        except Exception as e:
            print(f"[URGENT SWEEP] Error during urgent sweep: {e}")
            import traceback
            traceback.print_exc()
            try:
                self._clear_urgent_filter()
            except:
                pass
            return results

    def _search_in_urgent_list(self, target_name: str) -> bool:
        """
        Search for a lead in the urgent filter list.
        Returns True if lead was found and clicked.
        """
        try:
            print(f"[URGENT] Searching for '{target_name}' in urgent referrals...")

            # Get all referral rows in the urgent list
            referral_rows = self.driver_service.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")
            print(f"[URGENT] Found {len(referral_rows)} urgent referrals")

            if len(referral_rows) == 0:
                print("[URGENT] No urgent referrals found")
                return False

            # Parse target name
            name_parts = target_name.split()
            first_name = name_parts[0].lower() if name_parts else ""
            last_name = name_parts[-1].lower() if len(name_parts) > 1 else ""

            matching_rows = []

            for i, row in enumerate(referral_rows):
                try:
                    row_text = row.text.strip()
                    row_lower = row_text.lower()

                    # Check for full name match or first+last name match
                    full_name_match = target_name.lower() in row_lower
                    first_last_match = first_name in row_lower and last_name in row_lower if first_name and last_name else False

                    if full_name_match or first_last_match:
                        match_type = "full name" if full_name_match else "first+last name"
                        print(f"[URGENT] Found match in urgent list (row {i}, {match_type}): '{row_text[:80]}...'")
                        matching_rows.append((i, row, row_text, full_name_match))
                except Exception as row_error:
                    continue

            if matching_rows:
                # Handle multiple matches similar to regular search
                if len(matching_rows) > 1 and getattr(self, 'update_all_matches', True):
                    print(f"[URGENT] Found {len(matching_rows)} matches in urgent list - will update all")

                    processed_texts = getattr(self, '_processed_referral_texts', set())
                    unprocessed = [(i, row, row_text, is_full) for i, row, row_text, is_full in matching_rows
                                  if row_text[:50] not in processed_texts]

                    if unprocessed:
                        self._pending_matches = [(i, row_text) for i, row, row_text, is_full in unprocessed[1:]]
                        if not hasattr(self, '_processed_referral_texts'):
                            self._processed_referral_texts = set()
                        self._processed_referral_texts.add(unprocessed[0][2][:50])

                        print(f"[URGENT] Clicking first urgent match, {len(self._pending_matches)} more to process")
                        unprocessed[0][1].click()
                        self.wis.human_delay(2, 3)
                        return True
                else:
                    # Single match or not updating all
                    print(f"[URGENT] Clicking urgent match (row {matching_rows[0][0]})")
                    matching_rows[0][1].click()
                    self.wis.human_delay(2, 3)
                    return True
            else:
                print(f"[URGENT] No matches for '{target_name}' in urgent list")
                return False

        except Exception as e:
            print(f"[URGENT] Error searching urgent list: {e}")
            return False

    def _ensure_on_referrals_page(self):
        """Ensure we're on the referrals page before searching"""
        try:
            current_url = self.driver_service.get_current_url()
            if "referrals" not in current_url:
                # Try to navigate to referrals page
                referrals_link = self.driver_service.find_element(By.LINK_TEXT, "Referrals")
                referrals_link.click()
                self.wis.human_delay(2, 3)
        except Exception as e:
            print(f"Warning: Could not ensure on referrals page: {e}")

    def _navigate_back_to_referrals(self):
        """Navigate back to the referrals page after processing a lead"""
        try:
            # Try multiple ways to get back to referrals
            current_url = self.driver_service.get_current_url()

            # If we're already on referrals page, clear search and return
            if "referrals" in current_url and "referralId" not in current_url:
                # Clear the search box if it exists (use the correct selector)
                try:
                    search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                    search_box.clear()
                    self.wis.human_delay(0.5, 1)
                    search_box.send_keys(Keys.ESCAPE)  # Close any dropdowns
                    print("[CLEAR] Cleared search box before next search")
                except Exception as e:
                    print(f"[WARNING] Could not clear search box: {e}")
                    pass
                return

            # Try to click the "Done" button if on a detail page
            # Wait a bit for any modals/panels to settle
            self.wis.human_delay(1, 2)
            
            # Check if we're still on a detail page (contains referralId or similar)
            current_url = self.driver_service.get_current_url()
            if "referralId" in current_url or "/referral/" in current_url:
                # We're on a detail page, try to find Done button
                done_selectors = [
                    (By.XPATH, "//button[contains(text(), 'Done')]"),
                    (By.XPATH, "//button[contains(., 'Done')]"),
                    (By.XPATH, "//button[@type='button' and contains(text(), 'Done')]"),
                    (By.XPATH, "//*[contains(text(), 'Done') and self::button]"),
                ]
                
                done_button = None
                for selector in done_selectors:
                    try:
                        done_button = self.driver_service.find_element(*selector)
                        if done_button and done_button.is_displayed():
                            break
                    except:
                        continue
                
                if done_button:
                    try:
                        done_button.click()
                        print("[NAV] Clicked Done button")
                        self.wis.human_delay(2, 3)
                        # Clear search box after clicking Done
                        try:
                            search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                            search_box.click()
                            self.wis.human_delay(0.3, 0.5)
                            search_box.send_keys(Keys.CONTROL + "a")
                            self.wis.human_delay(0.3, 0.5)
                            search_box.send_keys(Keys.DELETE)
                            search_box.send_keys(Keys.ESCAPE)
                            print("[CLEAR] Cleared search box after clicking Done")
                        except Exception as e:
                            print(f"[WARNING] Could not clear search box after Done: {e}")
                        return
                    except Exception as e:
                        print(f"[WARNING] Could not click Done button: {e}")
                else:
                    print("[NAV] Done button not found or not visible, trying direct navigation")

            # Try to click the Referrals navigation link
            try:
                referrals_link = self.driver_service.find_element(By.LINK_TEXT, "Referrals")
                referrals_link.click()
                self.wis.human_delay(2, 3)
                # Clear search box after clicking Referrals
                try:
                    search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                    search_box.clear()
                    self.wis.human_delay(0.5, 1)
                    search_box.send_keys(Keys.ESCAPE)
                    print("[CLEAR] Cleared search box after clicking Referrals")
                except Exception as e:
                    print(f"[WARNING] Could not clear search box after Referrals: {e}")
                return
            except:
                pass

            # As a last resort, navigate directly to the referrals URL
            try:
                self.driver_service.get_page("https://agent.homelight.com/referrals/page/1")
                self.wis.human_delay(2, 3)
                # Clear search box after navigating
                try:
                    search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                    search_box.clear()
                    self.wis.human_delay(0.5, 1)
                    search_box.send_keys(Keys.ESCAPE)
                    print("[CLEAR] Cleared search box after navigation")
                except Exception as e:
                    print(f"[WARNING] Could not clear search box after navigation: {e}")
            except Exception as e:
                print(f"Warning: Could not navigate back to referrals: {e}")

        except Exception as e:
            print(f"Warning: Error navigating back to referrals: {e}")

    def update_single_lead(self) -> bool:
        """Update a single lead (assumes already logged in)"""
        try:
            full_name = f"{self.lead.first_name} {self.lead.last_name}"

            print("\n" + "="*60)
            print("[ROCKET] STARTING HOMELIGHT SYNC")
            print("="*60)
            print(f"[CLIPBOARD] Lead: {full_name}")
            print(f"[LOCATION] Current FUB Status: {getattr(self.lead, 'status', 'N/A')}")
            print(f"[TARGET] Target HomeLight Stage: {self.status}")
            print("="*60 + "\n")

            # Make sure we're on the referrals page before searching
            self._ensure_on_referrals_page()

            print(f"[SEARCH] Step 1: Searching for '{full_name}'...")
            customer_found = self.find_and_click_customer_by_name(full_name)
            if customer_found:
                print("[SUCCESS] Customer found and opened\n")
                
                # Check if lead should be skipped (metadata and page activity)
                should_skip = False
                skip_reason = None
                
                # FIRST: Check metadata to see if lead was recently synced
                try:
                    from datetime import datetime, timedelta, timezone
                    now = datetime.now(timezone.utc)
                    cutoff_time = now - timedelta(hours=self.min_sync_interval_hours)
                    
                    has_metadata = self.lead.metadata and isinstance(self.lead.metadata, dict)
                    if has_metadata:
                        last_synced_str = self.lead.metadata.get("homelight_last_updated")
                        if last_synced_str:
                            try:
                                if isinstance(last_synced_str, str):
                                    last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                                elif isinstance(last_synced_str, datetime):
                                    last_synced = last_synced_str
                                else:
                                    last_synced = None
                                
                                if last_synced:
                                    if last_synced.tzinfo is None:
                                        last_synced = last_synced.replace(tzinfo=timezone.utc)
                                    
                                    hours_since = (now - last_synced).total_seconds() / 3600
                                    if last_synced > cutoff_time:
                                        should_skip = True
                                        skip_reason = f"Synced {hours_since:.1f}h ago (metadata)"
                                        print(f"[SKIP] Skipping {full_name} - {skip_reason}")
                            except Exception as e:
                                print(f"[WARNING] Error parsing metadata timestamp: {e}")
                except Exception as e:
                    print(f"[WARNING] Error checking metadata: {e}")
                
                # SECOND: If metadata doesn't show recent sync, check page activity
                if not should_skip:
                    try:
                        should_skip = self._check_recent_activity_on_page(self.min_sync_interval_hours)
                        if should_skip:
                            skip_reason = "Recent activity found on page"
                            print(f"[SKIP] Skipping {full_name} - {skip_reason}")
                    except Exception as e:
                        print(f"[WARNING] Error checking activity: {e}")
                
                # Skip if either check indicates we should skip
                if should_skip:
                    print(f"[SKIP] Lead skipped: {skip_reason}")
                    self._navigate_back_to_referrals()
                    return False
                
                print(f"[PEN] Step 2: Updating stage to '{self.status}'...")
                success = self.update_customers(self.status)
                if success:
                    print("\n" + "="*60)
                    print("[SUCCESS] HOMELIGHT SYNC COMPLETED SUCCESSFULLY!")
                    print("="*60 + "\n")

                # Navigate back to referrals page
                self._navigate_back_to_referrals()

                # Check if there are more matching referrals to update (e.g., buyer + seller for same person)
                pending_matches = getattr(self, '_pending_matches', [])
                if pending_matches and success:
                    print(f"\n[MULTI] Processing {len(pending_matches)} additional matching referrals...")
                    additional_success = 0

                    for match_idx, (original_row_idx, row_text) in enumerate(pending_matches):
                        print(f"\n[MULTI] Processing match {match_idx + 2}/{len(pending_matches) + 1}: {row_text[:50]}...")

                        # Search again and find the matching row
                        self._ensure_on_referrals_page()
                        self.wis.human_delay(1, 2)

                        # Disable update_all_matches temporarily to avoid infinite recursion
                        # and to only click ONE new match (not the first one we already processed)
                        old_update_all = self.update_all_matches
                        self.update_all_matches = False
                        self._pending_matches = []  # Clear so it doesn't try to process more

                        # Re-search for the customer - it will click the first match found
                        # Since we just updated one, the activity check should help us skip it
                        if self.find_and_click_customer_by_name(full_name):
                            # Check activity and update - the activity check will skip recently updated ones
                            try:
                                should_skip = self._check_recent_activity_on_page(self.min_sync_interval_hours)
                                if not should_skip:
                                    if self.update_customers(self.status):
                                        print(f"[MULTI] Successfully updated match {match_idx + 2}")
                                        additional_success += 1
                                    else:
                                        print(f"[MULTI] Failed to update match {match_idx + 2}")
                                else:
                                    print(f"[MULTI] Skipped match {match_idx + 2} - recent activity (already updated)")
                                    # This match was already updated, so count it as done
                                    additional_success += 1
                            except Exception as e:
                                print(f"[MULTI] Error processing match {match_idx + 2}: {e}")

                            self._navigate_back_to_referrals()
                        else:
                            print(f"[MULTI] Could not find match {match_idx + 2} on re-search")

                        # Restore update_all_matches setting
                        self.update_all_matches = old_update_all

                    print(f"\n[MULTI] Completed: {additional_success}/{len(pending_matches)} additional referrals updated")

                return success
            else:
                # Customer not found via normal search - try urgent filter as fallback
                print("[FALLBACK] Customer not found via search, trying urgent filter...")

                # Check if we're already in urgent fallback mode to avoid infinite loops
                if not getattr(self, '_in_urgent_fallback', False):
                    self._in_urgent_fallback = True

                    # Click the urgent filter
                    if self._click_urgent_filter():
                        # Search for the lead in the urgent list
                        if self._search_in_urgent_list(full_name):
                            print("[URGENT] Found lead in urgent list!")

                            # Check activity and update
                            should_skip = False
                            try:
                                should_skip = self._check_recent_activity_on_page(self.min_sync_interval_hours)
                                if should_skip:
                                    print(f"[URGENT] Skipping {full_name} - recent activity found")
                            except Exception as e:
                                print(f"[URGENT] Error checking activity: {e}")

                            if not should_skip:
                                print(f"[URGENT] Updating stage to '{self.status}'...")
                                success = self.update_customers(self.status)
                                if success:
                                    print("\n" + "="*60)
                                    print("[URGENT] SUCCESS! Lead updated via urgent fallback")
                                    print("="*60 + "\n")

                                # Navigate back and clear filter
                                self._navigate_back_to_referrals()
                                self._clear_urgent_filter()
                                self._in_urgent_fallback = False
                                return success
                            else:
                                self._navigate_back_to_referrals()
                                self._clear_urgent_filter()
                                self._in_urgent_fallback = False
                                return False
                        else:
                            print("[URGENT] Lead not found in urgent list either")
                            self._clear_urgent_filter()

                    self._in_urgent_fallback = False

                print("[ERROR] Could not find or click customer")
                self.logger.warning(f"Customer {full_name} not found")
                # Still navigate back to be ready for next lead
                self._navigate_back_to_referrals()
                return False
        except Exception as e:
            print("\n" + "="*60)
            print("[ERROR] HOMELIGHT SYNC FAILED")
            print("="*60)
            print(f"Error: {str(e)}\n")
            print(f"There is an error updating {full_name}: {e}")
            # Try to navigate back to referrals page even on error
            try:
                self._navigate_back_to_referrals()
            except:
                pass
            return False

    def update_multiple_leads(self, leads_data: List[Tuple[Lead, str]]) -> Dict[str, Any]:
        """
        Update multiple leads in a single browser session

        Args:
            leads_data: List of tuples containing (lead, target_status)

        Returns:
            Dict with sync results
        """
        import logging
        logger = logging.getLogger(__name__)

        results = {
            "total_leads": len(leads_data),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "details": []
        }

        # Log the start of the process
        logger.info(f"Starting HomeLight bulk update for {len(leads_data)} leads")
        print(f"[START] Beginning HomeLight update process for {len(leads_data)} leads")

        try:
            print("[LOCK] Logging into HomeLight...")
            login_start = time.time()
            login_success = self.login_once()
            login_time = time.time() - login_start

            if not login_success:
                error_msg = "Failed to login to HomeLight - check credentials and network connection"
                print(f"[ERROR] {error_msg}")
                logger.error(error_msg)
                # Mark all leads as failed due to login failure
                for lead, status in leads_data:
                    results["failed"] += 1
                    results["details"].append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": f"{lead.first_name} {lead.last_name}",
                        "status": "failed",
                        "error": error_msg
                    })
                return results

            print(f"[SUCCESS] Login successful (took {login_time:.1f}s)\n")
            logger.info(f"Successfully logged into HomeLight in {login_time:.1f} seconds")
            print(f"[ROCKET] Processing {len(leads_data)} leads...")

            processed_count = 0
            for lead, target_status in leads_data:
                processed_count += 1
                lead_start_time = time.time()

                try:
                    # Update the service instance with this lead's data
                    self.update_active_lead(lead, target_status)

                    # Process this lead
                    full_name = f"{lead.first_name} {lead.last_name}"

                    print(f"\n[LEAD {processed_count}/{len(leads_data)}] Processing: {full_name}")
                    print(f"[LOCATION] Current FUB Status: {getattr(lead, 'status', 'N/A')}")
                    print(f"[TARGET] Target HomeLight Stage: {target_status}")
                    logger.info(f"Processing lead {processed_count}/{len(leads_data)}: {full_name} -> {target_status}")

                    # Make sure we're on the referrals page before searching
                    print(f"[SEARCH] Searching for '{full_name}'...")
                    search_start = time.time()
                    customer_found = self.find_and_click_customer_by_name(full_name)
                    search_time = time.time() - search_start

                    if customer_found:
                        print(f"[SUCCESS] Customer found and opened (search took {search_time:.1f}s)")
                        
                        # Check if lead should be skipped (metadata and page activity)
                        should_skip = False
                        skip_reason = None
                        
                        # FIRST: Check metadata to see if lead was recently synced
                        try:
                            from datetime import datetime, timedelta, timezone
                            now = datetime.now(timezone.utc)
                            cutoff_time = now - timedelta(hours=self.min_sync_interval_hours)
                            
                            has_metadata = lead.metadata and isinstance(lead.metadata, dict)
                            if has_metadata:
                                last_synced_str = lead.metadata.get("homelight_last_updated")
                                if last_synced_str:
                                    try:
                                        if isinstance(last_synced_str, str):
                                            last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                                        elif isinstance(last_synced_str, datetime):
                                            last_synced = last_synced_str
                                        else:
                                            last_synced = None
                                        
                                        if last_synced:
                                            if last_synced.tzinfo is None:
                                                last_synced = last_synced.replace(tzinfo=timezone.utc)
                                            
                                            hours_since = (now - last_synced).total_seconds() / 3600
                                            if last_synced > cutoff_time:
                                                should_skip = True
                                                skip_reason = f"Synced {hours_since:.1f}h ago (metadata)"
                                                print(f"[SKIP] Skipping {full_name} - {skip_reason}")
                                    except Exception as e:
                                        print(f"[WARNING] Error parsing metadata timestamp: {e}")
                        except Exception as e:
                            print(f"[WARNING] Error checking metadata: {e}")
                        
                        # SECOND: If metadata doesn't show recent sync, check page activity
                        if not should_skip:
                            try:
                                should_skip = self._check_recent_activity_on_page(self.min_sync_interval_hours)
                                if should_skip:
                                    skip_reason = "Recent activity found on page"
                                    print(f"[SKIP] Skipping {full_name} - {skip_reason}")
                            except Exception as e:
                                print(f"[WARNING] Error checking activity: {e}")
                        
                        # Skip if either check indicates we should skip
                        if should_skip:
                            results["skipped"] = results.get("skipped", 0) + 1
                            results["details"].append({
                                "lead_id": lead.id,
                                "fub_person_id": lead.fub_person_id,
                                "name": full_name,
                                "status": "skipped",
                                "reason": skip_reason
                            })
                            # Navigate back before processing next lead
                            self._navigate_back_to_referrals()
                            try:
                                self.wis.human_delay(2, 3)
                                search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                                search_box.click()
                                self.wis.human_delay(0.3, 0.5)
                                search_box.send_keys(Keys.CONTROL + "a")
                                self.wis.human_delay(0.3, 0.5)
                                search_box.send_keys(Keys.DELETE)
                                search_box.send_keys(Keys.ESCAPE)
                            except:
                                pass
                            continue
                        
                        print(f"[PEN] Updating stage to '{target_status}'...")

                        update_start = time.time()
                        success = self.update_customers(target_status)
                        update_time = time.time() - update_start

                        if success:
                            total_time = time.time() - lead_start_time
                            print(f"[SUCCESS] Lead updated successfully! (update took {update_time:.1f}s, total {total_time:.1f}s)")
                            logger.info(f"Successfully updated lead {full_name} in {total_time:.1f} seconds")
                            
                            # Update lead metadata to track last sync time
                            try:
                                from datetime import datetime, timezone
                                if not lead.metadata:
                                    lead.metadata = {}
                                lead.metadata["homelight_last_updated"] = datetime.now(timezone.utc).isoformat()
                                from app.service.lead_service import LeadServiceSingleton
                                lead_service = LeadServiceSingleton.get_instance()
                                lead_service.update(lead)
                                print(f"[TRACK] Recorded sync time for {full_name}")
                            except Exception as e:
                                print(f"[WARNING] Could not update lead sync timestamp: {e}")
                                logger.warning(f"Could not update lead sync timestamp for {full_name}: {e}")
                            
                            results["successful"] += 1
                            results["details"].append({
                                "lead_id": lead.id,
                                "fub_person_id": lead.fub_person_id,
                                "name": f"{lead.first_name} {lead.last_name}",
                                "status": "success",
                                "processing_time": round(total_time, 2)
                            })
                        else:
                            print("[ERROR] Failed to update lead - status change unsuccessful")
                            logger.error(f"Failed to update lead {full_name} - status change unsuccessful")
                            results["failed"] += 1
                            results["details"].append({
                                "lead_id": lead.id,
                                "fub_person_id": lead.fub_person_id,
                                "name": f"{lead.first_name} {lead.last_name}",
                                "status": "failed",
                                "error": "Status update failed"
                            })
                    else:
                        print(f"[ERROR] Could not find customer '{full_name}' in HomeLight")
                        logger.warning(f"Customer {full_name} (ID: {lead.fub_person_id}) not found in HomeLight")
                        results["failed"] += 1
                        results["details"].append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": f"{lead.first_name} {lead.last_name}",
                            "status": "failed",
                            "error": "Customer not found in HomeLight"
                        })

                    # Navigate back to referrals page for next lead
                    print("[NAVIGATE] Returning to referrals page...")
                    self._navigate_back_to_referrals()
                    
                    # Ensure search box is cleared before next search
                    try:
                        self.wis.human_delay(1, 2)  # Wait for page to settle
                        search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                        search_box.clear()
                        self.wis.human_delay(0.5, 1)
                        search_box.send_keys(Keys.ESCAPE)  # Close any dropdowns
                        print("[CLEAR] Cleared search box before next lead search")
                    except Exception as e:
                        print(f"[WARNING] Could not clear search box before next search: {e}")

                except Exception as e:
                    print(f"[ERROR] Error processing lead {lead.fub_person_id}: {e}")
                    results["failed"] += 1
                    results["details"].append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": f"{lead.first_name} {lead.last_name}",
                        "status": "failed",
                        "error": str(e)
                    })
                    # Try to navigate back even on error
                    try:
                        self._navigate_back_to_referrals()
                        # Clear search box even on error
                        try:
                            search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                            search_box.clear()
                            search_box.send_keys(Keys.ESCAPE)
                        except:
                            pass
                    except:
                        pass

            # Run urgent sweep to catch any missed leads
            print("\n[URGENT] Running urgent sweep to catch any missed leads...")
            results = self._process_urgent_sweep(leads_data, results)

            total_time = time.time() - login_start
            avg_time_per_lead = total_time / len(leads_data) if leads_data else 0

            # Calculate effective success (updated + skipped = leads that are now current)
            skipped_count = results.get('skipped', 0)
            effective_success = results['successful'] + skipped_count

            print("\n" + "="*80)
            print("[FINISH] HOMELIGHT BULK SYNC COMPLETED!")
            print(f"[STATS] Total leads processed: {results['total_leads']}")
            print(f"[SUCCESS] Successfully updated: {results['successful']}")
            print(f"[SKIP] Already up-to-date (skipped): {skipped_count}")
            print(f"[ERROR] Failed updates: {results['failed']}")
            print(f"[TIME] Total time: {total_time:.1f} seconds")
            print(f"[TIME] Average time per lead: {avg_time_per_lead:.1f} seconds")
            print(f"[RATE] Effective success rate: {(effective_success/results['total_leads']*100):.1f}% ({effective_success}/{results['total_leads']} leads current)")
            print("="*80 + "\n")

            logger.info(f"HomeLight bulk sync completed: {results['successful']} updated, {skipped_count} skipped, {results['failed']} failed in {total_time:.1f}s")

        except Exception as e:
            print(f"[ERROR] Critical error during bulk sync: {e}")
            # Mark remaining leads as failed if there's a critical error
            for lead, status in leads_data[len(results["details"]):]:
                results["failed"] += 1
                results["details"].append({
                    "lead_id": lead.id,
                    "fub_person_id": lead.fub_person_id,
                    "name": f"{lead.first_name} {lead.last_name}",
                    "status": "failed",
                    "error": f"Critical error: {str(e)}"
                })
        finally:
            self.logout()

        return results

    def update_multiple_leads_with_tracker(
        self, 
        leads_data: List[Tuple[Lead, str]], 
        sync_id: str, 
        tracker
    ) -> Dict[str, Any]:
        """
        Update multiple leads with progress tracking via tracker
        
        Args:
            leads_data: List of tuples containing (lead, target_status)
            sync_id: Unique sync ID for tracking
            tracker: SyncStatusTracker instance
            
        Returns:
            Dict with sync results
        """
        import logging
        logger = logging.getLogger(__name__)
        
        results = {
            "total_leads": len(leads_data),
            "successful": 0,
            "failed": 0,
            "details": []
        }
        
        try:
            tracker.update_progress(sync_id, message="Logging into HomeLight...")
            login_start = time.time()
            login_success = self.login_once()
            login_time = time.time() - login_start
            
            if not login_success:
                error_msg = "Failed to login to HomeLight"
                tracker.complete_sync(sync_id, error=error_msg)
                return results
            
            tracker.update_progress(
                sync_id,
                message=f"Login successful (took {login_time:.1f}s)"
            )
            
            processed_count = 0
            for lead, target_status in leads_data:
                # Check for cancellation
                if tracker.is_cancelled(sync_id):
                    logger.info(f"Sync {sync_id} cancelled, stopping at lead {processed_count}/{len(leads_data)}")
                    tracker.update_progress(
                        sync_id,
                        message=f"Sync cancelled. Processed {processed_count} of {len(leads_data)} leads before cancellation."
                    )
                    results["details"].append({
                        "lead_id": None,
                        "fub_person_id": None,
                        "name": "SYNC CANCELLED",
                        "status": "cancelled",
                        "error": "Sync was cancelled by user"
                    })
                    break
                
                processed_count += 1
                full_name = f"{lead.first_name} {lead.last_name}"
                
                try:
                    self.update_active_lead(lead, target_status)
                    
                    tracker.update_progress(
                        sync_id,
                        processed=processed_count,
                        current_lead=full_name,
                        message=f"Processing {processed_count}/{len(leads_data)}: {full_name}"
                    )
                    
                    customer_found = self.find_and_click_customer_by_name(full_name)
                    
                    if customer_found:
                        # FIRST: Check metadata to see if lead was recently synced (before checking page)
                        should_skip_metadata = False
                        try:
                            from datetime import datetime, timedelta, timezone
                            now = datetime.now(timezone.utc)
                            cutoff_time = now - timedelta(hours=self.min_sync_interval_hours)
                            
                            last_synced = None
                            has_metadata = lead.metadata and isinstance(lead.metadata, dict)
                            print(f"[SKIP CHECK] {full_name}: has_metadata={has_metadata}")
                            
                            if has_metadata:
                                last_synced_str = lead.metadata.get("homelight_last_updated")
                                print(f"[SKIP CHECK] {full_name}: last_synced_str={last_synced_str}")
                                if last_synced_str:
                                    try:
                                        if isinstance(last_synced_str, str):
                                            last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
                                        elif isinstance(last_synced_str, datetime):
                                            last_synced = last_synced_str
                                        if last_synced.tzinfo is None:
                                            last_synced = last_synced.replace(tzinfo=timezone.utc)
                                        
                                        hours_since = (now - last_synced).total_seconds() / 3600
                                        print(f"[SKIP CHECK] {full_name}: last_synced={last_synced}, hours_since={hours_since:.1f}, cutoff_hours={self.min_sync_interval_hours}")
                                        
                                        if last_synced > cutoff_time:
                                            should_skip_metadata = True
                                            print(f"[SKIP] Skipping {full_name} - synced {hours_since:.1f}h ago (metadata check)")
                                        else:
                                            print(f"[SKIP CHECK] {full_name}: Not skipping - last synced {hours_since:.1f}h ago (outside {self.min_sync_interval_hours}h window)")
                                    except Exception as e:
                                        print(f"[SKIP CHECK] Error parsing metadata timestamp: {e}")
                                        import traceback
                                        traceback.print_exc()
                            else:
                                print(f"[SKIP CHECK] {full_name}: No metadata, will check page activity")
                        except Exception as e:
                            print(f"[WARNING] Error checking metadata: {e}")
                            import traceback
                            traceback.print_exc()
                        
                        # SECOND: If metadata doesn't show recent sync, check page activity
                        should_skip_activity = False
                        if not should_skip_metadata:
                            try:
                                print(f"[SKIP CHECK] {full_name}: Checking page activity...")
                                should_skip_activity = self._check_recent_activity_on_page(self.min_sync_interval_hours)
                                print(f"[SKIP CHECK] {full_name}: Activity check result: {should_skip_activity}")
                                if should_skip_activity:
                                    print(f"[SKIP] Skipping {full_name} - recent activity found on page (activity check)")
                                else:
                                    print(f"[SKIP CHECK] {full_name}: No recent activity found, proceeding with update")
                            except Exception as e:
                                print(f"[WARNING] Error checking activity: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # Skip if either check indicates we should skip
                        if should_skip_metadata or should_skip_activity:
                            skip_reason = "Recently synced (metadata)" if should_skip_metadata else "Recent activity on page"
                            results["skipped"] = results.get("skipped", 0) + 1
                            print(f"[SKIP] Skipping {full_name} - {skip_reason}")
                            tracker.update_progress(
                                sync_id,
                                skipped=results["skipped"],
                                message=f"{full_name} skipped - {skip_reason}"
                            )
                            results["details"].append({
                                "lead_id": lead.id,
                                "fub_person_id": lead.fub_person_id,
                                "name": full_name,
                                "status": "skipped",
                                "reason": skip_reason
                            })
                            # Navigate back before processing next lead
                            self._navigate_back_to_referrals()
                            try:
                                self.wis.human_delay(2, 3)
                                search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                                search_box.click()
                                self.wis.human_delay(0.3, 0.5)
                                search_box.send_keys(Keys.CONTROL + "a")
                                self.wis.human_delay(0.3, 0.5)
                                search_box.send_keys(Keys.DELETE)
                                search_box.send_keys(Keys.ESCAPE)
                            except:
                                pass
                            continue

                        # Only proceed with update if not skipped
                        print(f"[UPDATE] Starting update for {full_name} with status: {target_status}")
                        try:
                            success = self.update_customers(target_status)
                        except Exception as e:
                            print(f"[ERROR] Exception during update_customers for {full_name}: {e}")
                            import traceback
                            traceback.print_exc()
                            success = False

                        if success:
                            # Wait for update to complete and UI to settle
                            self.wis.human_delay(3, 4)

                            # Navigate back to referrals and clear search BEFORE updating metadata
                            self._navigate_back_to_referrals()
                            
                            # Clear search box after navigation
                            try:
                                self.wis.human_delay(2, 3)  # Wait for page to settle
                                search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                                # Select all and delete
                                search_box.click()
                                self.wis.human_delay(0.3, 0.5)
                                search_box.send_keys(Keys.CONTROL + "a")
                                self.wis.human_delay(0.3, 0.5)
                                search_box.send_keys(Keys.DELETE)
                                self.wis.human_delay(0.3, 0.5)
                                search_box.send_keys(Keys.ESCAPE)
                                print("[CLEAR] Cleared search box after update")
                            except Exception as e:
                                print(f"[WARNING] Could not clear search box: {e}")
                            
                            # Update lead metadata
                            try:
                                from datetime import datetime, timezone
                                if not lead.metadata:
                                    lead.metadata = {}
                                lead.metadata["homelight_last_updated"] = datetime.now(timezone.utc).isoformat()
                                from app.service.lead_service import LeadServiceSingleton
                                lead_service = LeadServiceSingleton.get_instance()
                                lead_service.update(lead)
                                print(f"[TRACK] Recorded sync time for {full_name}")
                            except Exception as e:
                                logger.warning(f"Could not update lead sync timestamp: {e}")
                                print(f"[WARNING] Could not update lead sync timestamp: {e}")
                            
                            results["successful"] += 1
                            tracker.update_progress(
                                sync_id,
                                successful=results["successful"],
                                message=f"{full_name} updated successfully"
                            )
                            results["details"].append({
                                "lead_id": lead.id,
                                "fub_person_id": lead.fub_person_id,
                                "name": full_name,
                                "status": "success"
                            })
                        else:
                            results["failed"] += 1
                            tracker.update_progress(
                                sync_id,
                                failed=results["failed"],
                                message=f"{full_name} update failed"
                            )
                            results["details"].append({
                                "lead_id": lead.id,
                                "fub_person_id": lead.fub_person_id,
                                "name": full_name,
                                "status": "failed",
                                "error": "Status update failed"
                            })
                            # Still navigate back even on failure
                            self._navigate_back_to_referrals()
                            try:
                                self.wis.human_delay(2, 3)
                                search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                                search_box.click()
                                self.wis.human_delay(0.3, 0.5)
                                search_box.send_keys(Keys.CONTROL + "a")
                                self.wis.human_delay(0.3, 0.5)
                                search_box.send_keys(Keys.DELETE)
                                search_box.send_keys(Keys.ESCAPE)
                            except:
                                pass
                    else:
                        results["failed"] += 1
                        tracker.update_progress(
                            sync_id,
                            failed=results["failed"],
                            message=f"{full_name} not found"
                        )
                        results["details"].append({
                            "lead_id": lead.id,
                            "fub_person_id": lead.fub_person_id,
                            "name": full_name,
                            "status": "failed",
                            "error": "Customer not found"
                        })
                        # Navigate back even if customer not found
                        self._navigate_back_to_referrals()
                        try:
                            self.wis.human_delay(2, 3)
                            search_box = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                            search_box.click()
                            self.wis.human_delay(0.3, 0.5)
                            search_box.send_keys(Keys.CONTROL + "a")
                            self.wis.human_delay(0.3, 0.5)
                            search_box.send_keys(Keys.DELETE)
                            search_box.send_keys(Keys.ESCAPE)
                        except:
                            pass
                        
                except Exception as e:
                    # Check for cancellation before processing error
                    if tracker.is_cancelled(sync_id):
                        break
                    
                    results["failed"] += 1
                    tracker.update_progress(
                        sync_id,
                        failed=results["failed"],
                        message=f"Error processing {full_name}: {str(e)[:50]}"
                    )
                    results["details"].append({
                        "lead_id": lead.id,
                        "fub_person_id": lead.fub_person_id,
                        "name": full_name,
                        "status": "failed",
                        "error": str(e)
                    })
                    try:
                        self._navigate_back_to_referrals()
                    except:
                        pass

            # Run urgent sweep to catch any missed leads
            if not tracker.is_cancelled(sync_id):
                tracker.update_progress(sync_id, message="Running urgent sweep...")
                results = self._process_urgent_sweep(leads_data, results, tracker=tracker, sync_id=sync_id)

            # Complete sync with current results (will mark as cancelled if cancellation was requested)
            tracker.complete_sync(sync_id, results=results)
            return results
            
        except Exception as e:
            logger.error(f"Error in bulk sync with tracker: {e}", exc_info=True)
            tracker.complete_sync(sync_id, error=str(e))
            return results
        finally:
            self.logout()

    def homelight_run(self) -> bool:
        """Legacy method for backwards compatibility"""
        try:
            print("[LOCK] Logging into HomeLight...")
            if self.login_once():
                print("[SUCCESS] Login successful\n")
                return self.update_single_lead()
            else:
                print("[ERROR] Login failed")
                self.logger.error("Login failed")
                return False
        except Exception as e:
            print(f"There is an error in HomeLight: {e}")
            return False
        finally:
            self.logout()

    def login(self) -> bool:
        """Legacy login method - delegates to login_once() for consistency"""
        return self.login_once()

    def _should_skip_lead(self, lead: Lead) -> bool:
        """Check if lead was recently synced and should be skipped"""
        try:
            if not lead.metadata:
                return False

            last_synced_str = lead.metadata.get("homelight_last_updated")
            if not last_synced_str:
                return False

            last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
            if last_synced.tzinfo is None:
                from datetime import timezone
                last_synced = last_synced.replace(tzinfo=timezone.utc)

            from datetime import timezone
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self.min_sync_interval_hours)
            return last_synced > cutoff

        except Exception as e:
            print(f"[WARNING] Error checking sync status: {e}")
            return False

    def _get_hours_since_sync(self, lead: Lead) -> Optional[float]:
        """Get hours since last sync for display purposes"""
        try:
            if not lead.metadata:
                return None

            last_synced_str = lead.metadata.get("homelight_last_updated")
            if not last_synced_str:
                return None

            last_synced = datetime.fromisoformat(last_synced_str.replace('Z', '+00:00'))
            if last_synced.tzinfo is None:
                from datetime import timezone
                last_synced = last_synced.replace(tzinfo=timezone.utc)

            from datetime import timezone
            now = datetime.now(timezone.utc)
            return (now - last_synced).total_seconds() / 3600

        except Exception:
            return None

    def _mark_lead_synced(self, lead: Lead) -> None:
        """Update lead metadata with sync timestamp"""
        try:
            if not lead.metadata:
                lead.metadata = {}

            from datetime import timezone
            lead.metadata["homelight_last_updated"] = datetime.now(timezone.utc).isoformat()
            self.lead_service.update(lead)
            print(f"[TRACK] Recorded sync time for {lead.first_name} {lead.last_name}")

        except Exception as e:
            print(f"[WARNING] Failed to update lead sync timestamp: {e}")

    def find_and_click_customer_by_name(self, target_name: str) -> bool:
        try:
            print(f"Finding and logging customer: {target_name}")
            # First, ensure we have a stable page by waiting a bit longer
            self.wis.human_delay(2, 4)

            # Find the search bar and clear it first (use the main search box, not the top navigation one)
            search_bar = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
            
            # More aggressive clearing - click, select all, delete
            try:
                search_bar.click()
                self.wis.human_delay(0.3, 0.5)
                search_bar.send_keys(Keys.CONTROL + "a")
                self.wis.human_delay(0.2, 0.3)
                search_bar.send_keys(Keys.DELETE)
                self.wis.human_delay(0.3, 0.5)
            except:
                # Fallback to simple clear
                search_bar.clear()
            self.wis.human_delay(0.5, 1)

            # Search for the customer - try full name first, only fallback to first name if no results
            customer_found = False
            search_term = target_name  # Start with full name
            
            # Get fresh reference to search bar
            try:
                search_bar = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
            except:
                print("Warning: Could not find search bar")
                return False
            
            # Clear search box - multiple methods for reliability
            try:
                # Method 1: Click and clear via JavaScript (most reliable)
                self.driver_service.driver.execute_script("arguments[0].value = '';", search_bar)
                self.wis.human_delay(0.2, 0.3)
                
                # Method 2: Click, select all, delete
                search_bar.click()
                self.wis.human_delay(0.2, 0.3)
                search_bar.send_keys(Keys.CONTROL + "a")
                self.wis.human_delay(0.1, 0.2)
                search_bar.send_keys(Keys.DELETE)
                self.wis.human_delay(0.2, 0.3)
                
                # Method 3: Clear method as fallback
                search_bar.clear()
                self.wis.human_delay(0.2, 0.3)
                
                # Verify it's actually empty
                current_value = search_bar.get_attribute('value') or ''
                if current_value:
                    print(f"Warning: Search box still has value after clearing: '{current_value}'")
                    # Force clear again
                    self.driver_service.driver.execute_script("arguments[0].value = '';", search_bar)
            except Exception as clear_error:
                print(f"Error clearing search box: {clear_error}")
                search_bar.clear()
            
            # Type the search term (full name first)
            print(f"Typing search term: '{search_term}'")
            self.wis.simulated_typing(search_bar, search_term)
            
            # Verify what was actually typed
            typed_value = search_bar.get_attribute('value') or ''
            print(f"Search box value after typing: '{typed_value}'")
            
            if typed_value != search_term:
                print(f"WARNING: Typed value '{typed_value}' doesn't match search term '{search_term}'")
                # Try to fix it
                try:
                    self.driver_service.driver.execute_script("arguments[0].value = arguments[1];", search_bar, search_term)
                    typed_value = search_bar.get_attribute('value') or ''
                    print(f"Fixed search box value: '{typed_value}'")
                except:
                    pass
            
            search_bar.send_keys(Keys.ENTER)
            
            # Wait for search results to load - wait for rows to appear
            print("Waiting for search results to load...")
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                wait = WebDriverWait(self.driver_service.driver, 10)
                # Wait for at least one referral row to appear, or for "no results" message
                wait.until(
                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")) > 0 or
                    "no results" in driver.page_source.lower() or
                    "start typing" in driver.page_source.lower()
                )
            except:
                # Fallback to fixed delay if explicit wait fails
                self.wis.human_delay(3, 5)
            
            # Additional delay to ensure results are fully rendered
            self.wis.human_delay(1, 2)

            # Look for customer rows
            try:
                print(f"Searching for referral rows containing '{target_name}'...")

                # Use the most direct approach: find all referral rows and check their text
                referral_rows = self.driver_service.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")
                print(f"Found {len(referral_rows)} referral rows")

                matching_rows = []
                # Split target name for better matching
                name_parts = target_name.split()
                first_name = name_parts[0].lower() if name_parts else ""
                last_name = name_parts[-1].lower() if len(name_parts) > 1 else ""
                
                for i, row in enumerate(referral_rows):
                    try:
                        row_text = row.text.strip()
                        row_lower = row_text.lower()
                        print(f"Checking row {i}: '{row_text[:100]}...'")

                        # More precise matching: check for full name match first
                        full_name_match = target_name.lower() in row_lower
                        
                        # Also check for first + last name match (handles cases where middle name might be in one but not the other)
                        first_last_match = False
                        if first_name and last_name:
                            # Check if both first and last name appear in the row
                            first_last_match = first_name in row_lower and last_name in row_lower
                        
                        if full_name_match or first_last_match:
                            match_type = "full name" if full_name_match else "first+last name"
                            print(f"Found matching customer row {i} ({match_type}): '{row_text[:100]}...'")
                            matching_rows.append((i, row, row_text, full_name_match))
                    except Exception as row_error:
                        print(f"Error checking row {i}: {row_error}")
                        continue

                # If multiple matches found
                if len(matching_rows) > 1:
                    print(f"Found {len(matching_rows)} matching rows")

                    # Check if we should update ALL matches (e.g., both buyer and seller referrals)
                    if getattr(self, 'update_all_matches', True):
                        print(f"[MULTI] Will update ALL {len(matching_rows)} matching referrals for this lead")

                        # Check if we should skip any already-processed referrals
                        processed_texts = getattr(self, '_processed_referral_texts', set())

                        # Find the first unprocessed match
                        unprocessed_matches = [(i, row, row_text, is_full) for i, row, row_text, is_full in matching_rows
                                              if row_text[:50] not in processed_texts]

                        if unprocessed_matches:
                            # Store pending matches (excluding the one we're about to click)
                            self._pending_matches = [(i, row_text) for i, row, row_text, is_full in unprocessed_matches[1:]]

                            # Mark this one as processed
                            if not hasattr(self, '_processed_referral_texts'):
                                self._processed_referral_texts = set()
                            self._processed_referral_texts.add(unprocessed_matches[0][2][:50])

                            print(f"[MULTI] Clicking match (row {unprocessed_matches[0][0]}), {len(self._pending_matches)} more to process after")
                            unprocessed_matches[0][1].click()
                            customer_found = True
                        else:
                            print(f"[MULTI] All matches already processed, skipping")
                            customer_found = False
                    else:
                        # Original behavior: pick the best match
                        print(f"Found {len(matching_rows)} matching rows - trying to pick the best match")

                        # Try to match by buyer/seller type if available in lead tags
                        lead_tags = getattr(self.lead, 'tags', []) or []
                        if isinstance(lead_tags, str):
                            try:
                                import json
                                lead_tags = json.loads(lead_tags)
                            except:
                                lead_tags = []

                        best_match = None
                        best_match_score = 0

                        for i, row, row_text, is_full_match in matching_rows:
                            score = 0
                            row_lower = row_text.lower()

                            # Strong preference for full name matches
                            if is_full_match:
                                score += 20

                            # Check for buyer/seller match in tags
                            if any('buyer' in str(tag).lower() for tag in lead_tags) and 'buyer' in row_lower:
                                score += 10
                            elif any('seller' in str(tag).lower() for tag in lead_tags) and 'seller' in row_lower:
                                score += 10

                            # Prefer rows with addresses (more complete records)
                            if any(addr_word in row_lower for addr_word in ['ave', 'st', 'street', 'road', 'rd', 'drive', 'dr', 'blvd', 'cir', 'ct']):
                                score += 3

                            # Prefer rows that start with the full name (more likely to be the primary match)
                            if row_text.strip().lower().startswith(target_name.lower()):
                                score += 5

                            if score > best_match_score:
                                best_match_score = score
                                best_match = (i, row, row_text)

                        if best_match:
                            i, row, row_text = best_match
                            print(f"Selected best match (row {i}, score: {best_match_score}): '{row_text[:100]}...'")
                            row.click()
                            customer_found = True
                        else:
                            # If no best match, prefer the one with full name match
                            full_match = next((m for m in matching_rows if m[3]), None)
                            if full_match:
                                print(f"Using full name match (row {full_match[0]})")
                                full_match[1].click()
                                customer_found = True
                            else:
                                print(f"Using first match (no clear best match)")
                                matching_rows[0][1].click()
                                customer_found = True
                elif len(matching_rows) == 1:
                    # Single match - use it
                    print(f"Single match found - clicking row {matching_rows[0][0]}")
                    matching_rows[0][1].click()
                    customer_found = True
                else:
                    # No matches with full name - only try first name if we truly have zero results
                    if len(referral_rows) == 0 and len(target_name.split()) > 1:
                        first_name = target_name.split()[0]
                        print(f"No matches with full name '{target_name}' and no results found, trying first name '{first_name}'...")
                        
                        # Clear and search with first name
                        try:
                            search_bar = self.driver_service.find_element(By.CSS_SELECTOR, 'input[placeholder="Search"]')
                            self.driver_service.driver.execute_script("arguments[0].value = '';", search_bar)
                            search_bar.click()
                            self.wis.human_delay(0.2, 0.3)
                            search_bar.send_keys(Keys.CONTROL + "a")
                            self.wis.human_delay(0.1, 0.2)
                            search_bar.send_keys(Keys.DELETE)
                            self.wis.human_delay(0.2, 0.3)
                            
                            self.wis.simulated_typing(search_bar, first_name)
                            search_bar.send_keys(Keys.ENTER)
                            
                            # Wait for search results
                            try:
                                wait = WebDriverWait(self.driver_service.driver, 10)
                                wait.until(
                                    lambda driver: len(driver.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")) > 0 or
                                    "no results" in driver.page_source.lower()
                                )
                            except:
                                self.wis.human_delay(3, 5)
                            self.wis.human_delay(1, 2)
                            
                            # Search again
                            referral_rows = self.driver_service.find_elements(By.CSS_SELECTOR, "a[data-test='referralsList-row']")
                            print(f"Found {len(referral_rows)} referral rows with first name search")
                            
                            # Use same matching logic as before
                            name_parts = target_name.split()
                            first_name_lower = name_parts[0].lower() if name_parts else ""
                            last_name_lower = name_parts[-1].lower() if len(name_parts) > 1 else ""
                            
                            for i, row in enumerate(referral_rows):
                                try:
                                    row_text = row.text.strip()
                                    row_lower = row_text.lower()
                                    
                                    # Check for full name or first+last match
                                    if target_name.lower() in row_lower or (first_name_lower in row_lower and last_name_lower in row_lower):
                                        print(f"Found matching customer row {i} with first name search: '{row_text[:100]}...'")
                                        row.click()
                                        customer_found = True
                                        break
                                except Exception as row_error:
                                    continue
                        except Exception as first_name_error:
                            print(f"Error trying first name search: {first_name_error}")
                    else:
                        print(f"No matching rows found for '{target_name}' (but {len(referral_rows)} total rows exist)")

            except Exception as search_error:
                print(f"Error during search: {search_error}")
                import traceback
                traceback.print_exc()

            # If no customer found, there's likely an issue with the search or page structure
            if not customer_found:
                print(f"Failed to find customer '{target_name}' after searching. This may indicate:")
                print("1. The search didn't work properly")
                print("2. The page structure has changed")
                print("3. The customer name doesn't exist in the results")
                print("4. The referral row selector needs updating")

            if not customer_found:
                # Last resort: click the first customer-like element
                print("Could not find customer by name, trying first clickable element...")
                customer_elements = self.driver_service.find_elements(By.CSS_SELECTOR, "div[cursor='pointer'], div.cursor-pointer")
                if customer_elements:
                    # Skip navigation elements and click what looks like a customer
                    for i, element in enumerate(customer_elements):
                        try:
                            text = element.text.lower()
                            # Look for elements that have names or addresses
                            if (len(text.split()) >= 2 and  # At least 2 words
                                not any(nav_word in text for nav_word in ['menu', 'nav', 'header', 'sidebar']) and
                                any(indicator in text for indicator in ['seller', 'buyer', 'road', 'street', 'avenue', 'drive', 'ca', 'california', 'tx', 'texas', 'fl', 'florida'])):
                                print(f"Clicking customer element {i}: '{text[:50]}...'")
                                element.click()
                                customer_found = True
                                break
                        except:
                            continue

                    # If still no match, click the first reasonable element (skip first 2 nav elements)
                    if not customer_found and len(customer_elements) > 2:
                        try:
                            text = customer_elements[2].text[:50]
                            print(f"Clicking first fallback element: '{text}...'")
                            customer_elements[2].click()
                            customer_found = True
                        except Exception as fallback_error:
                            print(f"Fallback click failed: {fallback_error}")

            if not customer_found:
                raise Exception("No suitable customer element found to click")

            self.wis.human_delay(3, 4)
            return True

        except Exception as e:
            print(f"Error clicking customer: {e}")
            return False

    def update_customers(self, status_to_select: str) -> bool:
        try:
            primary_stage, sub_stage = self._parse_target_status(status_to_select)
            if not primary_stage:
                print("No stage provided to update in HomeLight")
                return False

            print(f"Syncing HomeLight stage to: {primary_stage}{f' / {sub_stage}' if sub_stage else ''}")

            # Wait for detail panel to load
            self.wis.human_delay(2, 3)

            if not self._select_stage_option(primary_stage):
                print(f"Failed to select stage '{primary_stage}'")
                return False

            if not self._fill_additional_fields(primary_stage):
                print(f"Missing required data to complete stage '{primary_stage}'")
                return False

            # Attempt to add a factual sync note based on FUB data
            if not self._open_add_note_form():
                return False

            print("Adding sync note based on FUB data...")
            if not self._add_sync_note(primary_stage, sub_stage):
                print("Failed to add sync note")
                return False

            # After changing the stage, look for "Update Stage" button (since we changed the stage)
            print("Confirming stage update...")
            update_stage_button = None
            try:
                update_stage_button = self.driver_service.find_element(By.XPATH, "//button[contains(text(), 'Update Stage')]")
            except:
                pass
            
            if update_stage_button:
                update_stage_button.click()
                print("Clicked Update Stage button")
                self.wis.human_delay(3, 4)  # Wait longer for update to complete
            else:
                # Fallback: look for "Add note" or "Add Another Note" button (for same stage updates)
                print("Update Stage button not found, trying Add note button...")
                add_note_button = None
                try:
                    add_note_button = self.driver_service.find_element(By.XPATH, "//button[contains(text(), 'Add Another Note')]")
                except:
                    pass
                
                if not add_note_button:
                    try:
                        add_note_button = self.driver_service.find_element(By.CSS_SELECTOR, "button[data-test='referral-add-note-btn']")
                    except:
                        pass
                
                if not add_note_button:
                    try:
                        add_note_button = self.driver_service.find_element(By.XPATH, "//button[contains(text(), 'Add note')]")
                    except:
                        pass
                
                if add_note_button:
                    add_note_button.click()
                    print("Clicked Add note/Add Another Note button")
                    self.wis.human_delay(2, 3)  # Wait for note form to appear or save

                    # For same-stage updates, might need to click Add note again to save
                    try:
                        # Check if there's a save/submit button now
                        save_buttons = [
                            (By.XPATH, "//button[contains(text(), 'Add note')]"),
                            (By.XPATH, "//button[contains(text(), 'Add Another Note')]"),
                            (By.XPATH, "//button[contains(text(), 'Save')]"),
                            (By.XPATH, "//button[@type='submit']"),
                        ]
                        for btn_selector in save_buttons:
                            try:
                                save_btn = self.driver_service.find_element(*btn_selector)
                                if save_btn and save_btn.is_displayed():
                                    save_btn.click()
                                    print("Clicked save/submit button")
                                    self.wis.human_delay(2, 3)
                                    break
                            except:
                                continue
                    except:
                        pass
                else:
                    print("Could not find Update Stage or Add note/Add Another Note button")
                    return False
            
            # Wait a bit more for any UI updates or success messages
            self.wis.human_delay(1, 2)
            print("Stage sync completed")
            return True
        except Exception as e:
            print(f"ERROR updating HomeLight stage: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def _fill_meeting_scheduled_fields(self, metadata: Dict[str, Any]) -> bool:
        try:
            meeting_date_value = metadata.get('meeting_date') or metadata.get('meeting_datetime')
            if not meeting_date_value:
                self.logger.warning("Missing meeting date in metadata; leaving fields untouched")
                return True

            try:
                meeting_date = datetime.fromisoformat(str(meeting_date_value)).strftime("%m/%d/%Y")
            except Exception:
                meeting_date = str(meeting_date_value)

            meeting_date_field = self.driver_service.find_element(By.XPATH, "//input[@placeholder='mm/dd/yyyy'] | //input[contains(@placeholder, 'Meeting Date')]")
            if meeting_date_field:
                meeting_date_field.clear()
                self.wis.simulated_typing(meeting_date_field, meeting_date)
                self.wis.human_delay(1, 2)
            return True
        except Exception as e:
            self.logger.warning(f"Could not fill Meeting Scheduled fields: {e}")
            return False

    def _fill_coming_soon_fields(self, metadata: Dict[str, Any]) -> bool:
        try:
            est_date_value = metadata.get('estimated_market_date')
            exp_date_value = metadata.get('coming_soon_expiration_date') or metadata.get('expiration_date')

            if not est_date_value or not exp_date_value:
                self.logger.warning("Missing coming soon dates in metadata; leaving fields untouched")
                return True

            def _format_date(value):
                try:
                    return datetime.fromisoformat(str(value)).strftime("%m/%d/%Y")
                except Exception:
                    return str(value)

            est_market_date = _format_date(est_date_value)
            expiration_date = _format_date(exp_date_value)

            est_date_field = self.driver_service.find_element(By.XPATH, "//input[contains(@placeholder, 'Estimated date on market')] | //label[contains(text(), 'Estimated date on market')]/following::input[1]")
            if est_date_field:
                est_date_field.clear()
                self.wis.simulated_typing(est_date_field, est_market_date)
                self.wis.human_delay(1, 2)

            exp_date_field = self.driver_service.find_element(By.XPATH, "//input[contains(@placeholder, 'Expiration date')] | //label[contains(text(), 'Expiration date')]/following::input[1]")
            if exp_date_field:
                exp_date_field.clear()
                self.wis.simulated_typing(exp_date_field, expiration_date)
                self.wis.human_delay(1, 2)
            return True
        except Exception as e:
            self.logger.warning(f"Could not fill Coming Soon fields: {e}")
            return False

    def _fill_listing_fields(self, metadata: Dict[str, Any]) -> bool:
        try:
            listing_date_value = metadata.get('listing_date') or getattr(self.lead, 'updated_at', None)
            mls_number = metadata.get('mls_number')
            listing_url = metadata.get('listing_url') or metadata.get('listing_link')

            if not listing_date_value and not mls_number and not listing_url:
                self.logger.warning("Missing listing details in metadata; leaving fields untouched")
                return True

            if listing_date_value:
                try:
                    listing_date = datetime.fromisoformat(str(listing_date_value)).strftime("%m/%d/%Y")
                except Exception:
                    listing_date = str(listing_date_value)
                date_listed_field = self.driver_service.find_element(By.XPATH, "//input[contains(@placeholder, 'Date listed')] | //label[contains(text(), 'Date listed')]/following::input[1]")
                if date_listed_field:
                    date_listed_field.clear()
                    self.wis.simulated_typing(date_listed_field, listing_date)
                    self.wis.human_delay(1, 2)

            if mls_number:
                mls_field = self.driver_service.find_element(By.XPATH, "//input[contains(@placeholder, 'MLS number')] | //label[contains(text(), 'MLS number')]/following::input[1]")
                if mls_field:
                    mls_field.clear()
                    self.wis.simulated_typing(mls_field, str(mls_number))
                    self.wis.human_delay(1, 2)

            if listing_url:
                url_field = self.driver_service.find_element(By.XPATH, "//input[contains(@placeholder, 'URL')] | //label[contains(text(), 'URL')]/following::input[1]")
                if url_field:
                    url_field.clear()
                    self.wis.simulated_typing(url_field, str(listing_url))
                    self.wis.human_delay(1, 2)

            return True
        except Exception as e:
            self.logger.warning(f"Could not fill Listing fields: {e}")
            return False

    def _fill_in_escrow_fields(self, metadata: Dict[str, Any]) -> bool:
        try:
            close_date_value = metadata.get('close_date') or metadata.get('estimated_close_date')
            final_price_value = metadata.get('final_price') or getattr(self.lead, 'price', None)
            payment_type_value = metadata.get('payment_type')
            contact_email_value = metadata.get('contact_email') or self.lead.email

            if close_date_value:
                try:
                    close_date = datetime.fromisoformat(str(close_date_value)).strftime("%m/%d/%Y")
                except Exception:
                    close_date = str(close_date_value)
                close_date_field = self.driver_service.find_element(By.XPATH, "//input[contains(@placeholder, 'Estimated close date')] | //label[contains(text(), 'Estimated close date')]/following::input[1]")
                if close_date_field:
                    close_date_field.clear()
                    self.wis.simulated_typing(close_date_field, close_date)
                    self.wis.human_delay(1, 2)

            if final_price_value is not None:
                price_str = str(final_price_value).replace('$', '').replace(',', '')
                price_field = self.driver_service.find_element(By.XPATH, "//input[contains(@placeholder, 'Final price')] | //label[contains(text(), 'Final price')]/following::input[1]")
                if price_field:
                    price_field.clear()
                    self.wis.simulated_typing(price_field, price_str)
                    self.wis.human_delay(1, 2)

            if payment_type_value:
                try:
                    payment_type_dropdown = self.driver_service.find_element(By.XPATH, "//button[contains(text(), 'Select a payment type')] | //select[contains(@name, 'payment')]")
                    if payment_type_dropdown:
                        payment_type_dropdown.click()
                        self.wis.human_delay(1, 2)
                        payment_option = self.driver_service.find_element(By.XPATH, f"//option[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{payment_type_value.lower()}')] | //li[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{payment_type_value.lower()}')]")
                        if payment_option:
                            payment_option.click()
                            self.wis.human_delay(1, 2)
                except Exception as e:
                    self.logger.warning(f"Could not select payment type: {e}")

            if contact_email_value:
                contact_field = self.driver_service.find_element(By.XPATH, "//input[contains(@placeholder, 'Enter an email address')] | //label[contains(text(), 'Contact for payment')]/following::input[1]")
                if contact_field:
                    contact_field.clear()
                    self.wis.simulated_typing(contact_field, contact_email_value)
                    self.wis.human_delay(1, 2)

            return True
        except Exception as e:
            self.logger.warning(f"Could not fill In Escrow fields: {e}")
            return False

    def _add_natural_note(self):
        """Deprecated. Use _add_sync_note instead."""
        return False

    @classmethod
    def get_platform_name(cls) -> str:
        return "HomeLight"

    def get_listing_info(self):
        # Use name from lead data to generate a mock MLS number if not available
        name = f"{self.lead.first_name} {self.lead.last_name}"
        mls_number = f"MLS{name.upper()[:4]}{datetime.now().strftime('%y%m%d')}"

        # Generate listing date (today or from webhook data if available
        listing_date = datetime.now().strftime('%y%m%d')

        # Generate URL based on name
        name_for_url = f"{self.lead.first_name}{self.lead.last_name}".lower()
        listing_url = f"https://www.example.com/listings/{name_for_url}"

        return {
            'mls_number': mls_number,
            'listing_date': listing_date,
            'listing_url': listing_url
        }

    def get_escrow_info(self):
        # Estimated close date: 30 days from now
        close_date = (datetime.now() + timedelta(days=30)).strftime('%m%d%Y')

        # Final price: Use price from webhook data or default
        final_price = self.lead.price

        # Contact email
        contact_email = self.lead.email

        return {
            "close_date": close_date,
            "final_price": final_price,
            "contact_email": contact_email
        }


if __name__ == '__main__':
    homelight = HomelightService(Lead(), "")
    homelight.homelight_run()


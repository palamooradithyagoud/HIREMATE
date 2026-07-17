import os
import re
import json
import logging
import asyncio
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JobApplicationAgent")

BASE_DIR = r"c:\PROJECTS\SKILL PATH\AI-CATALYST-main\AI-CATALYST-main"

class JobApplicationAgent:
    def __init__(self, headless=False):
        # We default to headless=False so the user can interact locally
        self.headless = headless

    async def check_login_status(self, page) -> bool:
        """
        Determines if the user has successfully signed in by checking common elements.
        """
        # Common elements indicating an active session
        login_indicators = [
            "text=Sign Out", "text=Logout", "text=log out", "text=sign out",
            "a[href*='logout']", "a[href*='signout']",
            "div[class*='avatar']", "img[class*='profile']",
            "text=Dashboard", "text=My Applications", "text=Welcome,"
        ]
        
        # Check if any of these selectors are present and visible
        for selector in login_indicators:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    logger.info(f"Detected login indicator element: {selector}")
                    return True
            except Exception:
                continue
                
        # Also check URL path
        url = page.url.lower()
        if "dashboard" in url or "home" in url or "feed" in url or "profile" in url:
            logger.info(f"URL indicates active dashboard session: {page.url}")
            return True
            
        return False

    async def detect_auth_required(self, page) -> bool:
        """
        Detects if the page is currently asking for authentication.
        """
        auth_selectors = [
            "input[type='password']", "input[name*='password']",
            "text=Sign In", "text=Login", "text=Log in", "text=Sign in to",
            "button:has-text('Sign In')", "button:has-text('Log In')",
            "a[href*='login']", "a[href*='signin']"
        ]
        
        # If we have password input or login titles, auth is likely required
        for selector in auth_selectors:
            try:
                el = await page.query_selector(selector)
                if el and await el.is_visible():
                    # Double check if we are already logged in (some pages keep login links visible)
                    if not await self.check_login_status(page):
                        logger.info(f"Detected auth requirement via selector: {selector}")
                        return True
            except Exception:
                continue
        return False

    async def run_state_machine(self, url: str, profile_data: dict, essay_answers: dict, status_callback, confirm_event: asyncio.Event):
        """
        Runs the complete job application pipeline using a State Machine design.
        Yields logs and status updates to status_callback(state, message).
        """
        async def update_status(state: str, message: str, success: bool = True):
            logger.info(f"[{state}] {message}")
            await status_callback(state, message, success)

        await update_status("START", "Initializing Job Application Agent...")
        
        async with async_playwright() as p:
            await update_status("OPEN_JOB", f"Opening target job application URL: {url}...")
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
                
                # Check if we need to click an initial "Apply" button to open the form
                apply_buttons = await page.query_selector_all("text=Apply, text=apply, text='Apply Now', text='Submit Application'")
                for btn in apply_buttons:
                    if await btn.is_visible():
                        await update_status("OPEN_JOB", "Clicking 'Apply' button to access form...")
                        await btn.click()
                        await page.wait_for_timeout(3000)
                        break

                # ── State: CHECK_LOGIN ──
                await update_status("CHECK_LOGIN", "Checking page authentication status...")
                auth_needed = await self.detect_auth_required(page)
                
                if auth_needed:
                    # ── State: WAIT_FOR_USER_LOGIN ──
                    await update_status("WAIT_FOR_USER_LOGIN", "Login required. Please sign in, complete MFA, or solve CAPTCHA in the pop-up browser window.", success=False)
                    
                    # Monitor loop: check if user logs in successfully (checks every 2 seconds for up to 5 minutes)
                    logged_in = False
                    for i in range(150): # 300 seconds total
                        if await self.check_login_status(page):
                            logged_in = True
                            break
                        # Check if target URL changes to an application form directly
                        if not await self.detect_auth_required(page):
                            # The auth inputs disappeared, might be redirected
                            await page.wait_for_timeout(2000)
                            if await self.check_login_status(page) or not await self.detect_auth_required(page):
                                logged_in = True
                                break
                        await asyncio.sleep(2)
                        
                    if not logged_in:
                        raise TimeoutError("Authentication monitoring timed out. The agent will close the session.")
                    
                    # ── State: LOGIN_SUCCESS ──
                    await update_status("LOGIN_SUCCESS", "Login detected. Continuing to application form...")
                else:
                    await update_status("LOGIN_SUCCESS", "Authentication not required or active session detected. Proceeding...")

                # ── State: OPEN_APPLICATION ──
                await update_status("OPEN_APPLICATION", "Navigating to final application form inputs...")
                await page.wait_for_timeout(2000)

                # ── State: DETECT_FORM ──
                await update_status("DETECT_FORM", "Scanning page for form fields (inputs, select options, textareas)...")
                inputs = await page.query_selector_all("input, textarea, select")
                
                # ── State: FILL_FIELDS ──
                await update_status("FILL_FIELDS", "Matching fields to user profile and starting auto-fill...")
                
                full_name = profile_data.get("full_name", "")
                first_name = ""
                last_name = ""
                if full_name:
                    parts = full_name.split(maxsplit=1)
                    first_name = parts[0]
                    last_name = parts[1] if len(parts) > 1 else ""

                filled_log = []
                unfilled_log = []

                for idx, element in enumerate(inputs):
                    el_type = await element.get_attribute("type")
                    if el_type in ["hidden", "submit", "button", "checkbox", "radio"]:
                        continue

                    name = await element.get_attribute("name") or ""
                    el_id = await element.get_attribute("id") or ""
                    placeholder = await element.get_attribute("placeholder") or ""
                    tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                    
                    label_text = ""
                    if el_id:
                        label_el = await page.query_selector(f"label[for='{el_id}']")
                        if label_el:
                            label_text = await label_el.inner_text()
                    
                    if not label_text:
                        label_text = await element.evaluate("""el => {
                            let label = el.closest('label');
                            if (label) return label.innerText;
                            let prev = el.previousElementSibling;
                            if (prev && prev.tagName.toLowerCase() === 'label') return prev.innerText;
                            return '';
                        }""")

                    label_text = (label_text or "").strip()
                    field_key = label_text or name or el_id or placeholder or f"field_{idx}"
                    classification = self._classify_field(field_key, tag_name)

                    fill_val = ""
                    if classification == "full_name":
                        fill_val = full_name
                    elif classification == "first_name":
                        fill_val = first_name
                    elif classification == "last_name":
                        fill_val = last_name
                    elif classification == "email":
                        fill_val = profile_data.get("email", "")
                    elif classification == "phone":
                        fill_val = profile_data.get("phone", "")
                    elif classification == "linkedin":
                        fill_val = profile_data.get("linkedin_profile", "")
                    elif classification == "github":
                        fill_val = profile_data.get("github_profile", "")
                    elif classification == "portfolio":
                        fill_val = profile_data.get("portfolio_url", "")
                    elif classification == "essay":
                        # Match label to keys in essay_answers
                        matched_key = None
                        for key in essay_answers.keys():
                            if key.lower() in field_key.lower() or field_key.lower() in key.lower():
                                matched_key = key
                                break
                        if matched_key:
                            fill_val = essay_answers[matched_key]
                        else:
                            fill_val = list(essay_answers.values())[0] if essay_answers else ""

                    if fill_val:
                        if el_type == "file":
                            # ── State: UPLOAD_RESUME / UPLOAD_COVER_LETTER ──
                            upload_state = "UPLOAD_RESUME" if "resume" in classification else "UPLOAD_COVER_LETTER"
                            await update_status(upload_state, f"Uploading file document for '{field_key}'...")
                            
                            file_dir = os.path.join(BASE_DIR, "data", "temp_uploads")
                            os.makedirs(file_dir, exist_ok=True)
                            file_name = "resume.pdf" if "resume" in classification else "cover_letter.pdf"
                            file_path = os.path.join(file_dir, file_name)
                            if not os.path.exists(file_path):
                                with open(file_path, "w") as tf:
                                    tf.write(f"Sample PDF File for {classification}")
                                    
                            await element.set_input_files(file_path)
                            filled_log.append(f"Uploaded {file_name}")
                        else:
                            # If essay questions are detected, transition to ANSWER_APPLICATION_QUESTIONS state
                            if classification == "essay":
                                await update_status("ANSWER_APPLICATION_QUESTIONS", f"Filling AI-generated essay answer for: '{field_key}'...")
                            
                            await element.focus()
                            await element.fill(fill_val)
                            filled_log.append(field_key)
                    else:
                        unfilled_log.append(field_key)

                # Capture preview screenshot before user confirmation
                screenshot_dir = os.path.join(BASE_DIR, "static", "screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)
                timestamp = int(asyncio.get_event_loop().time())
                preview_screenshot = f"preview_{timestamp}.png"
                preview_path = os.path.join(screenshot_dir, preview_screenshot)
                await page.screenshot(path=preview_path)

                # Check for captcha warning
                captcha_detected = False
                captcha_frames = await page.query_selector_all("iframe[src*='recaptcha'], iframe[src*='hcaptcha']")
                if captcha_frames:
                    captcha_detected = True

                # ── State: PREVIEW_APPLICATION ──
                # Package and return form overview details to UI
                preview_data = {
                    "filled_fields": filled_log,
                    "unfilled_fields": unfilled_log,
                    "screenshot": f"/static/screenshots/{preview_screenshot}",
                    "captcha_detected": captcha_detected
                }
                await update_status("PREVIEW_APPLICATION", json.dumps(preview_data))

                # ── State: WAIT_FOR_USER_CONFIRMATION ──
                await update_status("WAIT_FOR_USER_CONFIRMATION", "Application ready for review. Waiting for your confirmation...", success=False)
                
                # Wait for confirm event (user clicks confirm on frontend)
                # Max wait time of 10 minutes
                try:
                    await asyncio.wait_for(confirm_event.wait(), timeout=600.0)
                except asyncio.TimeoutError:
                    raise TimeoutError("Application confirmation timed out. Closing browser session.")

                # ── State: SUBMIT_APPLICATION ──
                await update_status("SUBMIT_APPLICATION", "Submitting application on target form...")
                submit_btn = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Submit'), button:has-text('Apply')")
                
                if submit_btn:
                    await submit_btn.click()
                    await page.wait_for_timeout(5000)
                    
                    # Capture success page screenshot
                    success_screenshot = f"success_{timestamp}.png"
                    success_path = os.path.join(screenshot_dir, success_screenshot)
                    await page.screenshot(path=success_path)
                    
                    # ── State: SAVE_APPLICATION_HISTORY ──
                    await update_status("SAVE_APPLICATION_HISTORY", f"Saved success screenshot: /static/screenshots/{success_screenshot}")
                    
                    # ── State: START_INTERVIEW_PREPARATION ──
                    await update_status("START_INTERVIEW_PREPARATION", "Auto-scheduling mock interview prep matching role requirements...")
                    
                    await browser.close()
                    return {
                        "status": "Applied",
                        "screenshot": f"/static/screenshots/{success_screenshot}"
                    }
                else:
                    raise ValueError("Failed to locate form submit button automatically.")

            except Exception as e:
                logger.error(f"Error during state machine execution: {e}")
                # Capture error screenshot for diagnostics
                error_screenshot = f"error_{int(asyncio.get_event_loop().time())}.png"
                error_path = os.path.join(screenshot_dir, error_screenshot)
                try:
                    await page.screenshot(path=error_path)
                except Exception:
                    pass
                if browser:
                    await browser.close()
                raise e

    def _classify_field(self, label: str, tag_name: str) -> str:
        label_lower = label.lower()
        if "first name" in label_lower:
            return "first_name"
        elif "last name" in label_lower:
            return "last_name"
        elif "full name" in label_lower or "name" in label_lower:
            return "full_name"
        elif "email" in label_lower or "mail" in label_lower:
            return "email"
        elif "phone" in label_lower or "mobile" in label_lower or "contact" in label_lower:
            return "phone"
        elif "linkedin" in label_lower:
            return "linkedin"
        elif "github" in label_lower:
            return "github"
        elif "portfolio" in label_lower or "website" in label_lower or "website" in label_lower:
            return "portfolio"
        elif "resume" in label_lower or "cv" in label_lower:
            return "resume"
        elif "cover letter" in label_lower:
            return "cover_letter"
        elif tag_name == "textarea" or "why" in label_lower or "describe" in label_lower or "tell us" in label_lower or "?" in label_lower:
            return "essay"
        return "other"

import asyncio
import os
import time
import logging
import traceback
import re # Import re for AI fallback label normalization
from typing import Dict, Any, Optional, Tuple, List

from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError
from queue_manager import QueueManager
from resume_loader import load_resume_data
from browser_computer import LocalPlaywrightComputer
# from agent_config import create_agent # This seems unused, remove?
from form_improvements import (
    fill_all_fields, check_for_missed_fields, get_field_label,
    select_custom_dropdown_option, 
    select_matching_option, 
    match_field 
)
from gemini_helper import get_gemini_response

# Configure logging (should be configured by main, but get logger)
logger = logging.getLogger("job_processor")

async def process_job(job: Dict[str, Any], resume: Dict[str, Any], config: Dict[str, Any], headless: bool = True) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Process a job application using the automated agent. Uses config for settings.

    Returns:
        Tuple[bool, str, Optional[Dict]]:
            - Success flag
            - Status message or error reason
            - Additional details or None
    """
    job_data = job.get('job_data', {})
    job_id = job.get('id')
    apply_url = job_data.get('apply_url')
    if not apply_url:
        logger.error(f"Job {job_id}: No application URL found.")
        return False, "No application URL found", None

    # Load settings from config
    testing_mode = config.get('agent_settings', {}).get('testing_mode', False)
    page_load_timeout = config.get('agent_settings', {}).get('page_load_timeout', 45000)
    navigation_timeout = config.get('agent_settings', {}).get('navigation_timeout', 40000)
    delay_before_filling = config.get('agent_settings', {}).get('delay_before_filling', 0.5)
    screenshots_dir = config.get('paths', {}).get('screenshots_dir', 'screenshots')
    captcha_selectors = config.get('common_selectors', {}).get('captcha', [])
    error_selectors = config.get('common_selectors', {}).get('error_message', [])
    success_selectors = config.get('common_selectors', {}).get('success_message', [])
    submit_selectors = config.get('common_selectors', {}).get('submit_button', [])


    logger.info(f"Processing job {job_id}: {job_data.get('title')} at {job_data.get('company')}")
    logger.info(f"Application URL: {apply_url}")
    if testing_mode: logger.warning("🧪 TESTING MODE ENABLED - Submission will be skipped.")

    start_time = time.time()
    computer: Optional[LocalPlaywrightComputer] = None # Define computer outside try block for finally
    filling_results: Dict[str, Any] = {} # Initialize filling_results

    try:
        # Start the browser session using async with
        async with LocalPlaywrightComputer(apply_url, headless, navigation_timeout=navigation_timeout) as computer:
            page = computer.page # Get page object

            try:
                # --- Page Load and Initial Checks ---
                logger.info("Waiting for page load...")
                # Using domcontentloaded is often faster and sufficient
                await page.wait_for_load_state("domcontentloaded", timeout=page_load_timeout)
                logger.info("✅ Page loaded.")

                # --- CAPTCHA Check ---
                logger.info("Checking for CAPTCHA...")
                captcha_found = False
                for selector in captcha_selectors:
                    # Use locator with short timeout for visibility check
                    captcha_element = page.locator(selector).first
                    try:
                        if await captcha_element.is_visible(timeout=1500):
                             logger.error(f"❌ CAPTCHA detected on page using selector: {selector}")
                             screenshot = await take_screenshot(page, job_id, screenshots_dir, "captcha_detected")
                             captcha_found = True
                             break # Exit loop once captcha found
                    except PlaywrightTimeoutError:
                         continue # Element not visible within timeout
                if captcha_found:
                     return False, "CAPTCHA detected", {"screenshot": screenshot}
                logger.info("✅ No CAPTCHA detected.")

                # Check if it looks like an application form
                has_form_elements = await page.locator("input[type='text'], input[type='email'], textarea, select").count() > 0
                submit_button_locator = await find_submit_button(page, submit_selectors)
                if not has_form_elements or submit_button_locator is None:
                    logger.warning("❌ Application form elements not detected or submit button missing.")
                    screenshot = await take_screenshot(page, job_id, screenshots_dir, "no_form_detected")
                    closed_msgs = ["job has been closed", "no longer available", "position has been filled"]
                    page_text = await page.content()
                    if any(msg in page_text.lower() for msg in closed_msgs):
                         logger.warning("Job may be closed or unavailable.")
                         return False, "Job appears closed or unavailable", {"screenshot": screenshot}
                    return False, "Application form not detected on page", {"screenshot": screenshot}
                logger.info("✅ Application form detected.")

                await asyncio.sleep(delay_before_filling) # Short pause

                # --- Step 1: Deterministic Filling ---
                logger.info("Running deterministic form filling...")
                filling_results = await fill_all_fields(page, resume, config)
                logger.info(f"Initial filling results: Filled={len(filling_results['fields_filled'])}, Skipped={len(filling_results['fields_skipped'])}, Errors={len(filling_results['errors'])}")

                # --- Step 2: Check for Missed Required Fields ---
                missed_required_labels = await check_for_missed_fields(page, config, filling_results)

                # --- Step 3: AI Fallback for Missed Fields ---
                if missed_required_labels:
                    logger.warning(f"Found {len(missed_required_labels)} potentially missed required fields: {missed_required_labels}. Attempting AI fallback.")
                    ai_filled_count = 0
                    labels_to_try = list(missed_required_labels)
                    for label in labels_to_try:
                        # Check if somehow filled/skipped between check and now
                        if label in filling_results['fields_filled'] or label in filling_results['fields_skipped'] or f"custom_dropdown:{label}" in filling_results['fields_filled'] or f"radio_group:{label}" in filling_results['fields_filled']:
                            continue
                        ai_success = await fill_missed_field_with_ai(page, label, resume, config, filling_results)
                        if ai_success: ai_filled_count += 1
                        await asyncio.sleep(0.6) # Slightly longer delay between AI API calls

                    logger.info(f"AI fallback completed. Successfully filled {ai_filled_count} additional fields.")

                else:
                    logger.info("No missed required fields detected after initial filling.")


                # --- Step 4: Final Check and Submission ---
                final_missed_labels = await check_for_missed_fields(page, config, filling_results)
                if final_missed_labels:
                    logger.error(f"❌ Still missing required fields after AI fallback: {', '.join(final_missed_labels)}")
                    screenshot = await take_screenshot(page, job_id, screenshots_dir, "missing_final")
                    final_details = {
                        "missing_fields": final_missed_labels,
                        "screenshot": screenshot,
                        "filling_results": filling_results
                    }
                    return False, "Missing required fields after AI fallback", final_details


                # Find submit button again
                submit_button = await find_submit_button(page, submit_selectors)
                if not submit_button:
                    logger.error("❌ Submit button not found or not visible/enabled before submission attempt.")
                    screenshot = await take_screenshot(page, job_id, screenshots_dir, "submit_not_found")
                    return False, "Submit button not found", {"screenshot": screenshot, "filling_results": filling_results}

                pre_submit_screenshot = await take_screenshot(page, job_id, screenshots_dir, "pre_submit")
                logger.info(f"Pre-submission screenshot saved to {pre_submit_screenshot}")

                # --- Actual Submission ---
                if testing_mode:
                    logger.info("🧪 Testing mode: Skipping actual form submission.")
                    return True, "Testing mode - form filled successfully but not submitted", {
                        "screenshot": pre_submit_screenshot,
                        "filling_results": filling_results
                    }

                logger.info("Attempting form submission...")
                submission_success = False
                submission_error = None
                try:
                     # Click and wait for navigation/response
                     async with page.expect_navigation(timeout=navigation_timeout, wait_until="domcontentloaded") as nav_info:
                          await submit_button.click(timeout=5000)
                     # response = await nav_info.value # Response might be null if navigation finishes first
                     logger.info(f"✅ Form submission initiated and navigation detected.")
                     submission_success = True # Assume success if navigation completes without error after click
                     await asyncio.sleep(1.5) # Allow time for page render after navigation

                except PlaywrightTimeoutError as e:
                     # Timeout might mean submission succeeded but page didn't navigate, or it truly failed
                     logger.warning(f"Timeout waiting for navigation after submit click: {e}. Checking page state...")
                     submission_error = f"Submission timeout ({navigation_timeout}ms)"
                     # Check for errors immediately after timeout
                     errors_visible = await check_for_validation_errors(page, error_selectors)
                     if errors_visible:
                          logger.error("❌ Validation errors found after submission timeout.")
                          submission_error += f" with validation errors: {errors_visible}"
                          submission_success = False
                     else:
                          # No errors, but no navigation... could be success or failure.
                          logger.warning("No navigation or validation errors after timeout. Status uncertain.")
                          # Check for success messages as a fallback
                          success_indicator = await check_for_success_indicators(page, success_selectors, apply_url)
                          if success_indicator:
                               logger.info(f"✅ Success indicator found after timeout: {success_indicator}. Assuming success.")
                               submission_success = True
                               submission_error = None # Override timeout error
                          else:
                               submission_success = False # Still uncertain, assume failure/needs review


                except Exception as e:
                     logger.error(f"Error during form submission click or wait: {str(e)}")
                     logger.error(traceback.format_exc())
                     submission_success = False
                     submission_error = f"Error during submission: {str(e)}"

                # --- Post-Submission Verification ---
                post_submit_screenshot = await take_screenshot(page, job_id, screenshots_dir, "post_submit")
                logger.info(f"Post-submission screenshot saved to {post_submit_screenshot}")

                # Final determination based on submission attempt and checks
                if submission_success:
                     elapsed_time = time.time() - start_time
                     success_indicator = await check_for_success_indicators(page, success_selectors, apply_url) # Check again just in case
                     logger.info(f"✅ Application submitted successfully for job {job_id}. Indicator: {success_indicator or 'Navigation'}. Time: {elapsed_time:.2f}s")
                     return True, "Application submitted successfully", {
                          "pre_submit_screenshot": pre_submit_screenshot,
                          "post_submit_screenshot": post_submit_screenshot,
                          "success_indicator": success_indicator or "Navigation after submit",
                          "filling_results": filling_results
                     }
                else:
                    # If submission failed explicitly or timed out without success indicators
                    errors_visible = await check_for_validation_errors(page, error_selectors)
                    final_message = submission_error or "Submission failed or status unclear"
                    if errors_visible and "validation errors" not in final_message:
                         final_message += f". Validation errors: {errors_visible}"

                    logger.error(f"❌ Submission failed for job {job_id}: {final_message}")
                    return False, final_message, {
                         "status_ambiguous": submission_error is not None and not errors_visible and not await check_for_success_indicators(page, success_selectors, apply_url), # Flag if ambiguous
                         "validation_errors": errors_visible,
                         "pre_submit_screenshot": pre_submit_screenshot,
                         "post_submit_screenshot": post_submit_screenshot,
                         "filling_results": filling_results
                    }

            except Exception as e:
                # Catch errors during the main page interaction logic
                error_details = traceback.format_exc()
                logger.error(f"Error during application processing for job {job_id}: {str(e)}\n{error_details}")
                # Ensure page is available before taking screenshot
                screenshot = await take_screenshot(page, job_id, screenshots_dir, "processing_error") if 'page' in locals() and page else "No page available"
                return False, f"Processing error: {str(e)}", {"error_details": error_details, "screenshot": screenshot, "filling_results": filling_results}

    except Exception as e:
        # Catch errors during browser startup/initial connection
        error_details = traceback.format_exc()
        logger.error(f"Browser session error for job {job_id}: {str(e)}\n{error_details}")
        return False, f"Browser session error: {str(e)}", {"error_details": error_details}

async def fill_missed_field_with_ai(page: Page, field_label: str, resume: Dict[str, Any], config: Dict[str, Any], results: Dict[str, Any]) -> bool:
    """
    Attempts to fill a single missed required field using hardcoded answers for common EEO/Auth
    questions, LLM context for location, or general LLM fallback.
    """
    logger.info(f"Attempting AI fallback/hardcoded answer for missed required field: '{field_label}'")
    normalized_label = re.sub(r'\*$', '', field_label).strip()
    if not normalized_label:
         logger.warning("AI Fallback: Cannot process empty field label.")
         return False

    element: Optional[Locator] = None
    unique_check_id = normalized_label
    fuzzy_threshold = config.get('agent_settings', {}).get('fuzzy_match_threshold', 85)
    hardcoded_answer = None # Variable to store hardcoded answer if applicable

    # --- START Hardcoded Answers & Location Check ---
    label_lower = normalized_label.lower()

    # EEO / Demographics (Prioritize specific wording if possible)
    if "hispanic or latino" in label_lower or "hispanic/latino" in label_lower:
        hardcoded_answer = "No" # Or "Decline to self-identify"
    elif "race/ethnicity" in label_lower or "race / ethnicity" in label_lower or "racial origin" in label_lower:
        hardcoded_answer = "Asian" # Or "Decline to self-identify", "Two or more races" etc. - Check form options
    elif "gender identity" in label_lower or (label_lower == "gender" and "optional" not in label_lower): # Avoid optional gender fields?
        hardcoded_answer = "Male" # Or "Decline to self-identify", "Non-binary" etc.
    elif "veteran status" in label_lower:
        hardcoded_answer = "I am not a protected veteran" # Or "No", "Decline to self-identify"
    elif "disability status" in label_lower or "disability" in label_lower and "form cc-305" in label_lower:
        hardcoded_answer = "No, I do not have a disability" # Match common option text closely
    elif "sexual orientation" in label_lower:
         hardcoded_answer = "Decline to self-identify"
    elif "transgender" in label_lower:
         hardcoded_answer = "No"

    # Work Authorization
    elif "sponsorship" in label_lower and ("require" in label_lower or "need" in label_lower):
        hardcoded_answer = "Yes" # Based on your previous predefined answers - CHANGE TO "No" if that's the default
    elif "authorized to work" in label_lower or "work authorization" in label_lower or "legally authorized" in label_lower:
        hardcoded_answer = "Yes"

    # Location Question (Will use LLM with context, set flag)
    is_location_question = False
    if "state" in label_lower and "province" in label_lower and "reside" in label_lower:
        is_location_question = True
        logger.info("Detected potential State/Province location question.")

    # --- END Hardcoded Answers & Location Check ---

    try:
        # 1. Find the element (Same logic as before)
        # ... (Keep the element finding logic from the previous version) ...
        possible_locators = [
             f"*:is(input, textarea, select):near(:text('{normalized_label}'), 150)", # Prioritize near text
             f"*:has(label:has-text('{normalized_label}')) >> input:not([type='checkbox']):not([type='radio'])",
             f"*:has(label:has-text('{normalized_label}')) >> textarea",
             f"*:has(label:has-text('{normalized_label}')) >> select",
             f"input[aria-label*='{normalized_label}' i]",
             f"textarea[aria-label*='{normalized_label}' i]",
             f"select[aria-label*='{normalized_label}' i]",
             f"div[role='combobox']:near(:text('{normalized_label}'), 150)",
             f"div[role='radiogroup']:near(:text('{normalized_label}'), 150)",
             f"input[id*='{normalized_label.replace(' ', '-').lower()}']",
        ]
        found_element = None
        element_id = None
        element_name = None
        for selector in possible_locators:
             try:
                  candidate = page.locator(selector).first
                  if await candidate.count() > 0 and await candidate.is_visible(timeout=500):
                        el_id = await candidate.get_attribute("id") or ""
                        el_name = await candidate.get_attribute("name") or ""
                        potential_id = normalized_label or el_id or el_name
                        # Check handled status using refined unique_check_id logic
                        temp_tag = await candidate.evaluate("el => el.tagName.toLowerCase()")
                        temp_role = await candidate.get_attribute("role") or ""
                        temp_check_id = potential_id
                        if temp_tag == "div" and temp_role == "radiogroup": temp_check_id = f"radio_group:{potential_id}"
                        elif temp_tag == "div" and temp_role == "combobox": temp_check_id = f"custom_dropdown:{potential_id}"

                        if temp_check_id not in results["fields_filled"] and temp_check_id not in results["fields_skipped"]:
                            found_element = candidate
                            element_id = el_id
                            element_name = el_name
                            unique_check_id = temp_check_id # Use the refined ID
                            logger.debug(f"AI Fallback: Located element for '{normalized_label}' using selector: {selector}. ID for results: '{unique_check_id}'")
                            break
                        else: logger.debug(f"AI Fallback: Element found by {selector} but ID '{temp_check_id}' already handled.")
             except Exception: continue

        if not found_element:
             logger.warning(f"AI Fallback: Could not locate visible, unhandled element for label '{normalized_label}'.")
             if (normalized_label not in results["fields_filled"]) and (normalized_label not in results["fields_skipped"]):
                 results["fields_skipped"].append(normalized_label) # Skip using original label
             return False
        element = found_element

        # --- Determine Answer: Hardcoded or LLM ---
        answer_to_use = None
        if hardcoded_answer is not None:
             answer_to_use = hardcoded_answer
             logger.info(f"Using hardcoded answer '{answer_to_use}' for '{normalized_label}'.")
        else:
             # Use LLM (existing logic, potentially enhanced for location)
             logger.info(f"No hardcoded answer found for '{normalized_label}'. Querying LLM.")

             # 2. Get Context (Same as before)
             # ... (Keep the context gathering logic: tag_name, role, options_text, is_multi_choice, etc.) ...
             tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
             role = await element.get_attribute("role") or ""
             options_text = []
             is_multi_choice = False
             is_text_input = False
             input_type_attr = ""
             standard_answers = config.get('standard_answers', {}) # Load standard answers here

             if tag_name == "select":
                 options = await element.locator("option").all()
                 options_text = [opt_text for opt in options if (opt_text := await opt.text_content()) and not await opt.is_disabled() and opt_text.strip() and "select" not in opt_text.lower()]
                 is_multi_choice = True
             elif role == "radiogroup":
                 radios = element.locator("input[type='radio']")
                 count = await radios.count()
                 for i in range(count): radio_label = await get_field_label(page, radios.nth(i)); options_text.append(radio_label or f"Option {i+1}")
                 is_multi_choice = True
             elif role == "combobox":
                  is_multi_choice = True
             elif tag_name == "textarea":
                  is_text_input = True
             elif tag_name == "input":
                  input_type_attr = await element.get_attribute("type") or "text"
                  if input_type_attr not in ["checkbox", "radio", "file", "button", "submit", "reset", "image"]:
                       is_text_input = True


             # 3. Construct Prompt for Gemini (modified for location)
             prompt = f"A required field labeled '{field_label}' on a job application form was missed by automation.\n"
             prompt += f"Field Type Guess: '{tag_name}'"
             if role: prompt += f" with role '{role}'."
             if input_type_attr: prompt += f" (type='{input_type_attr}')"
             prompt += "\n\n"
             prompt += "**Resume Summary & Skills:**\n" # Keep resume context
             prompt += f"- Summary: {resume.get('summary', 'N/A')}\n"
             skills_data = resume.get('skills'); # Check type before using
             if isinstance(skills_data, list) and skills_data: prompt += f"- Key Skills: {', '.join(skills_data[:15])}\n"
             elif isinstance(skills_data, str) and skills_data: prompt += f"- Skills (raw string): {skills_data}\n"
             prompt += "\n"

             prompt += "**Field Analysis & Instructions:**\n"
             # --- Location Question Enhancement ---
             if is_location_question:
                  city = resume.get("personal_info", {}).get("city", "N/A")
                  state = resume.get("personal_info", {}).get("state", "N/A")
                  country = resume.get("personal_info", {}).get("country", "N/A")
                  prompt += f"- This field asks for the user's State or Province.\n"
                  prompt += f"- User's Location from Resume: City={city}, State/Province={state}, Country={country}\n"
                  if state != "N/A":
                       prompt += f"- Provide the State/Province: {state}\n"
                  elif city != "N/A":
                      prompt += f"- State/Province missing, but City is {city}. Try using the City if State/Province isn't an option, otherwise respond 'N/A'.\n"
                  else:
                      prompt += "- Location information is missing from resume. Respond 'N/A'.\n"
             # --- End Location Enhancement ---
             else:
                  # Use existing keyword matching and context building logic for OTHER fields
                  keywords_map = config.get('field_keywords', {})
                  context_added = False
                  matched_category = None
                  matched_key = None
                  for category, keywords_dict in keywords_map.items():
                       key = match_field(normalized_label, keywords_dict, fuzzy_threshold)
                       if key: matched_category = category; matched_key = key; break

                  if matched_category == "personal_info":
                      # ... (personal info context logic from previous version) ...
                      resume_val = resume.get("personal_info", {}).get(matched_key)
                      if resume_val:
                          prompt += f"- Appears to be '{matched_key.replace('_',' ')}'. User's value: {resume_val}\n- Provide this exact value.\n"
                          context_added = True
                      else:
                          prompt += f"- Appears to be '{matched_key.replace('_',' ')}', but value missing from resume.\n- Provide standard placeholder or 'N/A'.\n"
                          context_added = True
                  # Add other context checks (salary, experience, availability) as before
                  elif "salary" in label_lower or "compensation" in label_lower:
                       salary_answer = config.get('standard_answers', {}).get('salary_expectation', 'Negotiable')
                       prompt += f"- Field asks for salary expectations.\n- Provide: {salary_answer}\n"
                       context_added = True
                  elif "experience" in label_lower and is_text_input:
                       work_titles = [w.get('title') for w in resume.get('work_experience', []) if w.get('title')]
                       prompt += "- Field asks for experience description.\n"
                       if work_titles: prompt += f"- Relevant Titles: {', '.join(work_titles)}\n"
                       prompt += "- Summarize relevant experience based on label & resume context (1-3 sentences).\n"
                       context_added = True
                  elif "available" in label_lower and "start" in label_lower:
                       availability = config.get('standard_answers', {}).get('availability', 'Immediately')
                       prompt += f"- Field asks about start availability.\n"
                       if options_text: prompt += f"- A standard answer is '{availability}'. Select the best matching option.\n"
                       else: prompt += f"- Provide the answer: {availability}\n"
                       context_added = True


                  # Generic instructions if no specific match (and not location)
                  if not context_added:
                       if is_multi_choice and options_text: prompt += "- Select the most appropriate option based on the field label and general knowledge.\n"
                       elif is_multi_choice: prompt += "- Enter a likely search term or value based on the field label and general knowledge.\n"
                       elif is_text_input: prompt += "- Provide a reasonable text answer based on the field label and general knowledge. If unsure, respond 'N/A'.\n"


             # Add options if available
             if options_text:
                  prompt += f"\n**Available Options:**\n[{', '.join(options_text)}]\n"

             prompt += "\n**Response Format:** Respond ONLY with the precise value or option text to be filled/selected. Do not include explanations. If unable to determine a value, respond ONLY with 'N/A'."

             # 4. Get AI Response
             ai_answer = await get_gemini_response(prompt)
             answer_to_use = ai_answer # Use the AI's answer

        # --- 5. Validate and Fill using answer_to_use ---
        if not answer_to_use or answer_to_use.strip().upper() == "N/A" or len(answer_to_use) > 300:
            logger.warning(f"AI/Hardcoded Fallback: Received unsuitable answer for '{normalized_label}': '{answer_to_use}'. Skipping.")
            if unique_check_id not in results["fields_skipped"] and unique_check_id not in results["fields_filled"]:
                 results["fields_skipped"].append(unique_check_id)
            return False

        logger.info(f"AI/Hardcoded Fallback: Suggests '{answer_to_use[:100]}' for '{normalized_label}'. Attempting to fill.")
        answer_to_use = answer_to_use.strip()

        fill_success = False
        standard_answers = config.get('standard_answers', {}) # Need for helpers

        try:
            # Use same filling logic as before, but using answer_to_use
            if is_text_input:
                await element.fill(answer_to_use, timeout=5000)
                fill_success = True
            elif tag_name == "select":
                 try: await element.select_option(label=answer_to_use, timeout=2000); fill_success = True
                 except:
                     try: await element.select_option(value=answer_to_use, timeout=2000); fill_success = True
                     except:
                         success_fuzzy, _ = await select_matching_option(element, answer_to_use, standard_answers, "dropdown")
                         if success_fuzzy: fill_success = True
            elif role == "combobox":
                 fill_success = await select_custom_dropdown_option(
                     page=page, base_element=element, desired_value=answer_to_use,
                     config=config, results=results, label_text=normalized_label
                 )
            elif role == "radiogroup":
                 success_radio, _ = await select_matching_option(element, answer_to_use, standard_answers, "radio")
                 if success_radio: fill_success = True

            # Update results
            if fill_success:
                if unique_check_id not in results["fields_filled"]:
                    results["fields_filled"].append(unique_check_id)
                if unique_check_id in results["fields_skipped"]:
                    results["fields_skipped"].remove(unique_check_id)
                logger.info(f"✅ AI/Hardcoded Fallback: Successfully filled '{normalized_label}' using ID '{unique_check_id}'.")
                return True
            else:
                 logger.warning(f"AI/Hardcoded Fallback: Could not fill '{normalized_label}' with suggested answer '{answer_to_use}' using known methods.")
                 if unique_check_id not in results["fields_skipped"] and unique_check_id not in results["fields_filled"]:
                      results["fields_skipped"].append(unique_check_id)
                 return False

        except Exception as fill_err:
            logger.error(f"AI/Hardcoded Fallback: Error performing fill action for field '{normalized_label}': {fill_err}")
            if unique_check_id not in results["fields_skipped"] and unique_check_id not in results["fields_filled"]:
                 results["fields_skipped"].append(unique_check_id)
            return False

    except Exception as e:
        logger.error(f"AI/Hardcoded Fallback: General error processing field '{normalized_label}': {e}", exc_info=True)
        final_id = unique_check_id or normalized_label
        if final_id not in results["fields_skipped"] and final_id not in results["fields_filled"]:
             results["fields_skipped"].append(final_id)
        return False


async def take_screenshot(page: Page, job_id: Optional[str], base_dir: str, suffix: str) -> str:
    """Take a screenshot and return the path."""
    try:
        timestamp = int(time.time())
        filename = f"job_{job_id or 'unknown'}_{suffix}_{timestamp}.png"
        screenshot_path = os.path.join(base_dir, filename)
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True) # Ensure directory exists
        await page.screenshot(path=screenshot_path, full_page=True, timeout=10000) # Add timeout
        return screenshot_path
    except Exception as e:
        logger.error(f"Failed to take screenshot '{suffix}': {str(e)}")
        return ""



async def find_submit_button(page: Page, selectors: List[str]) -> Optional[Locator]:
    """Find the form's submit button using configured selectors."""
    logger.debug("Finding submit button...")
    for selector in selectors:
        try:
            submit_button = page.locator(selector)
            count = await submit_button.count()
            # Find the first visible and enabled button matching the selector
            for i in range(count):
                 button = submit_button.nth(i)
                 if await button.is_visible(timeout=1000) and await button.is_enabled(timeout=1000):
                     logger.info(f"Found submit button using selector: {selector}")
                     return button
        except Exception as e:
             logger.debug(f"Error checking submit selector '{selector}': {e}")
             continue # Try next selector

    logger.warning("Could not find a visible and enabled submit button using configured selectors.")
    return None


async def check_for_validation_errors(page: Page, error_selectors: List[str]) -> Optional[List[str]]:
    """Checks if any validation error messages are visible on the page."""
    logger.info("Checking for visible validation errors...")
    visible_errors = []
    error_selector_str = ", ".join(error_selectors)
    if not error_selector_str: return None

    try:
        error_elements = page.locator(error_selector_str)
        count = await error_elements.count()
        if count == 0:
             logger.info("No elements matching error selectors found.")
             return None

        logger.debug(f"Found {count} potential error elements.")
        for i in range(count):
             element = error_elements.nth(i)
             try:
                  if await element.is_visible(timeout=500):
                       error_text = await element.text_content(timeout=500) or "[Empty Error]"
                       # Filter out empty / non-error like messages
                       if error_text.strip() and len(error_text.strip()) > 3:
                            logger.warning(f"Visible validation error found: {error_text.strip()}")
                            visible_errors.append(error_text.strip())
             except Exception: pass # Ignore errors checking individual elements

        # Remove duplicates
        unique_errors = list(dict.fromkeys(visible_errors))
        return unique_errors if unique_errors else None
    except Exception as e:
        logger.error(f"Error while checking for validation errors: {e}")
        return None

async def check_for_success_indicators(page: Page, success_selectors: List[str], apply_url: str) -> Optional[str]:
     """Checks for success indicators (text, selectors, URL change)."""
     success_indicator = None
     try:
         # Check common text/selectors from config
         for selector in success_selectors:
             try:
                 success_element = page.locator(selector).first
                 # Use a slightly longer timeout for success checks
                 if await success_element.count() > 0 and await success_element.is_visible(timeout=3000):
                     success_indicator = selector
                     logger.info(f"✅ Success indicator found: {selector}")
                     return success_indicator # Return first one found
             except PlaywrightTimeoutError:
                 continue
             except Exception as e:
                  logger.warning(f"Error checking success selector {selector}: {e}")

         # If no explicit success message, check if URL significantly changed
         current_url = page.url
         # Check if not original URL and doesn't contain obvious error terms
         if apply_url not in current_url and not any(err in current_url.lower() for err in ["error", "fail", "login", "signin"]):
             logger.info(f"URL changed significantly after submission: {apply_url} -> {current_url}. Assuming success.")
             success_indicator = f"URL Change to {current_url}"
             return success_indicator

     except Exception as e:
          logger.error(f"Error checking for success indicators: {e}")

     return success_indicator # Return None if nothing found
 
async def job_processing_service(config: Dict[str, Any]):
    """Main job processing service loop."""
    queue_manager = QueueManager(config)
    resume = load_resume_data(config)
    max_retries = config.get('agent_settings', {}).get('max_job_retries', 2)
    delay_between_jobs = config.get('agent_settings', {}).get('delay_between_jobs', 8.0)
    headless_mode = not config.get('agent_settings', {}).get('testing_mode', False) # Run headless unless testing_mode=true

    logger.info("Job processing service started.")
    logger.info(f"Initial queue stats: {queue_manager.get_queue_stats()}")

    run_continuously = True
    while run_continuously:
        job = None # Ensure job is None at start of loop
        try:
            logger.info("-" * 30) # Separator
            logger.info("Checking for next job...")
            job = queue_manager.get_next_job()

            if not job:
                logger.info(f"No jobs in queue. Waiting for {delay_between_jobs} seconds...")
                await asyncio.sleep(delay_between_jobs)
                continue

            job_id = job.get('id')
            logger.info(f"Processing job {job_id} (Attempt {job.get('attempts', 0) + 1}/{max_retries + 1})")

            # Process the job using the main process_job function
            success, message, details = await process_job(job, resume, config, headless=headless_mode)

            # Update job status based on result
            if success:
                logger.info(f"Job {job_id} completed successfully: {message}")
                queue_manager.mark_job_complete(job_id, details)
            else:
                # Determine failure category
                is_captcha = "captcha detected" in message.lower()
                # Check for ambiguous status explicitly
                is_ambiguous = details.get("status_ambiguous", False) if details else False
                needs_review = "missing required fields" in message.lower() or \
                               "submit button not found" in message.lower() or \
                               "validation errors" in message.lower() or \
                               is_ambiguous or \
                               is_captcha

                if needs_review:
                    review_reason = f"Needs Review: {message}"
                    if is_captcha: review_reason = f"CAPTCHA Review: {message}"
                    elif is_ambiguous: review_reason = f"Ambiguous Status: {message}"
                    logger.warning(f"Job {job_id} needs manual review: {review_reason}")
                    queue_manager.mark_job_needs_review(job_id, review_reason, details)
                else:
                    # General failure, check retry logic
                    should_retry = job.get('attempts', 0) < max_retries
                    logger.warning(f"Job {job_id} failed: {message}")
                    queue_manager.mark_job_failed(job_id, message, details, retry=should_retry, max_retries=max_retries)

            # Wait a bit before processing the next job
            logger.info(f"Waiting {delay_between_jobs} seconds before next job check...")
            await asyncio.sleep(delay_between_jobs)

        except KeyboardInterrupt:
             logger.info("KeyboardInterrupt received, stopping service loop.")
             run_continuously = False
             if job:
                  job_id_interrupt = job.get('id', 'Unknown')
                  logger.warning(f"Service stopped while job {job_id_interrupt} was potentially processing. Marking for retry.")
                  # Mark for retry regardless of previous attempts when interrupted
                  queue_manager.mark_job_failed(job_id_interrupt, "Service interrupted", details={"interrupted": True}, retry=True, max_retries=max_retries)

        except Exception as e:
            logger.critical(f"CRITICAL ERROR in job processing loop: {str(e)}")
            logger.critical(traceback.format_exc())
            if job:
                 job_id_err = job.get('id', 'Unknown ID')
                 logger.error(f"Marking job {job_id_err} as failed due to loop error (will retry if possible).")
                 queue_manager.mark_job_failed(job_id_err, f"Service loop error: {e}", details={"loop_error": str(e)}, retry=True, max_retries=max_retries)

            logger.info("Waiting 30 seconds after critical error...")
            await asyncio.sleep(30)

    logger.info("Job processing service finished.")

# Main guard
if __name__ == "__main__":
    print("This script is not intended to be run directly.")
    print("Run agent/main.py instead.")
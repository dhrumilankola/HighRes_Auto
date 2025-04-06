import logging
import re
import asyncio
import os
from typing import Dict, List, Any, Optional, Tuple, Union

from playwright.async_api import Page, Locator, ElementHandle, TimeoutError as PlaywrightTimeoutError
from fuzzywuzzy import fuzz # Import fuzzywuzzy
from gemini_helper import get_selectors_from_gemini # Keep AI selector helper
from resume_loader import get_resume_pdf_path

# Configure logging (already configured in main, but get logger)
logger = logging.getLogger("form_improvements")

# --- Configuration Dependent Constants (Defaults if config fails) ---
FUZZY_MATCH_THRESHOLD = 85 # Default score threshold for fuzzy matching
DELAY_BETWEEN_ACTIONS = 0.2 # Default small delay

def load_form_config(config: Dict[str, Any]):
    """Loads relevant settings from the main config for form filling."""
    global FUZZY_MATCH_THRESHOLD, DELAY_BETWEEN_ACTIONS
    agent_settings = config.get('agent_settings', {})
    FUZZY_MATCH_THRESHOLD = agent_settings.get('fuzzy_match_threshold', 85)
    DELAY_BETWEEN_ACTIONS = agent_settings.get('delay_between_actions', 0.2)
    logger.info(f"Form Improvement Settings: Fuzzy Threshold={FUZZY_MATCH_THRESHOLD}, Action Delay={DELAY_BETWEEN_ACTIONS}")


# --- Enhanced Field Label Identification ---

async def get_field_label(page: Page, element: Locator) -> Optional[str]:
    """
    Try various methods to get the label text associated with a form element.
    Prioritizes explicit associations (for, aria-labelledby, aria-label).
    """
    element_handle: Optional[ElementHandle] = None
    label_text: Optional[str] = None

    try:
        element_handle = await element.element_handle(timeout=1000) # Short timeout for handle
        if not element_handle: return None

        # --- Direct Association Methods ---
        # Method 1: aria-label
        aria_label = await element.get_attribute("aria-label", timeout=500)
        if aria_label: return aria_label.strip()

        # Method 2: aria-labelledby
        aria_labelledby = await element.get_attribute("aria-labelledby", timeout=500)
        if aria_labelledby:
            ids = aria_labelledby.split()
            label_texts = []
            for label_id in ids:
                label_elem = page.locator(f"#{label_id}")
                if await label_elem.count() > 0:
                    try:
                        text = await label_elem.first.text_content(timeout=500)
                        if text: label_texts.append(text.strip())
                    except Exception: pass # Ignore if element disappears
            if label_texts: return " ".join(label_texts)

        # Method 3: Associated label using 'for' attribute
        element_id = await element.get_attribute("id", timeout=500)
        if element_id:
            # Escape CSS identifiers if necessary (though simple IDs are common)
            # escaped_id = re.sub(r'([^\\])\.([^\\])', r'\1\\.\2', element_id) # Basic dot escaping
            label = page.locator(f"label[for='{element_id}']")
            if await label.count() > 0:
                try:
                    text = await label.first.text_content(timeout=500)
                    # Check if the label itself contains the input (common pattern)
                    if text and await label.locator(f"#{element_id}").count() == 0:
                         return text.strip()
                except Exception: pass

        # --- Positional & Contextual Methods ---
        # Method 4: Parent label (element inside label) - More reliable check
        try:
             parent_label_text = await element_handle.evaluate("""
                 el => {
                     let parent = el.parentElement;
                     if (parent && parent.tagName === 'LABEL') {
                         // Return text content excluding the input's own text/value if possible
                         const clone = parent.cloneNode(true);
                         const inputClone = clone.querySelector('#' + el.id) || clone.querySelector('[name="' + el.name + '"]') || clone.querySelector(el.tagName);
                         if (inputClone) inputClone.remove();
                         return clone.textContent?.trim();
                     }
                     // Check if grandparent is label (e.g., div wrapping input inside label)
                     if (parent && parent.parentElement && parent.parentElement.tagName === 'LABEL') {
                           const clone = parent.parentElement.cloneNode(true);
                           const inputClone = clone.querySelector('#' + el.id) || clone.querySelector('[name="' + el.name + '"]') || clone.querySelector(el.tagName);
                           if (inputClone) inputClone.remove();
                           return clone.textContent?.trim();
                     }
                     return null;
                 }
             """)
             if parent_label_text: return parent_label_text
        except Exception: pass


        # Method 5: Look for preceding sibling label or heading/strong tag (improved)
        try:
            nearby_text = await element_handle.evaluate("""
                el => {
                    let current = el;
                    for (let i = 0; i < 3; i++) { // Check element and up to 2 parents
                        if (!current) break;
                        let sibling = current.previousElementSibling;
                        while (sibling) {
                            if (sibling.tagName === 'LABEL') return sibling.textContent?.trim();
                            // Check for common heading/strong patterns used as labels
                            if (['H1','H2','H3','H4','H5','H6','STRONG'].includes(sibling.tagName)) return sibling.textContent?.trim();
                            // Check for divs that look like labels
                             if (sibling.tagName === 'DIV' && (sibling.className.toLowerCase().includes('label') || sibling.getAttribute('role') === 'label')) return sibling.textContent?.trim();

                            sibling = sibling.previousElementSibling;
                        }
                        // Also check parent's previous sibling if element is wrapped
                         if (current.parentElement) {
                              sibling = current.parentElement.previousElementSibling;
                              if (sibling && sibling.tagName === 'LABEL') return sibling.textContent?.trim();
                              if (sibling && ['H1','H2','H3','H4','H5','H6','STRONG'].includes(sibling.tagName)) return sibling.textContent?.trim();
                         }

                        current = current.parentElement; // Move up the DOM
                    }
                    return null;
                }
            """)
            if nearby_text: return nearby_text
        except Exception as e:
            # logger.debug(f"Error evaluating JS for nearby label: {e}") # Too verbose maybe
            pass

        # Method 6: Placeholder attribute as fallback
        placeholder = await element.get_attribute("placeholder", timeout=500)
        if placeholder:
            return placeholder.strip()

        # Method 7: Title attribute as fallback
        title = await element.get_attribute("title", timeout=500)
        if title:
             return title.strip()

    except PlaywrightTimeoutError:
        logger.warning(f"Timeout trying to get label info for an element.")
    except Exception as e:
        logger.error(f"Error getting field label: {e}", exc_info=False) # Avoid full trace usually
    finally:
        if element_handle:
            try: await element_handle.dispose()
            except: pass # Ignore disposal errors

    return None # Could not find a label

# --- Field Matching Logic ---

def match_field(combined_text: str, keywords_dict: Dict[str, List[str]], threshold: int) -> Optional[str]:
    """
    Matches combined field text (label, id, name, placeholder) against keyword lists
    using fuzzy matching. Returns the matched key (e.g., 'first_name') or None.
    """
    if not combined_text: return None
    text_lower = combined_text.lower()
    best_match_key = None
    highest_score = threshold - 1 # Initialize below threshold

    for key, keywords in keywords_dict.items():
        for keyword in keywords:
            # Using token_set_ratio is generally good for matching phrases regardless of word order
            # and partial matches. Adjust ratio type if needed.
            score = fuzz.token_set_ratio(text_lower, keyword.lower())
            if score > highest_score:
                highest_score = score
                best_match_key = key
            # Optimization: If exact match found, use it immediately (score 100)
            if score == 100:
                return key
            # Early exit if perfect keyword match (less fuzzy)
            if keyword.lower() in text_lower and score > threshold: # Check substring presence too
                 # If keyword is present and score is good, likely a good match
                 # Could add length check to avoid 'name' matching 'first name' too easily
                 if len(keyword) > 3 or score > 90: # Heuristic
                      # Prioritize longer or higher-scoring keyword matches
                      if best_match_key != key or score > highest_score:
                          highest_score = score # Update score even if key is the same
                          best_match_key = key


    if highest_score >= threshold:
        logger.debug(f"Fuzzy matched '{combined_text}' to key '{best_match_key}' with score {highest_score}")
        return best_match_key
    else:
        logger.debug(f"No sufficient fuzzy match for '{combined_text}'. Best score {highest_score} for key '{best_match_key}' (Threshold: {threshold})")
        return None


# --- Filling Functions (Using Config and Fuzzy Matching) ---

async def fill_personal_info(page: Page, resume: Dict[str, Any], config: Dict[str, Any], results: Dict[str, Any]) -> None:
    """Fill all personal information fields using config keywords and fuzzy matching."""
    logger.info("Filling personal information fields...")
    personal_info_data = resume.get("personal_info", {})
    keywords = config.get('field_keywords', {}).get('personal_info', {})
    filled_in_this_pass = set()
    inputs = page.locator("input[type='text'], input[type='email'], input[type='tel'], input[type='url'], input:not([type]), textarea")
    count = await inputs.count()

    for i in range(count):
        input_elem = inputs.nth(i)
        unique_check_id = f"personal_input_{i}" # Default unique id
        label_text = None # Ensure label_text is defined for logging scope
        try:
            if not await input_elem.is_visible(timeout=500): continue
            if await input_elem.is_disabled(timeout=500): continue
            current_value = await input_elem.input_value(timeout=1000)
            if current_value: continue

            label_text = await get_field_label(page, input_elem)
            field_id = await input_elem.get_attribute("id") or ""
            field_name = await input_elem.get_attribute("name") or ""
            placeholder = await input_elem.get_attribute("placeholder") or ""
            combined_text = f"{label_text or ''} {field_id} {field_name} {placeholder}".strip()
            # Refine unique check id
            unique_check_id = label_text or field_id or field_name or f"personal_input_{i}"

            if unique_check_id in results["fields_filled"] or unique_check_id in results["fields_skipped"]:
                continue

            matched_key = match_field(combined_text, keywords, FUZZY_MATCH_THRESHOLD)
            value_to_fill = None

            if matched_key:
                if matched_key == "full_name":
                     fname = personal_info_data.get("first_name", "")
                     lname = personal_info_data.get("last_name", "")
                     if fname and lname: value_to_fill = f"{fname} {lname}"
                elif matched_key == "phone":
                    phone_raw = personal_info_data.get(matched_key, "")
                    value_to_fill = re.sub(r'\D', '', phone_raw)
                # **** START FIX for LinkedIn ****
                elif matched_key == "linkedin":
                    # Explicitly look for linkedin_url in resume data
                    value_to_fill = personal_info_data.get("linkedin_url", "")
                elif matched_key == "portfolio":
                     # Explicitly look for portfolio_url
                     value_to_fill = personal_info_data.get("portfolio_url", "")
                # **** END FIX for LinkedIn ****
                else:
                    # Default lookup using the matched key
                    value_to_fill = personal_info_data.get(matched_key, "")

            # Fill if a value was found AND the value is not empty/None
            if value_to_fill: # Check if value_to_fill has content
                 # Log truncated value for potentially long URLs/etc.
                 log_value = value_to_fill[:50] + '...' if len(value_to_fill) > 50 else value_to_fill
                 logger.info(f"Attempting to fill '{matched_key}' field (Label: '{label_text}') with value '{log_value}'")
                 await input_elem.fill(value_to_fill, timeout=5000)
                 await asyncio.sleep(DELAY_BETWEEN_ACTIONS)
                 results["fields_filled"].append(unique_check_id)
                 filled_in_this_pass.add(unique_check_id)
                 logger.info(f"✅ Filled '{matched_key}' field (Label: '{label_text}').")
            elif matched_key:
                 logger.warning(f"Matched field for '{matched_key}' (Label: '{label_text}') but no corresponding value found in resume data (value was empty or None).")
                 results["fields_skipped"].append(unique_check_id)

        except PlaywrightTimeoutError:
            logger.warning(f"Timeout interacting with potential personal info field (Label: {label_text or 'N/A'}). Skipping.")
            if unique_check_id: results["fields_skipped"].append(unique_check_id)
        except Exception as e:
            label_text_err = label_text or field_id or f"input_{i}"
            error_msg = f"Error filling personal info field '{label_text_err}': {e}"
            if error_msg not in results.get("errors", []): results["errors"].append(error_msg)
            logger.error(f"⚠️ {error_msg}", exc_info=False)
            if unique_check_id: results["fields_skipped"].append(unique_check_id)


async def upload_resume_file(page: Page, config: Dict[str, Any], results: Dict[str, Any]) -> bool:
    """Upload resume file with improved locators and error handling."""
    logger.info("Handling resume upload...")
    # Use helper function from resume_loader to get path from config
    resume_pdf_path = get_resume_pdf_path(config)

    if not resume_pdf_path:
        error_msg = "Resume PDF file path not found or file doesn't exist (checked config)."
        if error_msg not in results.get("errors", []): results["errors"].append(error_msg)
        logger.error(f"⚠️ {error_msg}")
        results["fields_skipped"].append("Resume upload (file not found)")
        return False

    # Improved Locators: Prioritize specific labels/attributes, then general inputs, then buttons that might trigger inputs
    # Combine selectors using Playwright's recommended syntax if needed, or check sequentially.
    # Using sequential checks for clarity here.

    # Priority 1: Direct file inputs with relevant labels/IDs
    priority_selectors = [
        "input[type='file'][aria-label*='resume' i]",
        "input[type='file'][aria-label*='cv' i]",
        "input[type='file'][id*='resume' i]",
        "input[type='file'][id*='cv' i]",
        "input[type='file'][name*='resume' i]",
        "input[type='file'][name*='cv' i]",
        "label:has-text('Resume')" + " >> input[type='file']", # Input following label
        "label:has-text('CV')" + " >> input[type='file']",
        "*:near(:text('Resume'), 150) >> input[type='file']", # Input near text "Resume"
        "*:near(:text('CV'), 150) >> input[type='file']",
        "[data-automation-id='resumeUpload'] input[type='file']", # Workday pattern
    ]

    # Priority 2: General file inputs (might be for cover letter, check label if possible)
    general_selectors = [
        "input[type='file']"
    ]

    # Priority 3: Buttons/Links that likely trigger a file input
    trigger_selectors = [
        "button:has-text('Upload Resume')", "button:has-text('Attach Resume')",
        "button:has-text('Upload CV')", "button:has-text('Attach CV')",
        "a:has-text('Upload Resume')", "a:has-text('Attach Resume')",
        "[data-testid*='upload-resume']",
        "button[aria-label*='upload resume' i]",
    ]

    # Keep track of inputs we've tried to avoid redundant attempts
    tried_input_elements = set()
    success = False

    async def try_upload_to_input(file_input: Locator, identifier: str):
        nonlocal success, tried_input_elements
        if success: return True
        try:
            # Check visibility and enabled status efficiently
            if not await file_input.is_visible(timeout=1000) or not await file_input.is_enabled(timeout=1000):
                logger.debug(f"Skipping upload attempt for {identifier}: not visible or enabled.")
                return False

            # Check if we've already tried this exact element handle
            handle = await file_input.element_handle()
            if not handle or handle in tried_input_elements:
                 if handle: await handle.dispose()
                 return False
            tried_input_elements.add(handle) # Add handle to tried set

            logger.info(f"Attempting resume upload using: {identifier}")
            await file_input.set_input_files(resume_pdf_path, timeout=20000) # Increased timeout for upload action
            await asyncio.sleep(1.0) # Wait for potential client-side updates

            # Basic Verification: Check if the input now has a value (file name)
            # This isn't foolproof but better than nothing.
            if await file_input.input_value(timeout=1000):
                logger.info(f"✅ Resume appears uploaded successfully via {identifier}.")
                results["fields_filled"].append(f"Resume upload ({identifier})")
                success = True
                await handle.dispose() # Dispose handle after successful use
                return True
            else:
                 logger.warning(f"Upload via {identifier} completed, but input value is still empty. Upload might have failed silently.")
                 await handle.dispose() # Dispose handle even if validation fails
                 return False

        except PlaywrightTimeoutError:
             logger.warning(f"Timeout during upload attempt for {identifier}.")
             if handle: await handle.dispose() # Dispose on error too
             return False
        except Exception as e:
             logger.warning(f"Error uploading resume via {identifier}: {e}")
             if handle: await handle.dispose()
             return False

    # --- Attempt Upload ---
    # Try Priority 1 Selectors
    logger.debug("Trying priority file input selectors...")
    for i, selector in enumerate(priority_selectors):
        if success: break
        inputs = page.locator(selector)
        count = await inputs.count()
        for j in range(count):
            if await try_upload_to_input(inputs.nth(j), f"priority selector {i+1}"): break

    # Try Priority 3 Selectors (Click trigger, then find input)
    if not success:
         logger.debug("Trying trigger button/link selectors...")
         for i, selector in enumerate(trigger_selectors):
              if success: break
              triggers = page.locator(selector)
              count = await triggers.count()
              for j in range(count):
                   trigger = triggers.nth(j)
                   if await trigger.is_visible(timeout=1000) and await trigger.is_enabled(timeout=1000):
                        logger.info(f"Clicking potential resume upload trigger: {selector}")
                        try:
                            # Use page.expect_file_chooser to handle the dialog triggered by click
                            async with page.expect_file_chooser(timeout=5000) as fc_info:
                                await trigger.click(timeout=3000)
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(resume_pdf_path)
                            await asyncio.sleep(1.0) # Wait for potential updates

                            # Verification: Often harder after chooser, maybe check near trigger for filename text
                            # For now, assume success if no error
                            logger.info(f"✅ Resume uploaded successfully via file chooser triggered by: {selector}")
                            results["fields_filled"].append(f"Resume upload (triggered by {selector})")
                            success = True
                            break # Break inner loop once successful
                        except PlaywrightTimeoutError:
                            logger.warning(f"Timeout waiting for file chooser after clicking {selector}.")
                        except Exception as e:
                            logger.warning(f"Error clicking trigger {selector} or using file chooser: {e}")
                   if success: break # Break outer loop if successful

    # Try Priority 2 Selectors (General file inputs)
    if not success:
        logger.debug("Trying general file input selectors...")
        for i, selector in enumerate(general_selectors):
            if success: break
            inputs = page.locator(selector)
            count = await inputs.count()
            for j in range(count):
                # Get label to provide context (avoid uploading resume to cover letter field)
                input_elem = inputs.nth(j)
                label = await get_field_label(page, input_elem) or "general file input"
                if "cover" in label.lower() or "portfolio" in label.lower(): # Avoid common mis-uploads
                    logger.debug(f"Skipping general file input with label '{label}' - likely not for resume.")
                    continue
                if await try_upload_to_input(input_elem, f"general selector '{label}'"): break


    # --- Final Result ---
    if not success:
        if "Resume upload (file not found)" not in results["fields_skipped"]:
            results["fields_skipped"].append("Resume upload (failed to find element or upload)")
        logger.error("❌ Failed to upload resume with any detected method.")

    # Dispose any remaining handles in the set
    for handle in tried_input_elements:
        try: await handle.dispose()
        except: pass

    return success

# --- Placeholder for Education Fields (To be implemented with repeating sections logic) ---
async def fill_education_fields(page: Page, resume: Dict[str, Any], config: Dict[str, Any], results: Dict[str, Any]) -> None:
    logger.info("Skipping education fields - requires repeating section logic (Iteration 2).")
    # TODO: Implement logic to find education section(s) and handle "Add Education"
    results["fields_skipped"].append("Education Section (Not Implemented Yet)")


# --- Placeholder for Work Experience Fields ---
async def fill_work_experience_fields(page: Page, resume: Dict[str, Any], config: Dict[str, Any], results: Dict[str, Any]) -> None:
    logger.info("Skipping work experience fields - requires repeating section logic (Iteration 2).")
    # TODO: Implement logic to find work experience section(s) and handle "Add Experience"
    results["fields_skipped"].append("Work Experience Section (Not Implemented Yet)")

# --- Common Dropdowns, Radios, Checkboxes (Using Config and Fuzzy Matching) ---

async def select_matching_option(element: Locator, desired_value: Union[str, bool], standard_answers: Dict[str, Any], element_type: str = "dropdown") -> Tuple[bool, Optional[str]]:
    """
    Finds and selects the best matching option in a dropdown or radio group.

    Returns:
        Tuple[bool, Optional[str]]: (Success flag, Selected option text/value or None)
    """
    options = []
    selected_option_info = None
    best_match_score = -1
    selected_text = None

    try:
        if element_type == "dropdown":
            # Get options for standard select
            options_raw = await element.evaluate("""
                select => Array.from(select.options).map(option => ({
                    value: option.value,
                    text: option.text?.trim(),
                    disabled: option.disabled
                }))
            """)
            options = [opt for opt in options_raw if opt.get('text') and not opt.get('disabled')]
        elif element_type == "radio":
            # Radio buttons need to be located relative to the group element passed
            option_locators = element.locator("input[type='radio']")
            count = await option_locators.count()
            for i in range(count):
                 radio = option_locators.nth(i)
                 if not await radio.is_enabled(timeout=500): continue
                 value = await radio.get_attribute("value") or ""
                 label = await get_field_label(element.page, radio) or value # Pass page explicitly if needed
                 options.append({"value": value, "text": label, "locator": radio}) # Store locator for clicking

    except Exception as e:
        logger.error(f"Error getting options for {element_type}: {e}")
        return False, None

    if not options:
        logger.warning(f"No valid options found for {element_type}.")
        return False, None

    # Determine the actual value to look for (e.g., "Yes", "No", "Decline...", specific race)
    target_value_str = str(desired_value)

    # Match options against the target value
    for option in options:
        option_text = option.get("text", "")
        option_value = option.get("value", "") # Sometimes value matters too
        option_text_lower = option_text.lower()
        current_score = -1

        # Simple matching logic (can be expanded)
        # Prioritize exact matches on text or value
        if target_value_str.lower() == option_text_lower: current_score = 100
        elif target_value_str.lower() == option_value.lower(): current_score = 95 # Value match slightly lower priority
        # Fuzzy matching on text
        elif option_text:
            score = fuzz.token_set_ratio(target_value_str.lower(), option_text_lower)
            if score >= FUZZY_MATCH_THRESHOLD: current_score = score

        # Boost scores for common patterns (Yes/No/Decline)
        # Use standard answers config for keywords
        yes_keywords = standard_answers.get('yes_no', {}).get('yes', ['yes'])
        no_keywords = standard_answers.get('yes_no', {}).get('no', ['no'])
        decline_keywords = ["decline", "prefer not", "do not wish"] # Common decline phrases

        if any(kw in option_text_lower for kw in yes_keywords) and target_value_str.lower() == 'yes':
            current_score = max(current_score, 90) # High score for semantic 'yes'
        elif any(kw in option_text_lower for kw in no_keywords) and target_value_str.lower() == 'no':
             # Avoid matching "I do not wish..." if target is just "No"
             is_decline = any(dkw in option_text_lower for dkw in decline_keywords)
             if not is_decline: current_score = max(current_score, 90) # High score for semantic 'no'
        elif any(kw in option_text_lower for kw in decline_keywords) and any(kw in target_value_str.lower() for kw in decline_keywords):
            current_score = max(current_score, 95) # High score for 'decline' match

        # Specific known answers (e.g., veteran status)
        if target_value_str.lower() in option_text_lower and len(target_value_str) > 10: # Match longer standard answers well
             current_score = max(current_score, 98)


        if current_score > best_match_score:
            # Skip placeholder options like "Select..." unless it's the only option
            if "select" in option_text_lower and len(options) > 1 and current_score < 100:
                continue
            best_match_score = current_score
            selected_option_info = option
            selected_text = option_text

    # Select the best match if found
    if selected_option_info:
        try:
            if element_type == "dropdown":
                await element.select_option(value=selected_option_info["value"], timeout=3000)
            elif element_type == "radio":
                await selected_option_info["locator"].check(timeout=3000)

            logger.info(f"✅ Selected {element_type} option '{selected_text}' (Score: {best_match_score})")
            await asyncio.sleep(DELAY_BETWEEN_ACTIONS)
            return True, selected_text
        except Exception as e:
            logger.error(f"Error selecting {element_type} option '{selected_text}': {e}")
            return False, selected_text # Return text even if click failed
    else:
        logger.warning(f"No suitable option found for value '{target_value_str}' in {element_type}.")
        return False, None


async def fill_standard_dropdowns(page: Page, config: Dict[str, Any], resume: Dict[str, Any], results: Dict[str, Any]) -> None:
    """Fill standard select dropdowns using config keywords and standard answers."""
    logger.info("Filling standard dropdowns...")
    keywords_map = config.get('field_keywords', {})
    standard_answers = config.get('standard_answers', {})
    filled_in_this_pass = set()

    selects = page.locator("select")
    count = await selects.count()

    for i in range(count):
        select_elem = selects.nth(i)
        try:
            if not await select_elem.is_visible(timeout=500): continue
            if not await select_elem.is_enabled(timeout=500): continue

            # Avoid re-filling if already selected (check value is not empty/default)
            current_value = await select_elem.input_value(timeout=500)
            if current_value and current_value not in ["", "0", "-1"] and "select" not in current_value.lower():
                 continue

            label_text = await get_field_label(page, select_elem)
            field_id = await select_elem.get_attribute("id") or ""
            field_name = await select_elem.get_attribute("name") or ""
            combined_text = f"{label_text or ''} {field_id} {field_name}".strip()
            unique_check_id = label_text or field_id or field_name or f"select_{i}"

            if not combined_text or (unique_check_id in results["fields_filled"]) or (unique_check_id in results["fields_skipped"]):
                continue

            # Find the category and desired value based on keywords
            matched_key_category = None # e.g., 'work_authorization', 'demographics'
            matched_keyword_key = None # e.g., 'authorized', 'race_ethnicity'
            desired_value = None

            for category, keywords_dict in keywords_map.items():
                # Skip personal/education/experience as they are handled separately
                if category in ['personal_info', 'education', 'work_experience']: continue
                key = match_field(combined_text, keywords_dict, FUZZY_MATCH_THRESHOLD)
                if key:
                    matched_key_category = category
                    matched_keyword_key = key
                    # Get the standard answer for this key from the config
                    if category in standard_answers and key in standard_answers[category]:
                        desired_value = standard_answers[category][key]
                    # Handle special cases like yes/no based on category if needed
                    elif key in standard_answers.get('yes_no', {}):
                        desired_value = standard_answers['yes_no'][key][0] # Take first keyword e.g. "Yes"
                    break # Found a match

            if desired_value is not None:
                logger.info(f"Attempting to select standard dropdown '{label_text or unique_check_id}' for '{matched_keyword_key}' with value '{desired_value}'")
                success, _ = await select_matching_option(select_elem, desired_value, standard_answers, "dropdown")
                if success:
                    results["fields_filled"].append(unique_check_id)
                else:
                     logger.warning(f"Failed to select option for standard dropdown '{label_text or unique_check_id}'")
                     results["fields_skipped"].append(unique_check_id)
            elif matched_keyword_key:
                 logger.warning(f"Matched standard dropdown '{label_text or unique_check_id}' to '{matched_keyword_key}' but no standard answer defined in config.")
                 results["fields_skipped"].append(unique_check_id)

        except PlaywrightTimeoutError:
             logger.warning(f"Timeout interacting with standard dropdown {i}. Skipping.")
             if unique_check_id: results["fields_skipped"].append(unique_check_id)
        except Exception as e:
            label_text_err = label_text or field_id or f"select_{i}"
            error_msg = f"Error filling standard dropdown '{label_text_err}': {e}"
            if error_msg not in results.get("errors", []): results["errors"].append(error_msg)
            logger.error(f"⚠️ {error_msg}", exc_info=False)
            if unique_check_id: results["fields_skipped"].append(unique_check_id)


async def fill_custom_dropdowns(page: Page, config: Dict[str, Any], resume: Dict[str, Any], results: Dict[str, Any]) -> None:
    """Fill custom dropdowns using known selectors, AI fallback, config keywords and standard answers."""
    logger.info("Filling custom dropdowns...")
    known_selectors = config.get('common_selectors', {}).get('custom_dropdown', {})
    keywords_map = config.get('field_keywords', {})
    standard_answers = config.get('standard_answers', {})
    filled_in_this_pass = set()

    # Use combined selectors for containers
    container_selector = ", ".join(known_selectors.get('container', []))
    if not container_selector:
         logger.warning("No common selectors found for custom dropdown containers in config.")
         return

    containers = page.locator(container_selector)
    count = await containers.count()
    logger.info(f"Found {count} potential custom dropdown containers using selectors: {container_selector}")

    for i in range(count):
        container_elem = containers.nth(i)
        try:
            if not await container_elem.is_visible(timeout=1000): continue
            # Add more checks? e.g., ensure it has an input or button inside?

            label_text = await get_field_label(page, container_elem)
            # Use label as the primary identifier for custom dropdowns
            unique_check_id = f"custom_dropdown:{label_text}" if label_text else f"custom_dropdown_index_{i}"

            if not label_text or (unique_check_id in results["fields_filled"]) or (unique_check_id in results["fields_skipped"]):
                if not label_text: logger.debug(f"Skipping custom dropdown {i}, no label found.")
                continue

            # Check if it looks filled already (more robust check needed)
            # Example: Look for a selected value indicator excluding placeholder text
            selected_indicator = container_elem.locator(".select__single-value, .selected-item, .display-value, .value-text").first
            if await selected_indicator.count() > 0:
                 indicator_text = await selected_indicator.inner_text(timeout=500)
                 if indicator_text and "select" not in indicator_text.lower(): # Basic check if something other than placeholder is selected
                      logger.debug(f"Skipping custom dropdown '{label_text}', appears already filled with '{indicator_text}'.")
                      continue


            combined_text = label_text # Rely mainly on label for custom ones
            matched_key_category = None
            matched_keyword_key = None
            desired_value = None

            # Match label against keywords
            for category, keywords_dict in keywords_map.items():
                if category in ['personal_info', 'education', 'work_experience']: continue
                key = match_field(combined_text, keywords_dict, FUZZY_MATCH_THRESHOLD)
                if key:
                    matched_key_category = category
                    matched_keyword_key = key
                    if category in standard_answers and key in standard_answers[category]:
                        desired_value = standard_answers[category][key]
                    elif key in standard_answers.get('yes_no', {}):
                         desired_value = standard_answers['yes_no'][key][0]
                    break

            if desired_value is not None:
                logger.info(f"Attempting to select custom dropdown '{label_text}' for '{matched_keyword_key}' with value '{desired_value}'")
                # Pass necessary info to the selection helper
                # Use container_elem as the base for selection logic
                success = await select_custom_dropdown_option(
                    page=page,
                    base_element=container_elem, # The container we found
                    desired_value=str(desired_value),
                    config=config,
                    results=results,
                    label_text=label_text # Pass the identified label
                )
                if success:
                    results["fields_filled"].append(unique_check_id)
                else:
                    logger.warning(f"Failed to select option for custom dropdown '{label_text}'")
                    results["fields_skipped"].append(unique_check_id)
            elif matched_keyword_key:
                 logger.warning(f"Matched custom dropdown '{label_text}' to '{matched_keyword_key}' but no standard answer defined.")
                 results["fields_skipped"].append(unique_check_id)

        except PlaywrightTimeoutError:
             logger.warning(f"Timeout interacting with custom dropdown '{label_text or i}'. Skipping.")
             if unique_check_id: results["fields_skipped"].append(unique_check_id)
        except Exception as e:
            label_text_err = label_text or f"custom_dropdown_{i}"
            error_msg = f"Error processing custom dropdown '{label_text_err}': {e}"
            if error_msg not in results.get("errors", []): results["errors"].append(error_msg)
            logger.error(f"⚠️ {error_msg}", exc_info=False)
            if unique_check_id: results["fields_skipped"].append(unique_check_id)


async def select_custom_dropdown_option(page: Page, base_element: Locator, desired_value: str, config: Dict[str, Any], results: Dict[str, Any], label_text: str) -> bool:
    """
    Handles selecting an option within a custom dropdown element.
    Uses known selectors, type-ahead, and AI fallback for selectors.

    Args:
        page: Playwright page instance.
        base_element: Locator for the container of the custom dropdown.
        desired_value: The string value/text of the option to select.
        config: Loaded configuration.
        results: Results dictionary to update.
        label_text: The determined label for logging and identification.

    Returns:
        True if selection was successful, False otherwise.
    """
    option_selected = False
    known_selectors = config.get('common_selectors', {}).get('custom_dropdown', {})
    standard_answers = config.get('standard_answers', {}) # Needed for select_matching_option

    list_selector_str = None
    item_selector_str = None
    list_sel_ai = None 
    item_sel_ai = None 
    
    # --- Step 1: Try Type-Ahead / Search Interaction ---
    try:
        # Find the input field within the base element
        input_selector = ", ".join(known_selectors.get('input', []))
        search_input = base_element.locator(input_selector).first

        if await search_input.count() > 0 and await search_input.is_visible(timeout=1000):
            logger.info(f"Custom dropdown '{label_text}': Found search input. Trying type-and-select.")
            await search_input.scroll_into_view_if_needed(timeout=2000)
            await asyncio.sleep(0.1)

            # Click or focus to potentially open/activate
            try: await search_input.click(timeout=1500)
            except: await search_input.focus(timeout=1500)
            await asyncio.sleep(0.3) # Wait for potential animation/list appearance

            # Type the desired value (clear first?)
            try: await search_input.fill("", timeout=1000) # Clear field first
            except Exception: logger.debug("Could not clear search input before typing.")
            await asyncio.sleep(0.1)
            await search_input.press_sequentially(desired_value, delay=75, timeout=5000)
            logger.info(f"Typed '{desired_value}' into search input for '{label_text}'.")
            await asyncio.sleep(1.0) # ** Crucial: Wait for suggestions list to appear and populate **

            # --- Find Suggestions List and Item ---
            list_selector_str = ", ".join(known_selectors.get('list', [])) 
            item_selector_str = ", ".join(known_selectors.get('item', [])) 

            # Try known selectors first
            suggestion_list = page.locator(list_selector_str)
            # Wait for list to be visible *somewhere* on the page after typing
            try:
                 await suggestion_list.first.wait_for(state="visible", timeout=5000)
                 logger.info(f"Suggestion list found using known selectors: {list_selector_str}")
            except PlaywrightTimeoutError:
                 logger.info("Suggestion list not found using known selectors. Trying AI fallback.")
                 # --- AI Fallback ---
                 try:
                      html_snippet = await base_element.inner_html(timeout=2000)
                      # Maybe include nearby elements too?
                      # parent_html = await base_element.locator("xpath=..").inner_html(timeout=1000)
                      # html_context = parent_html + html_snippet # Combine? Be careful with length

                      task = f"After typing '{desired_value}' into an input within the component (HTML below), a list of suggestions appears. Provide CSS selectors for the container of this list ('list_selector') and a single item within it ('item_selector').\nHTML: {html_snippet}"
                      list_sel_ai, item_sel_ai = await get_selectors_from_gemini(html_snippet, task)

                      if list_sel_ai and item_sel_ai:
                           logger.info(f"AI suggested selectors - List: '{list_sel_ai}', Item: '{item_sel_ai}'")
                           # Validate AI selectors quickly
                           try:
                               await page.locator(list_sel_ai).first.wait_for(state="visible", timeout=3000)
                               list_selector_str = list_sel_ai # Use AI selector
                               item_selector_str = item_sel_ai # Use AI selector
                           except Exception as ai_val_err:
                                logger.warning(f"AI suggested selectors failed validation: {ai_val_err}. Reverting to known selectors.")
                      else:
                           logger.warning("AI fallback failed to provide usable selectors.")

                 except Exception as ai_err:
                      logger.error(f"Error during AI selector fetching for '{label_text}': {ai_err}")
                 # --- End AI Fallback ---

            # --- Select Option from List ---
            if list_selector_str and item_selector_str:
                 # Find the specific list associated with the input (if possible)
                 # This assumes list appears globally or near base_element
                 visible_list = page.locator(list_selector_str).filter(has=page.locator(item_selector_str)).first
                 if await visible_list.count() > 0:
                     logger.info(f"Suggestion list visible for '{label_text}'. Searching for item...")
                     # Locate suggestion items within the visible list
                     suggestion_items = visible_list.locator(item_selector_str)
                     items_count = await suggestion_items.count()
                     logger.debug(f"Found {items_count} potential items using selector: {item_selector_str}")

                     best_match_option: Optional[Locator] = None
                     best_match_text = ""
                     best_match_score = -1

                     # Iterate through visible options to find the best match
                     for k in range(items_count):
                          item = suggestion_items.nth(k)
                          try:
                               if not await item.is_visible(timeout=100): continue # Skip non-visible quickly
                               item_text = await item.text_content(timeout=500) or ""
                               item_text = item_text.strip()
                               if not item_text: continue # Skip empty options

                               score = fuzz.token_set_ratio(desired_value.lower(), item_text.lower())

                               if score > best_match_score:
                                    # Basic check to avoid selecting group headers if text doesn't match well
                                    is_header = await item.get_attribute("role") == "group" or "header" in (await item.get_attribute("class") or "")
                                    if is_header and score < 90: continue # Don't select headers unless very close match

                                    best_match_score = score
                                    best_match_option = item
                                    best_match_text = item_text

                               # Exact match is best
                               if score == 100: break

                          except Exception as item_err:
                               logger.debug(f"Error processing suggestion item {k}: {item_err}")

                     # Click the best match if found above threshold
                     if best_match_option and best_match_score >= FUZZY_MATCH_THRESHOLD:
                          logger.info(f"Best match found: '{best_match_text}' (Score: {best_match_score}). Attempting click.")
                          try:
                              await best_match_option.scroll_into_view_if_needed(timeout=2000)
                              await asyncio.sleep(0.1)
                              await best_match_option.click(timeout=3000)
                              option_selected = True
                              logger.info(f"✅ Selected '{best_match_text}' for '{label_text}' via type-and-select.")
                          except Exception as click_err:
                              logger.warning(f"Failed to click matched suggestion '{best_match_text}': {click_err}")
                     else:
                          logger.warning(f"Could not find a suitable suggestion matching '{desired_value}' in list for '{label_text}'. Best score: {best_match_score}")
                          # Try pressing Enter as a fallback if typing occurred
                          logger.info(f"Trying to press Enter in search input as fallback for '{label_text}'.")
                          try:
                              await search_input.press("Enter")
                              await asyncio.sleep(0.5)
                              # Re-check if input value changed as verification
                              final_value = await search_input.input_value(timeout=500)
                              if desired_value.lower() in final_value.lower():
                                   logger.info(f"✅ Pressing Enter seems to have selected the value for '{label_text}'.")
                                   option_selected = True
                              else: logger.warning("Pressing Enter did not seem to select the value.")
                          except Exception as enter_err:
                               logger.warning(f"Failed to press Enter in search input: {enter_err}")
                 else:
                      logger.warning(f"Suggestion list selector '{list_selector_str}' did not yield a visible list for '{label_text}'.")
            else:
                 logger.warning(f"Could not determine suggestion list/item selectors for '{label_text}'.")
        else:
            logger.debug(f"Custom dropdown '{label_text}': No search input found. Trying direct click.")
            # Proceed to Step 2 if no search input

    except Exception as search_interact_err:
         logger.warning(f"Error during type-ahead interaction for '{label_text}': {search_interact_err}", exc_info=False)
         # Proceed to Step 2

    # --- Step 2: Fallback to Standard Click-and-Select Logic (less common for custom) ---
    if not option_selected:
        logger.info(f"Trying standard click/select logic as fallback for custom dropdown '{label_text}'.")
        # This assumes the custom dropdown *might* behave like a standard one on click
        try:
            # Try clicking the base element or a button inside it to open options
            opener = base_element.locator("button, input, [role='button'], [role='combobox']").first
            clicked = False
            try:
                 if await opener.count() > 0 and await opener.is_visible(timeout=500): await opener.click(timeout=1500); clicked = True
                 else: await base_element.click(timeout=1500); clicked = True # Click container itself
            except Exception as open_err: logger.debug(f"Failed to open custom dropdown '{label_text}' via simple click: {open_err}")

            if clicked:
                 logger.info(f"Clicked custom dropdown '{label_text}'. Waiting for options...")
                 await asyncio.sleep(0.8) # Wait for options to appear

                 # Use the same item selectors as before (known or AI)
                 item_selector_str = ", ".join(known_selectors.get('item', [])) if list_selector_str else None # Reuse selectors if determined above
                 if not item_selector_str and item_selector_ai: item_selector_str = item_selector_ai
                 if not item_selector_str: item_selector_str = "div[role='option'], li[role='option']" # Generic fallback

                 options = page.locator(item_selector_str)
                 # Reuse matching logic (simplified - find best match text and click)
                 best_match_option: Optional[Locator] = None
                 best_match_text = ""
                 best_match_score = -1
                 option_count = await options.count()
                 # Limit search for performance
                 for k in range(min(option_count, 30)): # Check max 30 options in simple list
                      item = options.nth(k)
                      try:
                           if not await item.is_visible(timeout=100): continue
                           item_text = (await item.text_content(timeout=500) or "").strip()
                           if not item_text: continue
                           score = fuzz.token_set_ratio(desired_value.lower(), item_text.lower())
                           if score > best_match_score:
                                best_match_score = score
                                best_match_option = item
                                best_match_text = item_text
                           if score == 100: break
                      except: continue

                 if best_match_option and best_match_score >= FUZZY_MATCH_THRESHOLD:
                      logger.info(f"Found option '{best_match_text}' via fallback click method (Score: {best_match_score}). Clicking.")
                      try:
                           await best_match_option.click(timeout=3000)
                           option_selected = True
                           logger.info(f"✅ Selected '{best_match_text}' for '{label_text}' via fallback click.")
                      except Exception as click_err:
                           logger.warning(f"Failed to click option in fallback mode: {click_err}")
                 else:
                      logger.warning(f"Could not find matching option for '{label_text}' via fallback click method.")
            else:
                 logger.warning(f"Could not open custom dropdown '{label_text}' via simple click.")

        except Exception as fallback_err:
             logger.error(f"Error during fallback click/select for '{label_text}': {fallback_err}", exc_info=False)


    # --- Step 3: Cleanup ---
    # Try clicking outside to close any open lists, regardless of success
    try:
        await page.locator('body').click(position={'x': 5, 'y': 5}, delay=50, timeout=1000)
    except Exception: pass

    return option_selected


async def handle_all_checkboxes(page: Page, config: Dict[str, Any], resume: Dict[str, Any], results: Dict[str, Any]) -> None:
    """Handle all checkbox fields using config keywords and standard answers."""
    logger.info("Handling checkbox fields...")
    keywords_map = config.get('field_keywords', {})
    standard_answers = config.get('standard_answers', {})
    filled_in_this_pass = set()

    checkboxes = page.locator("input[type='checkbox']")
    count = await checkboxes.count()

    for i in range(count):
        checkbox = checkboxes.nth(i)
        try:
            if not await checkbox.is_visible(timeout=500): continue
            if not await checkbox.is_enabled(timeout=500): continue

            label_text = await get_field_label(page, checkbox)
            field_id = await checkbox.get_attribute("id") or ""
            field_name = await checkbox.get_attribute("name") or ""
            combined_text = f"{label_text or ''} {field_id} {field_name}".strip()
            unique_check_id = label_text or field_id or field_name or f"checkbox_{i}"

            if not combined_text or (unique_check_id in results["fields_filled"]) or (unique_check_id in results["fields_skipped"]):
                continue

            # Match against keywords
            matched_key = None
            desired_state = None # True to check, False to uncheck, None to leave alone unless required

            # Check for opt-out first
            opt_out_key = match_field(combined_text, keywords_map.get('other', {}).get('communication_opt_out', []), FUZZY_MATCH_THRESHOLD + 5) # Higher threshold for opt-out
            if opt_out_key:
                 matched_key = 'communication_opt_out'
                 desired_state = standard_answers.get('other', {}).get(matched_key, False) # Default False (uncheck)
            else:
                 # Check for agreement terms
                 agree_key = match_field(combined_text, keywords_map.get('other', {}).get('agree_terms', []), FUZZY_MATCH_THRESHOLD)
                 if agree_key:
                      matched_key = 'agree_terms'
                      desired_state = standard_answers.get('other', {}).get(matched_key, True) # Default True (check)

            # Determine if required
            is_required = False
            try:
                 if await checkbox.get_attribute("required") is not None or \
                    await checkbox.get_attribute("aria-required") == "true" or \
                    (label_text and "*" in label_text):
                      is_required = True
            except Exception: pass # Ignore errors determining required status

            # If required and state not determined, default to checking it
            if is_required and desired_state is None:
                 logger.info(f"Checkbox '{label_text or unique_check_id}' is required and unhandled, checking it.")
                 desired_state = True

            # Apply the decision
            current_state = await checkbox.is_checked(timeout=500)
            action_taken = False
            if desired_state is True and not current_state:
                await checkbox.check(timeout=3000)
                logger.info(f"✅ Checked checkbox: '{label_text or unique_check_id}'")
                action_taken = True
                await asyncio.sleep(DELAY_BETWEEN_ACTIONS)
            elif desired_state is False and current_state:
                await checkbox.uncheck(timeout=3000)
                logger.info(f"✅ Unchecked checkbox: '{label_text or unique_check_id}'")
                action_taken = True
                await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

            if action_taken:
                 results["fields_filled"].append(unique_check_id)
            elif desired_state is not None: # We decided state but didn't need to act
                 pass # No action needed, don't skip or fill
            else:
                 # If not required and no rule matched, we skip it
                 if not is_required:
                      logger.debug(f"Skipping optional checkbox '{label_text or unique_check_id}' as no rule matched.")
                      # results["fields_skipped"].append(unique_check_id) # Optional: track skipped optional fields?
                 else:
                      # This case (required, but no rule, didn't default to check) shouldn't happen often
                      logger.warning(f"Required checkbox '{label_text or unique_check_id}' had no matching rule and wasn't defaulted. Skipping.")
                      results["fields_skipped"].append(unique_check_id)


        except PlaywrightTimeoutError:
             logger.warning(f"Timeout interacting with checkbox {i}. Skipping.")
             if unique_check_id: results["fields_skipped"].append(unique_check_id)
        except Exception as e:
            label_text_err = label_text or field_id or f"checkbox_{i}"
            error_msg = f"Error handling checkbox '{label_text_err}': {e}"
            if error_msg not in results.get("errors", []): results["errors"].append(error_msg)
            logger.error(f"⚠️ {error_msg}", exc_info=False)
            if unique_check_id: results["fields_skipped"].append(unique_check_id)


async def handle_all_radio_groups(page: Page, config: Dict[str, Any], resume: Dict[str, Any], results: Dict[str, Any]) -> None:
    """Handle all radio button groups using config keywords and standard answers."""
    logger.info("Handling radio button groups...")
    keywords_map = config.get('field_keywords', {})
    standard_answers = config.get('standard_answers', {})
    filled_groups = set() # Track groups handled by name or label

    # Find potential grouping elements (fieldset, div role=radiogroup, or just rely on name attribute)
    grouping_elements = page.locator("fieldset, div[role='radiogroup']")
    processed_names = set() # Keep track of names processed via group elements

    # --- Strategy 1: Process within identified groups ---
    group_count = await grouping_elements.count()
    logger.debug(f"Found {group_count} potential radio grouping elements.")
    for i in range(group_count):
        group_element = grouping_elements.nth(i)
        try:
            if not await group_element.is_visible(timeout=500): continue

            # Find radio buttons *within* this group
            radios_in_group = group_element.locator("input[type='radio']")
            radio_count = await radios_in_group.count()
            if radio_count == 0: continue

            # Get group label (legend, aria-label, preceding header/label)
            group_label = await get_field_label(page, group_element)
            if not group_label: # Try first radio's name/label as fallback? Risky.
                 first_radio_name = await radios_in_group.first.get_attribute("name")
                 # group_label = await get_field_label(page, radios_in_group.first) or first_radio_name
                 if first_radio_name: group_label = f"Radio Group ({first_radio_name})" # Use name if no good label
                 else: group_label = f"Radio Group Index {i}"


            # Use label or index as unique ID for this group check
            unique_group_id = f"radio_group:{group_label}"
            if unique_group_id in filled_groups: continue

            # Check if any radio in this group is already checked
            is_already_checked = False
            for j in range(radio_count):
                if await radios_in_group.nth(j).is_checked(timeout=200):
                    is_already_checked = True
                    break
            if is_already_checked:
                 logger.debug(f"Skipping radio group '{group_label}' - already checked.")
                 filled_groups.add(unique_group_id) # Mark as handled
                 # Also mark the name as processed if possible
                 first_radio_name = await radios_in_group.first.get_attribute("name")
                 if first_radio_name: processed_names.add(first_radio_name)
                 continue

            # Match group label against keywords
            combined_text = group_label
            matched_key_category = None
            matched_keyword_key = None
            desired_value = None

            for category, keywords_dict in keywords_map.items():
                if category in ['personal_info', 'education', 'work_experience']: continue
                key = match_field(combined_text, keywords_dict, FUZZY_MATCH_THRESHOLD)
                if key:
                    matched_key_category = category
                    matched_keyword_key = key
                    if category in standard_answers and key in standard_answers[category]:
                        desired_value = standard_answers[category][key]
                    elif key in standard_answers.get('yes_no', {}):
                        desired_value = standard_answers['yes_no'][key][0]
                    break

            if desired_value is not None:
                logger.info(f"Attempting to select radio group '{group_label}' for '{matched_keyword_key}' with value '{desired_value}'")
                # Pass the group element to the selection helper
                success, _ = await select_matching_option(group_element, desired_value, standard_answers, "radio")
                if success:
                    filled_groups.add(unique_group_id)
                    first_radio_name = await radios_in_group.first.get_attribute("name")
                    if first_radio_name: processed_names.add(first_radio_name)
                    results["fields_filled"].append(unique_group_id) # Use group ID in results
                else:
                    # If failed, check if required and select first option? Very risky.
                    is_required = "*" in group_label # Simple check
                    # More robust: check if any radio inside has aria-required
                    # is_required = is_required or await group_element.locator("input[type='radio'][aria-required='true']").count() > 0

                    if is_required:
                         logger.warning(f"Required radio group '{group_label}' couldn't be matched. Attempting to select first option as fallback.")
                         try:
                              await radios_in_group.first.check(timeout=3000)
                              logger.info(f"✅ Selected first option for required radio group '{group_label}' as fallback.")
                              filled_groups.add(unique_group_id)
                              first_radio_name = await radios_in_group.first.get_attribute("name")
                              if first_radio_name: processed_names.add(first_radio_name)
                              results["fields_filled"].append(unique_group_id + " (fallback)")
                         except Exception as fallback_err:
                              logger.error(f"Failed to select first option fallback for '{group_label}': {fallback_err}")
                              results["fields_skipped"].append(unique_group_id)
                    else:
                         logger.warning(f"Failed to select option for radio group '{group_label}' and not marked required.")
                         results["fields_skipped"].append(unique_group_id)

            elif matched_keyword_key:
                 logger.warning(f"Matched radio group '{group_label}' to '{matched_keyword_key}' but no standard answer defined.")
                 results["fields_skipped"].append(unique_group_id)

        except PlaywrightTimeoutError:
             logger.warning(f"Timeout interacting with radio group {i}. Skipping.")
             if unique_group_id: results["fields_skipped"].append(unique_group_id)
        except Exception as e:
            group_label_err = group_label or f"group_{i}"
            error_msg = f"Error processing radio group '{group_label_err}': {e}"
            if error_msg not in results.get("errors", []): results["errors"].append(error_msg)
            logger.error(f"⚠️ {error_msg}", exc_info=False)
            if unique_group_id: results["fields_skipped"].append(unique_group_id)


    # --- Strategy 2: Process radios by name attribute if not handled by group element ---
    all_radio_names = await page.locator("input[type='radio']").evaluate_all("radios => radios.map(r => r.name).filter(name => name)")
    unique_names = set(all_radio_names) - processed_names
    logger.debug(f"Found radio names not processed by group elements: {unique_names}")

    for name in unique_names:
         if not name: continue # Should be filtered, but double check
         radio_locator_by_name = page.locator(f"input[type='radio'][name='{name}']")
         try:
              # Use first radio's label as group identifier
              first_radio = radio_locator_by_name.first
              group_label = await get_field_label(page, first_radio) or f"Radio Group ({name})"
              unique_group_id = f"radio_group:{group_label}"
              if unique_group_id in filled_groups: continue # Already handled maybe by similar label?

              # Check if already checked
              is_already_checked = await page.locator(f"input[type='radio'][name='{name}']:checked").count() > 0
              if is_already_checked:
                   logger.debug(f"Skipping radio group (by name '{name}') '{group_label}' - already checked.")
                   filled_groups.add(unique_group_id)
                   continue

              # Match label against keywords (same logic as above)
              combined_text = group_label
              matched_key_category = None
              matched_keyword_key = None
              desired_value = None
              for category, keywords_dict in keywords_map.items():
                   if category in ['personal_info', 'education', 'work_experience']: continue
                   key = match_field(combined_text, keywords_dict, FUZZY_MATCH_THRESHOLD)
                   if key:
                        matched_key_category = category
                        matched_keyword_key = key
                        if category in standard_answers and key in standard_answers[category]:
                             desired_value = standard_answers[category][key]
                        elif key in standard_answers.get('yes_no', {}):
                             desired_value = standard_answers['yes_no'][key][0]
                        break

              if desired_value is not None:
                   logger.info(f"Attempting to select radio group (by name '{name}') '{group_label}' for '{matched_keyword_key}' with value '{desired_value}'")
                   # Here, the 'base_element' for select_matching_option is effectively the page or a common ancestor
                   # We need to pass the locator for the radios with this name.
                   # Re-using select_matching_option directly is tricky. Let's adapt the logic here.

                   options_by_name = []
                   radios = radio_locator_by_name
                   count_by_name = await radios.count()
                   for k in range(count_by_name):
                        radio = radios.nth(k)
                        if not await radio.is_enabled(timeout=500): continue
                        value = await radio.get_attribute("value") or ""
                        label = await get_field_label(page, radio) or value
                        options_by_name.append({"value": value, "text": label, "locator": radio})

                   selected_option = None
                   best_match_score = -1
                   selected_text = None

                   for option in options_by_name:
                        option_text = option.get("text", "")
                        option_text_lower = option_text.lower()
                        current_score = -1
                        # Reuse scoring logic from select_matching_option
                        if str(desired_value).lower() == option_text_lower: current_score = 100
                        elif option_text: score = fuzz.token_set_ratio(str(desired_value).lower(), option_text_lower); current_score = max(current_score, score)
                        # Add yes/no/decline scoring boost...
                        yes_keywords = standard_answers.get('yes_no', {}).get('yes', ['yes'])
                        no_keywords = standard_answers.get('yes_no', {}).get('no', ['no'])
                        if any(kw in option_text_lower for kw in yes_keywords) and str(desired_value).lower() == 'yes': current_score = max(current_score, 90)
                        elif any(kw in option_text_lower for kw in no_keywords) and str(desired_value).lower() == 'no' and not any(dkw in option_text_lower for dkw in ["decline", "prefer not"]): current_score = max(current_score, 90)
                        # Add more boosts if needed

                        if current_score > best_match_score:
                             best_match_score = current_score
                             selected_option = option
                             selected_text = option_text

                   if selected_option and best_match_score >= FUZZY_MATCH_THRESHOLD:
                        try:
                             await selected_option["locator"].check(timeout=3000)
                             logger.info(f"✅ Selected radio (by name '{name}') '{selected_text}' for group '{group_label}' (Score: {best_match_score})")
                             filled_groups.add(unique_group_id)
                             results["fields_filled"].append(unique_group_id)
                             await asyncio.sleep(DELAY_BETWEEN_ACTIONS)
                        except Exception as e:
                             logger.error(f"Error selecting radio (by name '{name}') '{selected_text}': {e}")
                             results["fields_skipped"].append(unique_group_id)
                   else:
                        # Handle required fallback for named groups if needed (similar logic)
                        logger.warning(f"Failed to select option for radio group (by name '{name}') '{group_label}'.")
                        results["fields_skipped"].append(unique_group_id) # Skip if no match

              elif matched_keyword_key:
                   logger.warning(f"Matched radio group (by name '{name}') '{group_label}' to '{matched_keyword_key}' but no standard answer.")
                   results["fields_skipped"].append(unique_group_id)

         except Exception as e:
              group_label_err = group_label or f"name_{name}"
              error_msg = f"Error processing radio group by name '{group_label_err}': {e}"
              if error_msg not in results.get("errors", []): results["errors"].append(error_msg)
              logger.error(f"⚠️ {error_msg}", exc_info=False)
              if unique_group_id: results["fields_skipped"].append(unique_group_id)


# --- Master Filling Function ---
async def fill_all_fields(page: Page, resume: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrates filling all detectable fields based on the resume and config.

    Returns:
        Dictionary containing results: fields_filled, fields_skipped, errors.
    """
    load_form_config(config) # Load relevant settings from config

    results = { "fields_filled": [], "fields_skipped": [], "errors": [] }
    start_time = asyncio.get_event_loop().time()
    logger.info("Starting comprehensive form filling...")

    # Execute filling functions in a logical order
    await fill_personal_info(page, resume, config, results)
    await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

    await upload_resume_file(page, config, results)
    await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

    # --- TODO: ITERATION 2 ---
    await fill_education_fields(page, resume, config, results) # Placeholder
    await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

    await fill_work_experience_fields(page, resume, config, results) # Placeholder
    await asyncio.sleep(DELAY_BETWEEN_ACTIONS)
    # --- END TODO ---

    await fill_standard_dropdowns(page, config, resume, results)
    await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

    await fill_custom_dropdowns(page, config, resume, results)
    await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

    await handle_all_radio_groups(page, config, resume, results)
    await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

    await handle_all_checkboxes(page, config, resume, results)
    await asyncio.sleep(DELAY_BETWEEN_ACTIONS)

    end_time = asyncio.get_event_loop().time()
    logger.info(f"Deterministic filling attempt finished in {end_time - start_time:.2f} seconds.")
    logger.info(f"Fill results: Filled={len(results['fields_filled'])}, Skipped={len(results['fields_skipped'])}, Errors={len(results['errors'])}")
    if results["errors"]:
        logger.warning("Errors occurred during deterministic filling:")
        for error in results["errors"]: logger.warning(f" - {error}")

    # Note: check_for_missed_fields and AI fallback will be called *after* this in job_processor.py
    return results


# --- Check for Missed Required Fields (Adapted) ---
async def check_for_missed_fields(page: Page, config: Dict[str, Any], results: Dict[str, Any]) -> List[str]:
    """
    Checks the form for input fields, selects, and textareas marked as required
    that haven't been filled or skipped according to the results dictionary.

    Args:
        page: The Playwright page object.
        config: Loaded configuration.
        results: Dictionary containing 'fields_filled' and 'fields_skipped'.

    Returns:
        A list of labels/identifiers for missed required fields.
    """
    missed_required_fields: List[str] = []
    # Combine filled and skipped for checking if handled
    handled_fields_set = set(results.get("fields_filled", []) + results.get("fields_skipped", []))
    logger.info(f"Checking for missed required fields against {len(handled_fields_set)} handled items.")
    # logger.debug(f"Handled fields: {handled_fields_set}") # Can be very verbose


    # Selectors for potentially required elements (more comprehensive)
    potential_elements = page.locator("input, select, textarea, div[role='radiogroup'], div[role='combobox']")
    count = await potential_elements.count()
    logger.info(f"Checking {count} potential elements for missed required fields...")

    checked_radio_groups = set() # Track checked radio groups by name

    for i in range(count):
        element = potential_elements.nth(i)
        label = None # Reset label
        unique_check_id = f"element_{i}" # Fallback id

        try:
            # --- Basic Visibility and Type Checks ---
            if not await element.is_visible(timeout=200): continue

            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            role = await element.get_attribute("role") or ""
            input_type = (await element.get_attribute("type") or "text").lower() if tag_name == "input" else None

            # Skip buttons, hidden inputs, etc.
            if tag_name == "button" or input_type in ["button", "submit", "reset", "hidden", "image"]: continue

            # --- Get Label and Identifier ---
            label = await get_field_label(page, element)
            element_id = await element.get_attribute("id") or ""
            element_name = await element.get_attribute("name") or ""
            # Use label or name/id as the primary identifier for checking if handled
            unique_check_id = label or element_id or element_name or f"element_{i}"
            if tag_name == "div" and role == "radiogroup": unique_check_id = f"radio_group:{label or element_name or i}"
            elif tag_name == "div" and role == "combobox": unique_check_id = f"custom_dropdown:{label or element_id or i}"


            # --- Check if Already Handled ---
            if unique_check_id in handled_fields_set:
                 logger.debug(f"Field '{unique_check_id}' skipped (already handled).")
                 continue
            # Check related IDs too (e.g. if dropdown was filled using custom_dropdown:label)
            if f"custom_dropdown:{label}" in handled_fields_set or f"radio_group:{label}" in handled_fields_set:
                 logger.debug(f"Field '{unique_check_id}' skipped (related ID handled).")
                 continue


            # --- Determine if Required ---
            is_required = False
            try:
                 # Check standard attributes
                 if await element.get_attribute("required") is not None or \
                    await element.get_attribute("aria-required") == "true":
                      is_required = True
                 # Check label for asterisk (common pattern)
                 elif label and "*" in label:
                      is_required = True
                 # Check for required class on element or parent (less reliable)
                 # class_attr = await element.get_attribute("class") or ""
                 # if "required" in class_attr.lower(): is_required = True
                 # parent = element.locator("xpath=..")
                 # if await parent.count() > 0 and "required" in (await parent.get_attribute("class") or "").lower(): is_required = True

            except Exception as req_e:
                 logger.warning(f"Could not reliably determine required status for '{unique_check_id}': {req_e}")


            if not is_required: continue # Skip non-required fields

            logger.debug(f"Field '{unique_check_id}' IS required. Checking value...")

            # --- Check if Empty/Unselected ---
            is_empty = False
            if tag_name == "input":
                if input_type in ["text", "email", "tel", "url", "password", "search", "number", "date", "month", "week", "time", "datetime-local"]:
                    value = await element.input_value(timeout=500)
                    if not value or value.strip() == "": is_empty = True
                elif input_type == "checkbox":
                    if not await element.is_checked(timeout=500): is_empty = True
                elif input_type == "radio":
                    # Only consider radio group empty if NO button in the group is checked
                    if element_name and element_name not in checked_radio_groups:
                         group_checked = await page.locator(f"input[type='radio'][name='{element_name}']:checked").count() > 0
                         if not group_checked: is_empty = True
                         else: checked_radio_groups.add(element_name) # Mark group as checked
                    elif not element_name: # Radio without name - must be checked individually if required
                         if not await element.is_checked(timeout=500): is_empty = True
                elif input_type == "file":
                    if not await element.input_value(timeout=500): is_empty = True

            elif tag_name == "textarea":
                value = await element.input_value(timeout=500)
                if not value or value.strip() == "": is_empty = True

            elif tag_name == "select":
                value = await element.input_value(timeout=500)
                # Check for empty string, "0", "-1", or default "select..." options
                if not value or value in ["", "0", "-1"] or ("select" in value.lower() and len(value) < 15): # Allow longer "select..." values?
                    is_empty = True

            elif tag_name == "div" and role == "radiogroup":
                 # Check if any radio *inside* this group is checked
                 if await element.locator("input[type='radio']:checked").count() == 0:
                      is_empty = True

            elif tag_name == "div" and role == "combobox":
                 # Check if custom dropdown has a selected value indicator filled
                 selected_indicator = element.locator(".select__single-value, .selected-item, .display-value").first
                 value_text = ""
                 if await selected_indicator.count() > 0: value_text = await selected_indicator.inner_text(timeout=200)
                 # Also check input value if it's an input acting as combobox
                 input_inside = element.locator("input").first
                 if not value_text and await input_inside.count() > 0: value_text = await input_inside.input_value(timeout=200)

                 if not value_text or "select" in value_text.lower(): # Check if empty or placeholder
                      is_empty = True

            # --- Add to Missed List if Required and Empty ---
            if is_empty:
                identifier = label or element_id or element_name or f"Required Field Index {i}"
                logger.warning(f"Required field '{identifier}' appears to be empty/unselected.")
                missed_required_fields.append(identifier)

        except PlaywrightTimeoutError:
             logger.warning(f"Timeout checking required status or value for element {i}. Assuming OK.")
        except Exception as e:
            logger.error(f"Error checking potential required field '{label or unique_check_id}': {e}", exc_info=False)

    # Remove duplicates while preserving order (approximate)
    seen = set()
    unique_missed = [x for x in missed_required_fields if not (x in seen or seen.add(x))]
    if unique_missed:
        logger.warning(f"Found {len(unique_missed)} unique missed required fields: {', '.join(unique_missed)}")
    else:
        logger.info("No missed required fields detected.")

    return unique_missed
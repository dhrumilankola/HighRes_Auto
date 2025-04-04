# agent/job_processor.py

import asyncio
import os
import time
import logging
import traceback
from typing import Dict, Any, Optional, Tuple
from queue_manager import QueueManager
from resume_loader import load_resume_data
from browser_computer import LocalPlaywrightComputer
from agent_config import create_agent
from form_filler import (
    fill_basic_info, 
    upload_resume, 
    fill_demographics, 
    fill_portfolio_and_linkedin, 
    answer_open_ended_questions
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("job_processor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("job_processor")



async def process_job(job: Dict[str, Any], resume: Dict[str, Any]) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Process a job application using the automated agent.
    
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
        return False, "No application URL found", None
    
    logger.info(f"Processing job {job_id}: {job_data.get('title')} at {job_data.get('company')}")
    logger.info(f"Application URL: {apply_url}")
    
    try:
        # Start the browser session
        async with LocalPlaywrightComputer(apply_url) as computer:
            try:
                # Wait for page to load
                await computer.page.wait_for_load_state("networkidle", timeout=30000)
                logger.info("✅ Page loaded")
                
                # Check if the page has expected application form elements
                has_form = await check_for_application_form(computer.page)
                if not has_form:
                    logger.warning("❌ Application form not detected")
                    return False, "Application form not detected on page", {"screenshot": await take_screenshot(computer.page)}
                
                # Initialize agent (optional if using direct form filling)
                agent = create_agent(computer)
                
                # Fill out the form
                await fill_basic_info(computer.page, resume)
                await upload_resume(computer.page)
                await fill_demographics(computer.page)
                await fill_portfolio_and_linkedin(computer.page, resume)
                await answer_open_ended_questions(computer.page, resume, apply_url)
                
                # Check for any required fields that weren't filled
                missing_fields = await check_required_fields(computer.page)
                if missing_fields:
                    logger.warning(f"❌ Missing required fields: {', '.join(missing_fields)}")
                    screenshot = await take_screenshot(computer.page)
                    return False, "Missing required fields", {
                        "missing_fields": missing_fields,
                        "screenshot": screenshot
                    }
                
                # Check if there's a submit button
                submit_button = await find_submit_button(computer.page)
                if not submit_button:
                    logger.warning("❌ Submit button not found")
                    return False, "Submit button not found", {"screenshot": ""}
                
                # Actually submit the form
                await submit_button.click()
                logger.info("✅ Form submitted")
                
                # Wait for success message to appear (common success indicators)
                success_selectors = [
                    "text=application submitted",
                    "text=thank you for applying",
                    "text=application received",
                    "text=successfully submitted",
                    ".success-message",
                    "#success-message"
                ]
                
                success_found = False
                for selector in success_selectors:
                    try:
                        await computer.page.wait_for_selector(selector, timeout=10000)
                        success_found = True
                        logger.info(f"✅ Success message found: {selector}")
                        break
                    except:
                        pass

                # If no explicit success message, wait a moment for any transition
                if not success_found:
                    await computer.page.wait_for_timeout(3000)
                    logger.info("No explicit success message found, waited for page transition")

                # Take screenshot of the success page
                screenshot_path = await take_screenshot(computer.page)
                logger.info(f"✅ Success page screenshot saved to {screenshot_path}")

                return True, "Application submitted successfully", {"screenshot": screenshot_path}
                
            except Exception as e:
                error_details = traceback.format_exc()
                logger.error(f"Error during application: {str(e)}\n{error_details}")
                screenshot = await take_screenshot(computer.page)
                return False, str(e), {"error_details": error_details, "screenshot": screenshot}
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Browser session error: {str(e)}\n{error_details}")
        return False, f"Browser session error: {str(e)}", {"error_details": error_details}

async def take_screenshot(page) -> str:
    """Take a screenshot and return the path."""
    try:
        timestamp = int(time.time())
        screenshot_path = f"screenshots/job_{timestamp}.png"
        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
        await page.screenshot(path=screenshot_path, full_page=True)
        return screenshot_path
    except Exception as e:
        logger.error(f"Failed to take screenshot: {str(e)}")
        return ""

async def check_for_application_form(page) -> bool:
    """Check if the page has elements that suggest it's an application form."""
    # Look for common form elements
    selectors = [
        "input[type='text']",
        "input[type='email']",
        "textarea",
        "input[type='file']",
        "button[type='submit']",
        "input[type='submit']"
    ]
    
    for selector in selectors:
        count = await page.locator(selector).count()
        if count > 0:
            return True
    
    return False

async def check_required_fields(page) -> list:
    """Check for any required fields that are empty."""
    missing_fields = []
    
    # Check text inputs, textareas, and selects with required attribute
    required_elements = page.locator("[required]")
    count = await required_elements.count()
    
    for i in range(count):
        element = required_elements.nth(i)
        tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
        value = await element.evaluate("el => el.value")
        
        if not value:
            # Enhanced debugging: get more element details
            details = await element.evaluate("""el => {
                return {
                    tagName: el.tagName,
                    id: el.id,
                    name: el.name,
                    type: el.type,
                    className: el.className,
                    placeholder: el.placeholder,
                    labels: Array.from(el.labels || []).map(l => l.textContent)
                }
            }""")
            
            logger.info(f"Missing required field details: {details}")
            
            # Try to get a description of the field
            label = await element.evaluate("""el => {
                if (el.labels && el.labels.length > 0) {
                    return el.labels[0].textContent.trim();
                } else if (el.placeholder) {
                    return el.placeholder;
                } else if (el.name) {
                    return el.name;
                } else {
                    return el.id || 'Unknown field';
                }
            }""")
            
            missing_fields.append(label)
    
    return missing_fields

async def find_submit_button(page):
    """Find the submit button on the form."""
    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit')",
        "button:has-text('Apply')",
        ".submit-button",
        "#submit-button"
    ]
    
    for selector in submit_selectors:
        submit_button = page.locator(selector)
        count = await submit_button.count()
        if count > 0:
            return submit_button.first
    
    return None

async def job_processing_service():
    """Main job processing service loop."""
    queue_manager = QueueManager()
    resume = load_resume_data()
    
    logger.info("Starting job processing service")
    logger.info(f"Initial queue stats: {queue_manager.get_queue_stats()}")
    
    while True:
        try:
            # Get the next job from the queue
            job = queue_manager.get_next_job()
            
            if not job:
                logger.info("No jobs in queue. Waiting...")
                await asyncio.sleep(15)
                continue
            
            job_id = job.get('id')
            logger.info(f"Processing job {job_id}")
            
            # Process the job
            success, message, details = await process_job(job, resume)
            
            # Update job status based on result
            if success:
                logger.info(f"Job {job_id} completed successfully: {message}")
                queue_manager.mark_job_complete(job_id, details)
            else:
                if "missing required fields" in message.lower() or "submit button not found" in message.lower():
                    logger.warning(f"Job {job_id} needs manual review: {message}")
                    queue_manager.mark_job_needs_review(job_id, message)
                else:
                    # Determine if we should retry
                    attempts = job.get('attempts', 1)
                    if attempts < 3:  # Retry up to 3 times
                        logger.warning(f"Job {job_id} failed, will retry (attempt {attempts}): {message}")
                        queue_manager.mark_job_failed(job_id, message, retry=True)
                    else:
                        logger.error(f"Job {job_id} failed after {attempts} attempts: {message}")
                        queue_manager.mark_job_failed(job_id, message, retry=False)
            
            # Wait a bit before processing the next job
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Error in job processing loop: {str(e)}")
            logger.error(traceback.format_exc())
            await asyncio.sleep(30)  # Longer delay after an error

if __name__ == "__main__":
    # Create screenshots directory if it doesn't exist
    import os
    os.makedirs("screenshots", exist_ok=True)
    
    # Run the service
    asyncio.run(job_processing_service())
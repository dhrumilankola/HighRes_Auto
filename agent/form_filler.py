from gemini_helper import get_gemini_response
import re
import asyncio

# ----- FILL BASIC INFO FIELDS -----
async def fill_basic_info(page, resume):
    async def fill(selector, value):
        try:
            field = page.locator(selector)
            if await field.count() > 0 and await field.is_visible():
                await field.fill(value)
                print(f"✅ Filled {selector} with {value}")
        except Exception as e:
            print(f"⚠️ Error filling {selector}: {e}")

    await fill("#first_name", "Sai Sreekar")
    await fill("#last_name", "Sarvepalli")
    await fill("#email", resume["personal_info"]["email"])
    await fill("#phone", resume["personal_info"]["phone"])


# ----- RESUME UPLOAD -----
async def upload_resume(page):
    try:
        resume_field = page.locator("input#resume")
        if await resume_field.count() > 0:
            await resume_field.set_input_files("./resume_data/resume_data.pdf")
            print("✅ Resume uploaded")
    except Exception as e:
        print(f"⚠️ Resume upload failed: {e}")


import asyncio

async def fill_custom_dropdown(page, field_id, option_text):
    """Fills a custom dropdown (non-<select>) by clicking the input and then the option."""
    input_selector = f"input.select__input#{field_id}"
    input_elem = page.locator(input_selector)
    if await input_elem.count() == 0:
        print(f"⚠️ Custom dropdown input with id '{field_id}' not found")
        return False

    try:
        # Click the input to open the dropdown options
        await input_elem.click()
        print(f"🔽 Clicked on '{field_id}' dropdown to expand options")

        # Wait for the options to appear
        await page.wait_for_selector(".select__option", timeout=5000)

        # Find the option element that matches our desired value
        option_locator = page.locator(".select__option", has_text=option_text)
        if await option_locator.count() > 0:
            await option_locator.first.click()
            print(f"✅ Selected '{option_text}' for '{field_id}' dropdown")
            return True
        else:
            print(f"⚠️ Option '{option_text}' not found for '{field_id}'")
            return False
    except Exception as e:
        print(f"⚠️ Error handling custom dropdown '{field_id}': {e}")
        return False

import asyncio

import asyncio

async def fill_demographics(page):
    print("\n📋 Scanning for demographic dropdowns (custom implementation)...")

    # Define the fields in order
    demographic_fields = [
        {"key": "hispanic", "labelContains": ["hispanic", "latino"], "option": "No"},
        {"key": "race",      "labelContains": ["race"], "option": "Asian"},  # relaxed for race
        {"key": "veteran",   "labelContains": ["veteran"], "option": "I am not a protected veteran"},
        {"key": "disability","labelContains": ["disability"], "option": "No, I do not have a disability"},
        {"key": "gender",    "labelContains": ["gender"], "option": "Male"}
    ]

    # Process each field, with extra attempts for fields that depend on previous interactions
    for field in demographic_fields:
        success = False
        max_attempts = 3 if "race" in field["labelContains"] else 2
        attempts = 0
        while not success and attempts < max_attempts:
            # Re-scan for all custom dropdown inputs
            all_inputs = page.locator("input.select__input")
            count = await all_inputs.count()
            for i in range(count):
                input_elem = all_inputs.nth(i)
                # Retrieve label text from aria-labelledby or aria-label
                label_text = ""
                aria_labelledby = await input_elem.get_attribute("aria-labelledby") or ""
                aria_label = await input_elem.get_attribute("aria-label") or ""
                if aria_labelledby:
                    label_elem = page.locator(f"#{aria_labelledby}")
                    if await label_elem.count() > 0:
                        label_text = (await label_elem.inner_text()).lower()
                if not label_text and aria_label:
                    label_text = aria_label.lower()

                # Debug: print out the label text for inspection
                # print(f"Found dropdown with label: '{label_text}'")

                # Use an OR (any) condition rather than requiring all keywords to match
                if any(fragment in label_text for fragment in field["labelContains"]):
                    try:
                        await input_elem.click()
                        print(f"🔽 Opened dropdown for label '{label_text}'")
                        # Wait for the dropdown options to appear
                        await page.wait_for_selector(".select__option", timeout=5000)
                        option_locator = page.locator(".select__option", has_text=field["option"])
                        if await option_locator.count() > 0:
                            await option_locator.first.click()
                            print(f"✅ Selected '{field['option']}' for '{label_text}'")
                            success = True
                            break  # move on to next field
                        else:
                            print(f"⚠️ Option '{field['option']}' not found for '{label_text}'")
                    except Exception as e:
                        print(f"⚠️ Error filling '{label_text}' with '{field['option']}': {e}")
            if not success:
                print(f"⚠️ Could not fill dropdown for label fragments: {field['labelContains']}, attempt {attempts+1}")
                # If it's the race field, wait a bit longer to allow it to render after hispanic selection.
                wait_time = 3000 if "race" in field["labelContains"] else 2000
                await page.wait_for_timeout(wait_time)
            attempts += 1

    print("🎉 Finished attempting to fill custom demographic dropdowns.")




# ----- FILL PORTFOLIO AND LINKEDIN -----
async def fill_portfolio_and_linkedin(page, resume):
    portfolio_url = resume.get("personal_info", {}).get("portfolio", "")
    linkedin_url = "https://www.linkedin.com/in/saisreekarsarvepalli"

    async def try_fill(keywords, value):
        inputs = page.locator("input[type='text']")
        count = await inputs.count()
        for i in range(count):
            input_elem = inputs.nth(i)
            label = await input_elem.evaluate("el => el.labels?.[0]?.innerText || ''")
            if any(kw in label.lower() for kw in keywords):
                try:
                    await input_elem.fill(value)
                    print(f"✅ Filled field with label '{label}'")
                    return True
                except:
                    continue
        return False

    if portfolio_url:
        await try_fill(["portfolio", "website"], portfolio_url)
    await try_fill(["linkedin"], linkedin_url)


# ----- ANSWER OPEN-ENDED QUESTIONS -----
async def answer_open_ended_questions(page, resume, job_url):
    textareas = page.locator("textarea")
    count = await textareas.count()
    for i in range(count):
        textarea = textareas.nth(i)
        label = await textarea.evaluate("el => el.labels?.[0]?.innerText || ''")
        if "why" in label.lower():
            question_text = label
            company_match = re.search(r'(?:https?://(?:www\.)?)?([^/]+)', job_url)
            company_name = "the company"
            if company_match:
                parts = company_match.group(1).split(".")
                if parts:
                    company_name = parts[0].capitalize()

            resume_summary = resume.get("summary", "")
            skills = ", ".join(resume.get("skills", []))

            prompt = f"""
            Based on the following information, write a concise and compelling response (150-200 words) to the question: '{question_text}'

            About the question: This appears to be asking why I want to work at {company_name}
            My resume summary: {resume_summary}
            My key skills: {skills}

            Make the response specific to {company_name}, mentioning my relevant skills and experience, and expressing genuine interest in the company's mission and work.
            """

            print(f"Generating answer for: {question_text}")
            response = await get_gemini_response(prompt)
            await textarea.fill(response)
            print("✅ Answered open-ended question")
            break

import asyncio
import base64
import json
import re
from typing import Union, Dict, Any, List

from playwright.async_api import Browser, Page, Playwright, async_playwright
from agents import Agent, AsyncComputer, Button, ComputerTool, Environment, ModelSettings, Runner, trace
import google.generativeai as genai

# ---------- Configure Gemini ----------
genai.configure(api_key="AIzaSyD9vOmTfraMqIZTLqNjCbS-NGzG7UJW3ko")
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

# ---------- Load Resume Data ----------
def load_resume_data(path: str = "./resume_data/resume_data.json") -> dict:
    with open(path, "r") as file:
        return json.load(file)

# ---------- Key Mappings ----------
CUA_KEY_TO_PLAYWRIGHT_KEY = {
    "/": "Divide", "\\": "Backslash", "alt": "Alt", "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft", "arrowright": "ArrowRight", "arrowup": "ArrowUp",
    "backspace": "Backspace", "capslock": "CapsLock", "cmd": "Meta",
    "ctrl": "Control", "delete": "Delete", "end": "End", "enter": "Enter",
    "esc": "Escape", "home": "Home", "insert": "Insert", "option": "Alt",
    "pagedown": "PageDown", "pageup": "PageUp", "shift": "Shift", "space": " ",
    "super": "Meta", "tab": "Tab", "win": "Meta"
}

# ---------- Local Browser Controlled by Agent ----------
class LocalPlaywrightComputer(AsyncComputer):
    def __init__(self, job_url: str):
        self.job_url = job_url
        self._playwright: Union[Playwright, None] = None
        self._browser: Union[Browser, None] = None
        self._page: Union[Page, None] = None

    async def _get_browser_and_page(self) -> tuple[Browser, Page]:
        width, height = self.dimensions
        browser = await self.playwright.chromium.launch(headless=False, args=[f"--window-size={width},{height}"])
        page = await browser.new_page()
        await page.set_viewport_size({"width": width, "height": height})
        await page.goto(self.job_url)
        return browser, page

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser, self._page = await self._get_browser_and_page()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def playwright(self) -> Playwright:
        return self._playwright

    @property
    def browser(self) -> Browser:
        return self._browser

    @property
    def page(self) -> Page:
        return self._page

    @property
    def environment(self) -> Environment:
        return "browser"

    @property
    def dimensions(self) -> tuple[int, int]:
        return (1280, 800)

    async def screenshot(self) -> str:
        png_bytes = await self.page.screenshot(full_page=False)
        return base64.b64encode(png_bytes).decode("utf-8")

    async def click(self, x: int, y: int, button: Button = "left") -> None:
        await self.page.mouse.click(x, y, button=button)

    async def double_click(self, x: int, y: int) -> None:
        await self.page.mouse.dblclick(x, y)

    async def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        await self.page.mouse.move(x, y)
        await self.page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")

    async def type(self, text: str) -> None:
        await self.page.keyboard.type(text)

    async def wait(self) -> None:
        await asyncio.sleep(1)

    async def move(self, x: int, y: int) -> None:
        await self.page.mouse.move(x, y)

    async def keypress(self, keys: list[str]) -> None:
        for key in keys:
            await self.page.keyboard.press(CUA_KEY_TO_PLAYWRIGHT_KEY.get(key.lower(), key))

    async def drag(self, path: list[tuple[int, int]]) -> None:
        if not path:
            return
        await self.page.mouse.move(path[0][0], path[0][1])
        await self.page.mouse.down()
        for px, py in path[1:]:
            await self.page.mouse.move(px, py)
        await self.page.mouse.up()

# ---------- Use Gemini to generate text responses ----------
async def get_gemini_response(prompt: str) -> str:
    try:
        # Add safety settings and properly structure the generation request
        safety_settings = {
            "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
            "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
            "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
        }
        
        response = gemini_model.generate_content(
            prompt,
            safety_settings=safety_settings
        )
        
        return response.text.strip()
    except Exception as e:
        print(f"⚠ Gemini generation error: {e}")
        return "I'm very excited to apply and believe I fit the role well."

# ---------- Main ----------
async def main():
    resume = load_resume_data()
    job_url = "https://job-boards.greenhouse.io/6sense/jobs/6666248"  # Replace with actual job URL

    async with LocalPlaywrightComputer(job_url) as computer:
        # Initial wait for page to fully load
        await computer.page.wait_for_load_state("networkidle")
        print("Page loaded, starting form fill process...")
        
        # Create the agent
        agent = Agent(
            name="JobAppAgent",
            instructions="Use tools to help fill job forms.",
            tools=[ComputerTool(computer)],
            model="computer-use-preview",
            model_settings=ModelSettings(truncation="auto"),
        )
        
        # Store filled fields to avoid duplicate filling
        filled_fields = set()
        
        # Function to fill a form field
        async def fill_field(selector, value, field_name, required=False, skip_if_filled=True):
            if selector in filled_fields and skip_if_filled:
                print(f"⚠️ Skipping {field_name} as it was already filled")
                return False
                
            try:
                element = computer.page.locator(selector)
                count = await element.count()
                if count == 0:
                    if required:
                        print(f"⚠️ Required field {field_name} not found with selector: {selector}")
                    return False
                
                is_visible = await element.is_visible()
                if not is_visible:
                    print(f"⚠️ Field {field_name} with selector {selector} is not visible")
                    return False
                
                # Check if already has a value
                current_value = await element.input_value()
                if current_value and skip_if_filled:
                    print(f"✅ Field {field_name} already has value: {current_value}")
                    filled_fields.add(selector)
                    return True
                
                # Fill the field
                await element.fill(value)
                print(f"✅ Filled {field_name}: {value}")
                filled_fields.add(selector)
                return True
            except Exception as e:
                print(f"⚠️ Error filling {field_name}: {e}")
                return False
        
        # Enhanced dropdown selection function
        async def handle_dropdown(selector, option_text, field_name):
            try:
                dropdown = computer.page.locator(selector)
                count = await dropdown.count()
                if count == 0:
                    print(f"⚠️ Dropdown {field_name} not found with selector: {selector}")
                    return False
                
                is_visible = await dropdown.is_visible()
                if not is_visible:
                    print(f"⚠️ Dropdown {field_name} with selector {selector} is not visible")
                    return False
                
                print(f"Found dropdown: {field_name}")
                
                # Get all options
                options = await dropdown.evaluate("""(el) => {
                    return Array.from(el.options).map(opt => ({
                        value: opt.value, 
                        text: opt.text, 
                        index: opt.index
                    }));
                }""")
                
                print(f"Available options: {options}")
                
                # Skip empty first option (usually "Select...")
                valid_options = [opt for opt in options if opt["value"] and opt["text"]]
                if not valid_options:
                    print(f"⚠️ No valid options found for {field_name}")
                    return False
                
                # Find matching option
                matching_option = None
                for opt in valid_options:
                    if option_text.lower() in opt["text"].lower():
                        matching_option = opt
                        break
                
                if not matching_option:
                    # If no match found, use the first valid option
                    matching_option = valid_options[0]
                    print(f"⚠️ No matching option found for '{option_text}', using: {matching_option['text']}")
                
                # Try selecting by value
                try:
                    await dropdown.select_option(value=matching_option["value"])
                    print(f"✅ Selected '{matching_option['text']}' for {field_name}")
                    return True
                except Exception as e:
                    print(f"⚠️ Error selecting by value: {e}")
                    
                    # Try by index as fallback
                    try:
                        await dropdown.select_option(index=matching_option["index"])
                        print(f"✅ Selected option at index {matching_option['index']} for {field_name}")
                        return True
                    except Exception as e2:
                        print(f"⚠️ Error selecting by index: {e2}")
                        
                        # Last resort: try clicking
                        try:
                            # Click to open dropdown
                            await dropdown.click()
                            await asyncio.sleep(0.5)
                            
                            # Try to find and click the option
                            option_locator = computer.page.locator(f"option:has-text('{matching_option['text']}')")
                            if await option_locator.count() > 0:
                                await option_locator.click()
                                print(f"✅ Selected option by clicking: {matching_option['text']}")
                                return True
                        except Exception as e3:
                            print(f"⚠️ Error selecting by clicking: {e3}")
                
                return False
            except Exception as e:
                print(f"⚠️ Error handling dropdown {field_name}: {e}")
                return False
        
        # Handle basic fields first
        await fill_field("#first_name", "Sai Sreekar", "First Name", required=True)
        await fill_field("#last_name", "Sarvepalli", "Last Name", required=True)
        await fill_field("#email", resume["personal_info"]["email"], "Email", required=True)
        await fill_field("#phone", resume["personal_info"]["phone"], "Phone", required=True)
            
        # Handle resume upload
        resume_uploaded = False
        try:
            resume_field = computer.page.locator("#resume")
            if await resume_field.count() > 0:
                is_visible = await resume_field.is_visible()
                print(f"Found resume field with selector '#resume', visible: {is_visible}")
                
                if is_visible:
                    await resume_field.set_input_files('./resume_data/resume_data.pdf')
                    print("✅ Resume uploaded")
                    resume_uploaded = True
                    
                    # Wait for dynamic fields to load
                    print("Waiting for dynamic fields to load...")
                    await computer.page.wait_for_timeout(5000)
            else:
                print("Resume field with ID 'resume' not found, trying alternative selectors")
        except Exception as e:
            print(f"⚠️ Error uploading resume: {e}")
            
        if not resume_uploaded:
            print("⚠️ Trying alternative methods for resume upload...")
            
            # Try alternative methods
            resume_selectors = [
                "input[type='file'][accept*='pdf']",
                "input[type='file'][name*='resume']",
                "input[type='file']"  # Last resort
            ]
            
            for selector in resume_selectors:
                try:
                    resume_field = computer.page.locator(selector)
                    count = await resume_field.count()
                    if count > 0:
                        is_visible = await resume_field.is_visible()
                        print(f"Found resume field with selector '{selector}', visible: {is_visible}")
                        
                        if is_visible:
                            await resume_field.set_input_files('./resume_data/resume_data.pdf')
                            print(f"✅ Resume uploaded using selector: {selector}")
                            resume_uploaded = True
                            
                            # Wait for dynamic fields to load
                            print("Waiting for dynamic fields to load...")
                            await computer.page.wait_for_timeout(5000)
                            break
                except Exception as e:
                    print(f"⚠️ Error with resume selector '{selector}': {e}")
                    continue
        
        if not resume_uploaded:
            print("⚠️ Could not upload resume automatically. Please upload manually.")
        
        # Find and handle any dropdown/select fields for demographic information
        print("\nScanning for demographic dropdowns...")
        
        # Get all <select> elements
        select_elements = computer.page.locator("select")
        select_count = await select_elements.count()
        print(f"Found {select_count} dropdown elements")
        
        if select_count > 0:
            # First scan the page to find what kinds of dropdowns we're dealing with
            demographic_dropdowns = {
                "gender": {"found": False, "selector": "", "option": "Male"},
                "hispanic": {"found": False, "selector": "", "option": "No"},
                "race": {"found": False, "selector": "", "option": "Asian"},
                "veteran": {"found": False, "selector": "", "option": "I am not a protected veteran"},
                "disability": {"found": False, "selector": "", "option": "No, I do not have a disability"}
            }
            
            # First pass - identify dropdowns
            for i in range(select_count):
                select = select_elements.nth(i)
                
                # Get attributes
                id_attr = await select.get_attribute("id") or ""
                name_attr = await select.get_attribute("name") or ""
                
                # Get surrounding text for context
                context_text = await select.evaluate("""
                (el) => {
                    // Get text from parent elements
                    let node = el;
                    let depth = 0;
                    let text = "";
                    
                    while (node && depth < 3) {
                        if (node.parentElement) {
                            text += " " + (node.parentElement.innerText || "");
                        }
                        node = node.parentElement;
                        depth++;
                    }
                    
                    // Also check for labels associated with this element
                    if (el.id) {
                        const label = document.querySelector(label[for="${el.id}"]);
                        if (label) {
                            text += " " + (label.innerText || "");
                        }
                    }
                    
                    return text.toLowerCase();
                }
                """)
                
                # Determine dropdown type
                selector = f"select#{id_attr}" if id_attr else f"select[name='{name_attr}']"
                
                print(f"\nExamining dropdown #{i+1}")
                print(f"ID: {id_attr}")
                print(f"Name: {name_attr}")
                print(f"Context: {context_text[:100]}...")  # Show first 100 chars of context
                
                if "gender" in id_attr.lower() or "gender" in name_attr.lower() or "gender" in context_text:
                    demographic_dropdowns["gender"]["found"] = True
                    demographic_dropdowns["gender"]["selector"] = selector
                    print("✓ Identified as Gender dropdown")
                
                elif "hispanic" in id_attr.lower() or "hispanic" in name_attr.lower() or "hispanic" in context_text or "latino" in context_text:
                    demographic_dropdowns["hispanic"]["found"] = True
                    demographic_dropdowns["hispanic"]["selector"] = selector
                    print("✓ Identified as Hispanic/Latino dropdown")
                
                elif "race" in id_attr.lower() or "race" in name_attr.lower() or "race" in context_text or "ethnicity" in context_text:
                    demographic_dropdowns["race"]["found"] = True
                    demographic_dropdowns["race"]["selector"] = selector
                    print("✓ Identified as Race/Ethnicity dropdown")
                
                elif "veteran" in id_attr.lower() or "veteran" in name_attr.lower() or "veteran" in context_text:
                    demographic_dropdowns["veteran"]["found"] = True
                    demographic_dropdowns["veteran"]["selector"] = selector
                    print("✓ Identified as Veteran Status dropdown")
                
                elif "disability" in id_attr.lower() or "disability" in name_attr.lower() or "disability" in context_text:
                    demographic_dropdowns["disability"]["found"] = True
                    demographic_dropdowns["disability"]["selector"] = selector
                    print("✓ Identified as Disability Status dropdown")
                else:
                    print("? Unidentified dropdown type")
            
            # Second pass - fill the identified dropdowns
            for dropdown_type, dropdown_info in demographic_dropdowns.items():
                if dropdown_info["found"]:
                    print(f"\nFilling {dropdown_type} dropdown...")
                    success = await handle_dropdown(
                        dropdown_info["selector"], 
                        dropdown_info["option"],
                        f"{dropdown_type.capitalize()} Dropdown"
                    )
                    if not success:
                        print(f"⚠️ Failed to fill {dropdown_type} dropdown")
                        
                        # Try clicking approach for stubborn dropdowns
                        try:
                            dropdown = computer.page.locator(dropdown_info["selector"])
                            if await dropdown.count() > 0 and await dropdown.is_visible():
                                # Click to open dropdown
                                await dropdown.click()
                                await asyncio.sleep(1)
                                
                                # Look for option by text content
                                option_text = dropdown_info["option"]
                                option = computer.page.locator(f"text='{option_text}'").first
                                
                                if await option.count() > 0:
                                    await option.click()
                                    print(f"✅ Selected {dropdown_type} option by text clicking")
                        except Exception as e:
                            print(f"⚠️ Error with click approach: {e}")
        else:
            print("No dropdown elements found on the page")
        
        # Handle Website/Portfolio field
        print("\nLooking for Website/Portfolio field...")
        website_selectors = [
            "#website",
            "#portfolio",
            "input[id*='website']",
            "input[id*='portfolio']",
            "input[name*='website']",
            "input[name*='portfolio']",
            "input[placeholder*='website']",
            "input[placeholder*='portfolio']"
        ]
        
        website_filled = False
        for selector in website_selectors:
            portfolio_url = resume.get("personal_info", {}).get("portfolio", "")
            if portfolio_url and await fill_field(selector, portfolio_url, "Website/Portfolio"):
                website_filled = True
                break
        
        if not website_filled and resume.get("personal_info", {}).get("portfolio"):
            print("⚠️ Could not find Website/Portfolio field using common selectors")
            
            # Try a more general approach - look for visible text fields with "website" or "portfolio" in surrounding text
            try:
                all_inputs = computer.page.locator("input[type='text']")
                input_count = await all_inputs.count()
                
                for i in range(input_count):
                    input_field = all_inputs.nth(i)
                    if not await input_field.is_visible():
                        continue
                    
                    # Get field ID and name
                    id_attr = await input_field.get_attribute("id") or ""
                    name_attr = await input_field.get_attribute("name") or ""
                    
                    # Try to get label text
                    label_text = ""
                    if id_attr:
                        label_elem = computer.page.locator(f"label[for='{id_attr}']")
                        if await label_elem.count() > 0:
                            label_text = await label_elem.inner_text()
                    
                    # Check parent elements for relevant text
                    surrounding_text = await input_field.evaluate("""
                    (el) => {
                        const textContent = [];
                        
                        // Check for label siblings
                        let sibling = el.previousElementSibling;
                        while (sibling) {
                            textContent.push(sibling.innerText || sibling.textContent);
                            sibling = sibling.previousElementSibling;
                        }
                        
                        // Check parent for text
                        let parent = el.parentElement;
                        if (parent) {
                            textContent.push(parent.innerText || parent.textContent);
                        }
                        
                        return textContent.join(' ').toLowerCase();
                    }
                    """)
                    
                    # Check if this might be a Website/Portfolio field
                    if ("website" in surrounding_text or 
                        "portfolio" in surrounding_text or
                        "website" in id_attr.lower() or 
                        "portfolio" in id_attr.lower() or
                        "website" in name_attr.lower() or
                        "portfolio" in name_attr.lower() or
                        "website" in label_text.lower() or
                        "portfolio" in label_text.lower()):
                        
                        portfolio_url = resume.get("personal_info", {}).get("portfolio", "")
                        await input_field.fill(portfolio_url)
                        print(f"✅ Filled Website/Portfolio field using context detection: {portfolio_url}")
                        website_filled = True
                        break
                
                if not website_filled and resume.get("personal_info", {}).get("portfolio"):
                    print("⚠️ Could not find Website/Portfolio field even with context detection")
            except Exception as e:
                print(f"⚠️ Error during Website/Portfolio field detection: {e}")
                
        # Handle LinkedIn field
        print("\nLooking for LinkedIn field...")
        linkedin_selectors = [
            "#linkedin_profile",
            "input[id*='linkedin']",
            "input[name*='linkedin']",
            "input[placeholder*='LinkedIn']"
        ]
        
        linkedin_filled = False
        for selector in linkedin_selectors:
            if await fill_field(selector, "https://www.linkedin.com/in/saisreekarsarvepalli", "LinkedIn"):
                linkedin_filled = True
                break
        
        if not linkedin_filled:
            print("⚠️ Could not find LinkedIn field using common selectors")
            
            # Try a more general approach - look for visible text fields with "linkedin" in surrounding text
            try:
                all_inputs = computer.page.locator("input[type='text']")
                input_count = await all_inputs.count()
                
                for i in range(input_count):
                    input_field = all_inputs.nth(i)
                    if not await input_field.is_visible():
                        continue
                    
                    # Get field ID and name
                    id_attr = await input_field.get_attribute("id") or ""
                    name_attr = await input_field.get_attribute("name") or ""
                    
                    # Try to get label text
                    label_text = ""
                    if id_attr:
                        label_elem = computer.page.locator(f"label[for='{id_attr}']")
                        if await label_elem.count() > 0:
                            label_text = await label_elem.inner_text()
                    
                    # Check parent elements for "linkedin" text
                    surrounding_text = await input_field.evaluate("""
                    (el) => {
                        const textContent = [];
                        
                        // Check for label siblings
                        let sibling = el.previousElementSibling;
                        while (sibling) {
                            textContent.push(sibling.innerText || sibling.textContent);
                            sibling = sibling.previousElementSibling;
                        }
                        
                        // Check parent for text
                        let parent = el.parentElement;
                        if (parent) {
                            textContent.push(parent.innerText || parent.textContent);
                        }
                        
                        return textContent.join(' ');
                    }
                    """)
                    
                    # Check if this might be a LinkedIn field
                    if ("linkedin" in surrounding_text.lower() or 
                        "linkedin" in id_attr.lower() or 
                        "linkedin" in name_attr.lower() or
                        "linkedin" in label_text.lower()):
                        
                        await input_field.fill("https://www.linkedin.com/in/saisreekarsarvepalli")
                        print("✅ Filled LinkedIn field using context detection")
                        linkedin_filled = True
                        break
                
                if not linkedin_filled:
                    print("⚠️ Could not find LinkedIn field even with context detection")
            except Exception as e:
                print(f"⚠️ Error during LinkedIn field detection: {e}")
        
        # Look for open-ended questions like "Why do you want to work here?"
        print("\nScanning for open-ended questions...")
        why_work_selectors = [
            "textarea[id*='question']",
            "textarea[id*='why']",
            "textarea[name*='why']",
            "textarea"  # Last resort
        ]
        
        why_work_filled = False
        for selector in why_work_selectors:
            try:
                why_field = computer.page.locator(selector)
                count = await why_field.count()
                if count > 0 and await why_field.is_visible():
                    # Extract the company name and question text
                    question_text = await why_field.evaluate("""
                    (el) => {
                        // Try to find the label or question text
                        const textContent = [];
                        
                        // Check for label with 'for' attribute
                        const id = el.getAttribute('id');
                        if (id) {
                            const label = document.querySelector(label[for="${id}"]);
                            if (label) {
                                return label.innerText || label.textContent;
                            }
                        }
                        
                        // Check surrounding elements for question text
                        let parent = el.parentElement;
                        let depth = 0;
                        
                        while (parent && depth < 3) {
                            // Filter out long text blocks and just get short labels/headings
                            const children = parent.childNodes;
                            for (const child of children) {
                                if (child.nodeType === Node.TEXT_NODE && child.textContent.trim()) {
                                    textContent.push(child.textContent.trim());
                                } else if (child.nodeType === Node.ELEMENT_NODE && 
                                          child !== el && 
                                          (child.tagName === 'LABEL' || 
                                           child.tagName === 'H1' || 
                                           child.tagName === 'H2' || 
                                           child.tagName === 'H3' || 
                                           child.tagName === 'H4' || 
                                           child.tagName === 'H5' || 
                                           child.tagName === 'H6' || 
                                           child.tagName === 'P')) {
                                    const text = child.innerText || child.textContent;
                                    if (text && text.length < 200) { // Only include shorter text elements that are likely labels
                                        textContent.push(text);
                                    }
                                }
                            }
                            
                            parent = parent.parentElement;
                            depth++;
                        }
                        
                        return textContent.join(' ');
                    }
                    """)
                    
                    # Extract company name from URL or question text
                    company_match = re.search(r'(?:https?://(?:www\.)?)?([^/]+)', job_url)
                    company_name = "the company"
                    
                    if company_match:
                        company_domain = company_match.group(1)
                        company_parts = company_domain.split('.')
                        if len(company_parts) > 1 and company_parts[0] != "job-boards" and company_parts[0] != "www":
                            company_name = company_parts[0].capitalize()
                    
                    # Also look for company name in the question text
                    if re.search(r'(?i)why[^a-z]*(?:work|join|apply)[^a-z]*(?:at|with|for)[^a-z]*([a-z0-9 ]+)', question_text.lower()):
                        company_match = re.search(r'(?i)why[^a-z]*(?:work|join|apply)[^a-z]*(?:at|with|for)[^a-z]*([a-z0-9 ]+)', question_text.lower())
                        if company_match:
                            company_name = company_match.group(1).strip().title()
                    
                    # Create a dynamic prompt based on the question and resume
                    resume_summary = resume.get("summary", "")
                    skills = ", ".join(resume.get("skills", []))
                    
                    prompt = f"""Based on the following information, write a concise and compelling response (150-200 words) to the question: '{question_text}'
                    
                    About the question: This appears to be asking why I want to work at {company_name}
                    
                    My resume summary: {resume_summary}
                    
                    My key skills: {skills}
                    
                    Make the response specific to {company_name}, mentioning my relevant skills and experience, and expressing genuine interest in the company's mission and work.
                    Keep it professional, enthusiastic, and tailored to this specific company.
                    """
                    
                    print(f"Generating response for question: '{question_text}'")
                    print(f"Identified company: {company_name}")
                    
                    response = await get_gemini_response(prompt)
                    
                    await why_field.fill(response)
                    print(f"✅ Filled open-ended question: {response[:50]}...")
                    why_work_filled = True
                    break
            except Exception as e:
                print(f"⚠️ Error with 'Why work' selector '{selector}': {e}")
        
        if not why_work_filled:
            print("⚠️ Could not find any open-ended questions using common selectors")
            
            # Try to find it by looking for textareas with relevant context
            try:
                all_textareas = computer.page.locator("textarea")
                textarea_count = await all_textareas.count()
                
                for i in range(textarea_count):
                    textarea = all_textareas.nth(i)
                    if not await textarea.is_visible():
                        continue
                    
                    # Get surrounding text
                    surrounding_text = await textarea.evaluate("""
                    (el) => {
                        const textContent = [];
                        
                        // Check parent elements up to 3 levels
                        let parent = el.parentElement;
                        let depth = 0;
                        
                        while (parent && depth < 3) {
                            textContent.push(parent.innerText || parent.textContent);
                            parent = parent.parentElement;
                            depth++;
                        }
                        
                        return textContent.join(' ');
                    }
                    """)
                    
                    if "why" in surrounding_text.lower():
                        # Extract company name from surrounding text if possible
                        company_name = "the company"
                        
                        # Try to find company name in the text
                        if re.search(r'(?i)why[^a-z]*(?:work|join|apply)[^a-z]*(?:at|with|for)[^a-z]*([a-z0-9 ]+)', surrounding_text.lower()):
                            company_match = re.search(r'(?i)why[^a-z]*(?:work|join|apply)[^a-z]*(?:at|with|for)[^a-z]*([a-z0-9 ]+)', surrounding_text.lower())
                            if company_match:
                                company_name = company_match.group(1).strip().title()
                        else:
                            # Extract from URL as fallback
                            company_match = re.search(r'(?:https?://(?:www\.)?)?([^/]+)', job_url)
                            if company_match:
                                company_domain = company_match.group(1)
                                company_parts = company_domain.split('.')
                                if len(company_parts) > 1 and company_parts[0] != "job-boards" and company_parts[0] != "www":
                                    company_name = company_parts[0].capitalize()
                        
                        # Extract the actual question text from surrounding context
                        question_text = surrounding_text
                        
                        # Create a dynamic prompt based on the question and resume
                        resume_summary = resume.get("summary", "")
                        skills = ", ".join(resume.get("skills", []))
                        
                        prompt = f"""Based on the following information, write a concise and compelling response (150-200 words) explaining why I want to work at {company_name}:
                        
                        Context from the application form: '{question_text[:200]}...' if len(question_text) > 200 else question_text
                        
                        My resume summary: {resume_summary}
                        
                        My key skills: {skills}
                        
                        Make the response specific to {company_name}, mentioning my relevant skills and experience, and expressing genuine interest in the company's mission and work.
                        Keep it professional, enthusiastic, and tailored to this specific company.
                        """
                        
                        print(f"Generating response for question about working at: '{company_name}'")
                        print(f"Based on context: {question_text[:100]}..." if len(question_text) > 100 else f"Based on context: {question_text}")
                        
                        response = await get_gemini_response(prompt)
                        
                        await textarea.fill(response)
                        print(f"✅ Filled open-ended question using context detection: {response[:50]}...")
                        why_work_filled = True
                        break
            except Exception as e:
                print(f"⚠️ Error during 'Why work' context detection: {e}")
        
        # Try direct interaction with dropdowns by simulating clicks
        print("\nAttempting direct interaction with dropdowns...")
        try:
            # Common demographic dropdown IDs and patterns
            demographic_fields = [
                {"name": "Gender", "keywords": ["gender"], "value": "Male", "priority": 1},
                {"name": "Hispanic/Latino", "keywords": ["hispanic", "latino"], "value": "No", "priority": 2},
                {"name": "Race/Ethnicity", "keywords": ["race", "ethnicity"], "value": "Asian", "priority": 3},
                {"name": "Veteran Status", "keywords": ["veteran"], "value": "I am not a protected veteran", "priority": 4},
                {"name": "Disability Status", "keywords": ["disability"], "value": "No", "priority": 5}
            ]
            
            # Process fields in priority order (to ensure disability status is reached)
            demographic_fields.sort(key=lambda x: x["priority"])
            
            # Find all dropdowns that look like select elements but might be custom implementations
            dropdown_elements = computer.page.locator("div[role='listbox'], div[class*='dropdown'], div[class*='select'], select")
            dropdown_count = await dropdown_elements.count()
            print(f"Found {dropdown_count} potential dropdown elements")
            
            for i in range(dropdown_count):
                dropdown = dropdown_elements.nth(i)
                if not await dropdown.is_visible():
                    continue
                
                # Get context from surrounding elements
                context = await dropdown.evaluate("""
                (el) => {
                    // Get surrounding text to figure out what this dropdown is for
                    let context = '';
                    
                    // Check for a visible element with text inside or around this element
                    const parentText = el.parentElement ? el.parentElement.innerText : '';
                    const prevSiblingText = el.previousElementSibling ? el.previousElementSibling.innerText : '';
                    
                    context = (prevSiblingText + ' ' + parentText).toLowerCase();
                    return context;
                }
                """)
                
                # Limit processing time per dropdown to avoid getting stuck
                MAX_DROPDOWN_TIME = 2  # seconds
                start_time = asyncio.get_event_loop().time()
                
                matched_field = None
                for field in demographic_fields:
                    if any(keyword in context for keyword in field["keywords"]):
                        matched_field = field
                        break
                    
                    # Check if we've spent too much time on dropdowns
                    if asyncio.get_event_loop().time() - start_time > MAX_DROPDOWN_TIME:
                        print(f"⚠️ Time limit exceeded for dropdown processing")
                        break
                
                if matched_field:
                    print(f"Found {matched_field['name']} dropdown through context: '{context[:50]}...'")
                    
                    try:
                        # Click to open the dropdown
                        await dropdown.click()
                        await asyncio.sleep(1)
                        
                        # Now find the option that matches our desired value
                        target_value = matched_field["value"]
                        
                        # Look for elements that might be dropdown options
                        option_selectors = [
                            f"li:text-is('{target_value}')",
                            f"div[role='option']:text-is('{target_value}')",
                            f"div:text-is('{target_value}')",
                            f"text='{target_value}'"
                        ]
                        
                        option_found = False
                        for option_selector in option_selectors:
                            try:
                                option = computer.page.locator(option_selector)
                                if await option.count() > 0 and await option.is_visible():
                                    await option.click()
                                    print(f"✅ Selected '{target_value}' for {matched_field['name']}")
                                    option_found = True
                                    break
                            except Exception as e:
                                print(f"⚠️ Error with selector '{option_selector}': {e}")
                        
                        if not option_found:
                            # If exact match not found, try partial match
                            partial_selectors = [
                                f"li:has-text('{target_value}')",
                                f"div[role='option']:has-text('{target_value}')",
                                f"div:has-text('{target_value}')"
                            ]
                            
                            for selector in partial_selectors:
                                try:
                                    option = computer.page.locator(selector)
                                    if await option.count() > 0 and await option.is_visible():
                                        await option.click()
                                        print(f"✅ Selected partial match for '{target_value}' in {matched_field['name']}")
                                        option_found = True
                                        break
                                except Exception as e:
                                    print(f"⚠️ Error with partial selector '{selector}': {e}")
                            
                            if not option_found:
                                # If still no match, just select something (first non-empty option)
                                try:
                                    options = computer.page.locator("li, div[role='option'], option")
                                    options_count = await options.count()
                                    
                                    for j in range(min(options_count, 10)):  # Limit to first 10 to avoid too much processing
                                        option = options.nth(j)
                                        if await option.is_visible():
                                            option_text = await option.text_content()
                                            if option_text and "select" not in option_text.lower():
                                                await option.click()
                                                print(f"✅ Selected fallback option '{option_text}' for {matched_field['name']}")
                                                break
                                except Exception as e:
                                    print(f"⚠️ Error with fallback option selection: {e}")
                    except Exception as e:
                        print(f"⚠️ Error interacting with {matched_field['name']} dropdown: {e}")
                        
                    # Add a short timeout to prevent getting stuck on one dropdown
                    # and limit excessive scrolling
                    await asyncio.sleep(0.2)
                    
                    # Skip further processing after 3 successful dropdown interactions
                    # to avoid repeated handling of the same dropdowns
                    if i >= 3 and matched_field and matched_field["name"] in ["Gender", "Hispanic/Latino", "Race/Ethnicity"]:
                        print(f"Skipping further processing of {matched_field['name']} dropdown (already handled)")
                        continue
        except Exception as e:
            print(f"⚠️ Error during direct dropdown interaction: {e}")
        
        # Add explicit handling for Disability Status field to make sure it gets handled
        print("\nSpecifically handling Disability Status field...")
        try:
            # Try using JavaScript to directly manipulate the select elements
            # This bypasses the need for clicking which might get intercepted
            dropdown_js_result = await computer.page.evaluate("""
            () => {
                // Find all select elements or React select containers
                const results = [];
                
                // Handle standard select elements
                document.querySelectorAll('select').forEach(select => {
                    const label = findLabelForElement(select);
                    if (label && label.toLowerCase().includes('disability')) {
                        // Find the "No" option
                        for (let i = 0; i < select.options.length; i++) {
                            const option = select.options[i];
                            if (option.text.toLowerCase().includes('no') || 
                                option.text.toLowerCase().includes('not') || 
                                option.text.toLowerCase().includes("don't")) {
                                // Select this option
                                select.selectedIndex = i;
                                select.dispatchEvent(new Event('change', { bubbles: true }));
                                results.push({ type: 'standard', label: label, value: option.text });
                                break;
                            }
                        }
                    }
                });
                
                // Handle React-style selects (which use divs with specific classes)
                document.querySelectorAll('div[class*="select"], div[class*="dropdown"]').forEach(div => {
                    // Check if this might be a disability dropdown
                    const parentText = div.textContent || '';
                    if (parentText.toLowerCase().includes('disability')) {
                        // Try to find the container that has the dropdown value
                        const valueContainer = div.querySelector('div[class*="container"], div[class*="control"]');
                        if (valueContainer) {
                            // Try to find "No" option nearby
                            const options = document.querySelectorAll('div[role="option"], li');
                            for (const option of options) {
                                const optionText = option.textContent || '';
                                if (optionText.toLowerCase().includes('no') && 
                                    !optionText.toLowerCase().includes('note')) {
                                    // Try to simulate a selection - this might not work for all implementations
                                    try {
                                        // First click to open the dropdown
                                        valueContainer.click();
                                        // Then try to click the option
                                        setTimeout(() => option.click(), 100);
                                        results.push({ type: 'react', element: 'valueContainer', value: optionText });
                                    } catch (e) {
                                        results.push({ type: 'react', error: e.toString() });
                                    }
                                    break;
                                }
                            }
                        }
                    }
                });
                
                // Helper function to find a label for an element
                function findLabelForElement(element) {
                    // Check for label with 'for' attribute
                    if (element.id) {
                        const label = document.querySelector(label[for="${element.id}"]);
                        if (label) return label.textContent;
                    }
                    
                    // Check parent elements for text
                    let parent = element.parentElement;
                    let depth = 0;
                    while (parent && depth < 3) {
                        // Try to get text directly from parent
                        if (parent.textContent && parent.childNodes.length < 5) {
                            return parent.textContent;
                        }
                        
                        // Check for label elements
                        const labels = parent.querySelectorAll('label, h4, h5, h6, p');
                        for (const label of labels) {
                            if (label.textContent && label.textContent.length < 100) {
                                return label.textContent;
                            }
                        }
                        
                        parent = parent.parentElement;
                        depth++;
                    }
                    
                    return '';
                }
                
                return results;
            }
            """)
            
            if dropdown_js_result and len(dropdown_js_result) > 0:
                print(f"✅ JavaScript approach found and handled {len(dropdown_js_result)} disability dropdown(s):")
                for result in dropdown_js_result:
                    print(f"  - Type: {result.get('type', 'unknown')}, Value: {result.get('value', 'unknown')}")
            else:
                print("⚠️ JavaScript didn't find any disability dropdowns")
                
                # Try a more direct approach with specific selectors
                print("Trying direct approach with specific selectors...")
                # Target the specific React component structure used by Greenhouse
                react_select_js_result = await computer.page.evaluate("""
                () => {
                    // Specific targeting for Greenhouse React selects
                    const results = [];
                    
                    // Find all elements that might contain "disability" text
                    const disabilityElements = Array.from(document.querySelectorAll('*'))
                        .filter(el => (el.textContent || '').toLowerCase().includes('disability'));
                    
                    for (const element of disabilityElements) {
                        // Look for nearby select components
                        const nearby = element.parentElement ? 
                            element.parentElement.querySelectorAll('div[class*="select"], div[class*="Select"]') : [];
                        
                        if (nearby.length > 0) {
                            // Found a potential select - try to interact with it
                            const select = nearby[0];
                            
                            // Different approach: set data directly if possible
                            if (select.__reactProps$ || select._reactProps) {
                                // For React 17+
                                const props = select.__reactProps$ || select._reactProps;
                                if (props && props.onChange) {
                                    // Try to call onChange with a "No" value
                                    try {
                                        props.onChange({ value: 'no', label: 'No' });
                                        results.push({ approach: 'react-props', element: 'select', action: 'onChange' });
                                    } catch (e) {
                                        results.push({ approach: 'react-props', error: e.toString() });
                                    }
                                }
                            } else {
                                // Click approach
                                try {
                                    // Find clickable part
                                    const clickable = select.querySelector('div[class*="control"], div[class*="container"]');
                                    if (clickable) {
                                        clickable.click();
                                        results.push({ approach: 'click', element: 'clickable' });
                                        
                                        // Now look for "No" option
                                        setTimeout(() => {
                                            const options = document.querySelectorAll('div[class*="option"], div[class*="menu"] div');
                                            for (const option of options) {
                                                if ((option.textContent || '').toLowerCase().includes('no')) {
                                                    option.click();
                                                    results.push({ approach: 'option-click', value: option.textContent });
                                                    break;
                                                }
                                            }
                                        }, 100);
                                    }
                                } catch (e) {
                                    results.push({ approach: 'click', error: e.toString() });
                                }
                            }
                            
                            // Also try setting aria-selected attribute directly
                            try {
                                document.querySelectorAll('[role="option"]').forEach(option => {
                                    if ((option.textContent || '').toLowerCase().includes('no')) {
                                        option.setAttribute('aria-selected', 'true');
                                        results.push({ approach: 'aria-selected', value: option.textContent });
                                    }
                                });
                            } catch (e) {
                                results.push({ approach: 'aria-selected', error: e.toString() });
                            }
                        }
                    }
                    
                    return results;
                }
                """)
                
                if react_select_js_result and len(react_select_js_result) > 0:
                    print(f"✅ Direct React approach found and handled {len(react_select_js_result)} components:")
                    for result in react_select_js_result:
                        if 'error' in result:
                            print(f"  - {result.get('approach', 'unknown')}: {result.get('error', 'unknown error')}")
                        else:
                            print(f"  - {result.get('approach', 'unknown')}: {result.get('value', 'action performed')}")
                else:
                    print("⚠️ Direct React approach didn't find any components")
                    
                    # Last resort - just try to target specific structure used by Greenhouse
                    try:
                        # Look for any element with "disability" in text and has a control nearby
                        disability_elements = computer.page.locator("text=disability")
                        count = await disability_elements.count()
                        
                        if count > 0:
                            print(f"Found {count} elements with 'disability' text")
                            
                            for i in range(min(count, 5)):  # Check up to 5 elements
                                element = disability_elements.nth(i)
                                if await element.is_visible():
                                    # Try to find a nearby select control
                                    # Use JavaScript for more precise targeting
                                    js_result = await computer.page.evaluate("""
                                    (index) => {
                                        // Get all elements with "disability" text
                                        const elements = Array.from(document.querySelectorAll('*'))
                                            .filter(el => (el.textContent || '').toLowerCase().includes('disability'));
                                        
                                        if (elements.length <= index) return { error: 'Index out of bounds' };
                                        
                                        const element = elements[index];
                                        
                                        // Search up to 3 levels up for a select-like element
                                        let current = element;
                                        let depth = 0;
                                        const results = { actions: [] };
                                        
                                        while (current && depth < 3) {
                                            // Look for select-like elements
                                            const selects = current.querySelectorAll('select, div[class*="select"], div[class*="Select"]');
                                            
                                            if (selects.length > 0) {
                                                for (const select of selects) {
                                                    // Try different approaches
                                                    
                                                    // 1. Direct click on select
                                                    try {
                                                        select.click();
                                                        results.actions.push({ type: 'select-click', status: 'attempted' });
                                                    } catch (e) {
                                                        results.actions.push({ type: 'select-click', error: e.toString() });
                                                    }
                                                    
                                                    // 2. Find and click on control element
                                                    try {
                                                        const control = select.querySelector('div[class*="control"], div[class*="value"]');
                                                        if (control) {
                                                            control.click();
                                                            results.actions.push({ type: 'control-click', status: 'attempted' });
                                                        }
                                                    } catch (e) {
                                                        results.actions.push({ type: 'control-click', error: e.toString() });
                                                    }
                                                    
                                                    // 3. Set value directly if it's a standard select
                                                    if (select.tagName === 'SELECT') {
                                                        try {
                                                            // Find a "No" option
                                                            for (let i = 0; i < select.options.length; i++) {
                                                                if (select.options[i].text.toLowerCase().includes('no')) {
                                                                    select.selectedIndex = i;
                                                                    select.dispatchEvent(new Event('change', { bubbles: true }));
                                                                    results.actions.push({ type: 'select-value', status: 'success', value: select.options[i].text });
                                                                    break;
                                                                }
                                                            }
                                                        } catch (e) {
                                                            results.actions.push({ type: 'select-value', error: e.toString() });
                                                        }
                                                    }
                                                }
                                                
                                                // We've found and tried to interact with selects
                                                return results;
                                            }
                                            
                                            current = current.parentElement;
                                            depth++;
                                        }
                                        
                                        return { error: 'No select elements found' };
                                    }
                                    """, i)
                                    
                                    if js_result and 'actions' in js_result:
                                        print(f"✅ Last resort approach attempted {len(js_result['actions'])} actions:")
                                        for action in js_result['actions']:
                                            if 'error' in action:
                                                print(f"  - {action.get('type', 'unknown')}: {action.get('error', 'unknown error')}")
                                            else:
                                                print(f"  - {action.get('type', 'unknown')}: {action.get('status', 'unknown')} {action.get('value', '')}")
                                    elif js_result and 'error' in js_result:
                                        print(f"⚠️ Last resort error: {js_result['error']}")
                    except Exception as e:
                        print(f"⚠️ Error in last resort approach: {e}")
        except Exception as e:
            print(f"⚠️ Error during explicit disability status handling: {e}")
            
        # Try direct tab-based navigation for dropdowns as a last resort
        try:
            print("\nTrying tab-based navigation approach...")
            
            # First press tab to get to first field
            await computer.page.keyboard.press("Tab")
            
            # Press tab multiple times to navigate to select fields
            for i in range(10):  # Adjust this number based on form structure
                # Wait for any UI updates
                await asyncio.sleep(0.5)
                
                # Get active element info 
                active_element_info = await computer.page.evaluate("""
                () => {
                    const active = document.activeElement;
                    if (!active) return { type: 'none' };
                    
                    return {
                        type: active.tagName,
                        id: active.id,
                        classNames: active.className,
                        value: active.value,
                        text: active.textContent,
                        isSelect: active.tagName === 'SELECT',
                        isDiv: active.tagName === 'DIV',
                        hasSelectClass: (active.className || '').includes('select')
                    };
                }
                """)
                
                print(f"Tab #{i+1}: Active element: {active_element_info}")
                
                # If active element is a select or select-like element
                if active_element_info.get('isSelect') or active_element_info.get('hasSelectClass'):
                    print("Found a select element, trying to interact with it...")
                    
                    # Get surrounding text to identify which dropdown this is
                    surrounding_text = await computer.page.evaluate("""
                    () => {
                        const active = document.activeElement;
                        if (!active) return '';
                        
                        // Get nearby text to identify what this field is
                        let parent = active.parentElement;
                        let depth = 0;
                        let text = '';
                        
                        while (parent && depth < 3) {
                            text += ' ' + (parent.textContent || '');
                            parent = parent.parentElement;
                            depth++;
                        }
                        
                        return text.toLowerCase();
                    }
                    """)
                    
                    print(f"Surrounding text: {surrounding_text[:100]}...")
                    
                    # Check if this is one of our demographic fields
                    field_type = None
                    if "gender" in surrounding_text:
                        field_type = "Gender"
                        key_to_press = "m"  # For "Male"
                    elif "hispanic" in surrounding_text or "latino" in surrounding_text:
                        field_type = "Hispanic/Latino"
                        key_to_press = "n"  # For "No"
                    elif "race" in surrounding_text or "ethnicity" in surrounding_text:
                        field_type = "Race/Ethnicity"
                        key_to_press = "a"  # For "Asian"
                    elif "veteran" in surrounding_text:
                        field_type = "Veteran Status"
                        key_to_press = "i"  # For "I am not..."
                    elif "disability" in surrounding_text:
                        field_type = "Disability Status"
                        key_to_press = "n"  # For "No"
                    
                    if field_type:
                        print(f"Identified as {field_type} dropdown")
                        
                        # Try direct click on the element first
                        try:
                            # Use JavaScript to click since it's more reliable
                            await computer.page.evaluate("""
                            () => {
                                const active = document.activeElement;
                                if (active) {
                                    // Try to click on the element
                                    active.click();
                                    
                                    // Also try to click on parent containers that might be the actual select control
                                    let parent = active.parentElement;
                                    for (let i = 0; i < 3 && parent; i++) {
                                        if (parent.className && 
                                           (parent.className.includes('select') || 
                                            parent.className.includes('control') || 
                                            parent.className.includes('container'))) {
                                            parent.click();
                                        }
                                        parent = parent.parentElement;
                                    }
                                }
                            }
                            """)
                            print("Clicked on element using JavaScript")
                        except Exception as e:
                            print(f"⚠️ Error clicking with JavaScript: {e}")
                            
                        await asyncio.sleep(0.5)
                        
                        # Special handling for disability status - try multiple approaches
                        if field_type == "Disability Status":
                            print("Using special handling for Disability Status...")
                            
                            # Approach 1: Try to find and click "No" option directly
                            try:
                                # Use a more specific selector for "No" option
                                no_option = computer.page.locator('div[role="option"]:has-text("No"), div[class*="option"]:has-text("No")')
                                if await no_option.count() > 0:
                                    await no_option.first.click()
                                    print("✅ Clicked 'No' option for Disability Status")
                                else:
                                    print("⚠️ 'No' option not found for Disability Status")
                            except Exception as e:
                                print(f"⚠️ Error clicking 'No' option: {e}")
                            
                            # Approach 2: Try to use down arrow and enter
                            try:
                                # Press down arrow a few times to navigate to "No" option
                                for _ in range(2):  # Assuming "No" is the 2nd option
                                    await computer.page.keyboard.press("ArrowDown")
                                    await asyncio.sleep(0.3)
                                
                                # Press enter to select
                                await computer.page.keyboard.press("Enter")
                                print("✅ Used arrow keys for Disability Status")
                            except Exception as e:
                                print(f"⚠️ Error using arrow keys: {e}")
                            
                            # Approach 3: Try to use more direct JavaScript
                            try:
                                await computer.page.evaluate("""
                                () => {
                                    // Try multiple approaches to find and select "No" option
                                    
                                    // 1. Try to find a React select and manipulate it
                                    document.querySelectorAll('*').forEach(el => {
                                        // Look for elements that might be React select components
                                        if (el.className && el.className.includes && el.className.includes('select')) {
                                            // Look for nearby text to identify the disability field
                                            const nearbyText = el.textContent || '';
                                            if (nearbyText.toLowerCase().includes('disability')) {
                                                // Found a potential disability dropdown
                                                
                                                // Try to find the option elements
                                                const options = document.querySelectorAll('div[role="option"], div[class*="option"]');
                                                for (const option of options) {
                                                    if ((option.textContent || '').toLowerCase() === 'no') {
                                                        // Try to click it
                                                        option.click();
                                                        console.log('Clicked No option');
                                                        
                                                        // Also try to set selected state directly
                                                        if (option.setAttribute) {
                                                            option.setAttribute('aria-selected', 'true');
                                                            option.setAttribute('data-selected', 'true');
                                                        }
                                                        
                                                        // Try to dispatch events
                                                        const clickEvent = new MouseEvent('click', {
                                                            bubbles: true,
                                                            cancelable: true,
                                                            view: window
                                                        });
                                                        option.dispatchEvent(clickEvent);
                                                    }
                                                }
                                            }
                                        }
                                    });
                                    
                                    // 2. Try to find the specific input for disability status
                                    const disabilityInput = document.getElementById('disability_status');
                                    if (disabilityInput) {
                                        // Try to set value directly
                                        disabilityInput.value = 'No';
                                        
                                        // Fire events
                                        const changeEvent = new Event('change', { bubbles: true });
                                        disabilityInput.dispatchEvent(changeEvent);
                                        
                                        const inputEvent = new Event('input', { bubbles: true });
                                        disabilityInput.dispatchEvent(inputEvent);
                                    }
                                }
                                """)
                                print("✅ Used direct JavaScript for Disability Status")
                            except Exception as e:
                                print(f"⚠️ Error with direct JavaScript: {e}")
                        else:
                            # For other dropdowns, use the standard approach
                            # Press Enter to open the dropdown
                            await computer.page.keyboard.press("Enter")
                            await asyncio.sleep(0.5)
                            
                            # Type the first letter of the desired option
                            await computer.page.keyboard.press(key_to_press)
                            await asyncio.sleep(0.5)
                            
                            # Press Enter to select
                            await computer.page.keyboard.press("Enter")
                            print(f"✅ Tab-based interaction: Selected option for {field_type}")
                
                # Press Tab to move to next field
                await computer.page.keyboard.press("Tab")
                
                # Special handling for disability field
                if active_element_info.get('id') == 'disability_status':
                    print("Found disability_status by ID - using direct input method")
                    
                    # Try to set its value directly
                    try:
                        # Use element handle for direct property setting
                        element_handle = await computer.page.query_selector("#disability_status")
                        if element_handle:
                            # Try to set properties directly
                            await element_handle.evaluate("""
                            element => {
                                // Try multiple approaches
                                element.value = 'No';
                                
                                // Set custom properties that React might use
                                element._value = 'No';
                                element.defaultValue = 'No';
                                
                                // Trigger events
                                element.dispatchEvent(new Event('change', { bubbles: true }));
                                element.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                            """)
                            print("✅ Set disability_status value directly")
                    except Exception as e:
                        print(f"⚠️ Error setting disability_status value: {e}")
                    
                    # Also try clicking nearby elements to trigger the dropdown
                    try:
                        nearby_elements = await computer.page.evaluate("""
                        () => {
                            const input = document.getElementById('disability_status');
                            if (!input) return { error: 'Input not found' };
                            
                            // Click on parent containers
                            const containers = [];
                            let parent = input.parentElement;
                            for (let i = 0; i < 3 && parent; i++) {
                                containers.push({
                                    index: i,
                                    className: parent.className || 'no-class'
                                });
                                parent.click();
                                parent = parent.parentElement;
                            }
                            
                            return { clicked: containers };
                        }
                        """)
                        
                        if nearby_elements and 'clicked' in nearby_elements:
                            print(f"Clicked {len(nearby_elements['clicked'])} parent containers")
                    except Exception as e:
                        print(f"⚠️ Error clicking parent containers: {e}")
                    
                    # Wait a bit longer after finding the disability field
                    await asyncio.sleep(1.0)
        except Exception as e:
            print(f"⚠️ Error in tab-based navigation: {e}")
        
        # Special attempt for disability status at the very end
        try:
            print("\nFinal attempt for disability status with direct DOM targeting...")
            
            # First approach: target with ID and completely bypass the React component
            await computer.page.evaluate("""
            () => {
                // Find all elements containing disability status
                const disabilityElements = Array.from(document.querySelectorAll('*'))
                    .filter(el => el.id === 'disability_status' || 
                               (el.textContent && el.textContent.toLowerCase().includes('disability status')));
                
                console.log('Found ' + disabilityElements.length + ' disability-related elements');
                
                // Try multiple approaches in sequence
                const actions = [];
                
                // Target both the dropdown and the option list
                let dropdown = null;
                let optionsList = null;
                
                // Find option list nearby - it might be disconnected from the dropdown in the DOM
                for (const el of disabilityElements) {
                    // If this is the input element
                    if (el.id === 'disability_status') {
                        dropdown = el;
                        
                        // Look for select container
                        let selectContainer = el.closest('[class*="select"], [class*="Select"]');
                        if (selectContainer) {
                            actions.push({action: 'Found select container', class: selectContainer.className});
                            
                            // Try to click it to open options
                            try {
                                selectContainer.click();
                                actions.push({action: 'Clicked select container'});
                            } catch(e) {
                                actions.push({action: 'Error clicking container', error: e.toString()});
                            }
                        }
                    }
                    
                    // Check if this element has "No" as an option inside it
                    if (el.querySelectorAll) {
                        const noOptions = Array.from(el.querySelectorAll('*'))
                            .filter(opt => opt.textContent && 
                                   opt.textContent.trim() === 'No' && 
                                   !opt.closest('li, option'));
                        
                        if (noOptions.length > 0) {
                            optionsList = el;
                            actions.push({action: 'Found options list with No option', count: noOptions.length});
                        }
                    }
                }
                
                // Now search the whole document for dropdown items that might be "No"
                const menuItems = document.querySelectorAll('[class*="menu-item"], [class*="option"], [role="option"]');
                actions.push({action: 'Searching for menu items', count: menuItems.length});
                
                for (const item of menuItems) {
                    // Get the text directly from the item
                    const itemText = item.textContent.trim();
                    actions.push({action: 'Found menu item', text: itemText});
                    
                    // If this is a "No" option, click it
                    if (itemText === 'No') {
                        try {
                            item.click();
                            actions.push({action: 'Clicked No option'});
                            break;
                        } catch(e) {
                            actions.push({action: 'Error clicking No option', error: e.toString()});
                        }
                    }
                }
                
                // Extreme measures: directly manipulate the React state
                // This looks for any DOM element that might store the state
                document.querySelectorAll('[data-value]').forEach(el => {
                    if (el.getAttribute('data-value') === 'no' || 
                        el.getAttribute('data-value') === 'No') {
                        try {
                            el.click();
                            actions.push({action: 'Clicked element with data-value=no'});
                        } catch(e) {
                            actions.push({action: 'Error clicking data-value', error: e.toString()});
                        }
                    }
                });
                
                // Last resort: set hidden input values that might be controlling the selection
                document.querySelectorAll('input[type="hidden"][name*="disability"]').forEach(input => {
                    input.value = 'No';
                    input.dispatchEvent(new Event('change', {bubbles: true}));
                    actions.push({action: 'Set hidden input value', name: input.name});
                });
                
                return {actions, dropdownFound: !!dropdown, optionsListFound: !!optionsList};
            }
            """)
            
            # Second approach: use keyboard navigation specifically for the disability field
            print("Trying keyboard navigation approach...")
            
            # First locate the disability dropdown again
            disability_element = computer.page.locator('#disability_status, [aria-labelledby*="disability"]')
            
            if await disability_element.count() > 0:
                # Try direct click to open dropdown
                try:
                    await disability_element.click()
                    print("Clicked disability element")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Could not click directly: {e}")
                
                # Try using keyboard navigation
                # Tab to the element
                await computer.page.keyboard.press("Tab")
                await computer.page.keyboard.press("Tab")
                await computer.page.keyboard.press("Tab")
                
                # Press space to open dropdown
                await computer.page.keyboard.press("Space")
                await asyncio.sleep(0.5)
                
                # Press down arrow to navigate options
                await computer.page.keyboard.press("ArrowDown")
                await asyncio.sleep(0.2)
                await computer.page.keyboard.press("ArrowDown")
                await asyncio.sleep(0.2)
                
                # Press Enter to select the option
                await computer.page.keyboard.press("Enter")
                await asyncio.sleep(0.5)
                
                print("Completed keyboard navigation sequence for disability")
            
            # Third approach: xpath targeting of the dropdown and its components
            print("Trying XPath targeting approach...")
            
            try:
                # Look for a div containing 'Disability Status' text that's near a select element
                disability_containers = computer.page.locator("//div[contains(text(), 'Disability Status')]/following::div[contains(@class, 'select')]")
                if await disability_containers.count() > 0:
                    await disability_containers.first.click()
                    await asyncio.sleep(0.5)
                    
                    # Now look for the 'No' option
                    no_option = computer.page.locator("//div[text()='No'][contains(@class, 'option')]")
                    if await no_option.count() > 0:
                        await no_option.click()
                        print("Selected 'No' using XPath targeting")
                    else:
                        print("Could not find 'No' option with XPath")
                else:
                    print("Could not find disability container with XPath")
            except Exception as e:
                print(f"Error in XPath approach: {e}")
            
            # Fourth approach: click on specific elements in sequence to fully open the dropdown
            await computer.page.evaluate("""
            () => {
                // Target the specific Greenhouse React components
                const actions = [];
                
                // 1. First find the container
                const container = document.querySelector('#disability_status')?.closest('.select');
                if (!container) {
                    return {error: 'Could not find container'};
                }
                
                // 2. Click on all possible interactive parts in sequence
                const clickTargets = [
                    // The container itself
                    container,
                    // The control/value part
                    container.querySelector('.select__control, .select__value-container'),
                    // The input
                    container.querySelector('input'),
                    // The dropdown indicator
                    container.querySelector('.select__dropdown-indicator, .select__arrow')
                ];
                
                // Click each target
                for (const target of clickTargets) {
                    if (target) {
                        try {
                            target.click();
                            actions.push({clicked: target.className || target.tagName});
                        } catch(e) {
                            actions.push({error: e.toString()});
                        }
                    }
                }
                
                // 3. Wait a moment then look for 'No' option
                setTimeout(() => {
                    // Check for menu/option elements in the entire document
                    // (they might be in a portal outside the main container)
                    const options = document.querySelectorAll('.select__option, [role="option"]');
                    
                    for (const option of options) {
                        if (option.textContent.trim() === 'No') {
                            try {
                                option.click();
                                console.log('Clicked No option');
                            } catch(e) {
                                console.error('Error clicking option', e);
                            }
                            break;
                        }
                    }
                }, 100);
                
                return {actions};
            }
            """)
            
            print("✅ Made final comprehensive attempt on disability status field")
            
            # Take a screenshot after all attempts
            screenshot_base64 = await computer.screenshot()
            print("✅ Screenshot taken to verify form state")
            
            # Give it a moment to see if any of the attempts were successful
            await asyncio.sleep(1.0)
        except Exception as e:
            print(f"⚠️ Error in final disability status attempt: {e}")
        
        print("\n✅ Form filling completed. You can now review and submit the application manually.")
        
        # Final wait so user can see the results
        await computer.page.wait_for_timeout(10000)

if __name__ == "__main__":
    asyncio.run(main())
import google.generativeai as genai
import logging
import os
import asyncio
import json
import re
from typing import Tuple, Optional, Dict, Any
from dotenv import load_dotenv

# Configure logging for this module
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s') # Configured in main
logger = logging.getLogger("gemini_helper")

# --- Configuration ---
_API_KEY_LOADED = False
_GEMINI_MODEL = None
_CONFIG_CACHE = None  # Cache loaded config

def _load_config_if_needed():
    """Loads config.yaml if not already cached."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        try:
            from resume_loader import load_config  # Lazy import
            _CONFIG_CACHE = load_config()
        except Exception as e:
            logger.error(f"Failed to load config.yaml in gemini_helper: {e}")
            _CONFIG_CACHE = {}  # Set empty dict on failure
    return _CONFIG_CACHE

def _configure_gemini():
    """Loads API key and configures the Generative AI client."""
    global _API_KEY_LOADED, _GEMINI_MODEL
    if _API_KEY_LOADED:
        return True

    config = _load_config_if_needed()
    api_key = None

    # 1. Try loading from environment variable (highest priority)
    try:
        load_dotenv()  # Load environment variables from .env file if present
        api_key = os.getenv("GOOGLE_API_KEY")
        if api_key:
            logger.info("Loaded GOOGLE_API_KEY from environment/.env file.")
    except ImportError:
        logger.warning("Failed to import 'dotenv'. Cannot load .env file. pip install python-dotenv")
    except Exception as e:
        logger.warning(f"Error loading .env file: {e}")

    # 2. If not found in env, try loading from config.yaml (lower priority)
    # if not api_key:
    #     api_key = config.get("google_api_key")
    #     if api_key:
    #         logger.info("Loaded google_api_key from config.yaml.")
    # DEPRECATED: Recommend *only* using env var / .env for API keys. Don't store in config.yaml.
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in environment variables or .env file.")
        logger.error("Please create a .env file in the root directory with GOOGLE_API_KEY='YOUR_KEY' or set the environment variable.")
        return False

    try:
        genai.configure(api_key=api_key)
        # Use flash model by default (configurable later if needed)
        _GEMINI_MODEL = genai.GenerativeModel('gemini-1.5-flash')
        _API_KEY_LOADED = True
        logger.info("Google Generative AI configured successfully using gemini-1.5-flash.")
        return True
    except Exception as e:
        logger.error(f"Error configuring Google Generative AI: {e}")
        return False

# --- Core Gemini Interaction ---

async def get_gemini_response(prompt: str, retry_attempts: int = 2) -> Optional[str]:
    """
    Sends a prompt to the configured Gemini model and returns the text response.

    Args:
        prompt: The text prompt to send to the model.
        retry_attempts: Number of times to retry on failure.

    Returns:
        The text response from the model, or None if an error occurs
        or the response is blocked.
    """
    if not _API_KEY_LOADED:
        if not _configure_gemini():
            return None  # Configuration failed
    if not _GEMINI_MODEL:
        logger.error("Gemini model not initialized.")
        return None

    # Simple check for overly long prompts (adjust limit as needed for flash model)
    MAX_PROMPT_CHARS = 30000
    if len(prompt) > MAX_PROMPT_CHARS:
        logger.warning(f"Prompt length ({len(prompt)} chars) exceeds threshold ({MAX_PROMPT_CHARS}). Truncating.")
        prompt = prompt[:MAX_PROMPT_CHARS]

    logger.debug(f"Sending prompt to Gemini (first 500 chars):\n---PROMPT START---\n{prompt[:500]}...\n---PROMPT END---")

    current_attempt = 0
    while current_attempt <= retry_attempts:
        try:
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            ]

            response = await _GEMINI_MODEL.generate_content_async(
                prompt,
                safety_settings=safety_settings,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3  # Lower temperature for more deterministic/factual answers
                )
            )

            try:
                response_text = response.text
                logger.debug(f"Gemini raw response text: {response_text}")
                return response_text.strip()
            except ValueError:
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                    block_reason = response.prompt_feedback.block_reason
                    block_details = response.prompt_feedback.block_reason_message
                    logger.warning(f"Gemini response blocked. Reason: {block_reason}. Details: {block_details}")
                elif not getattr(response, 'parts', None):
                    logger.warning("Gemini response missing content parts and not explicitly blocked.")
                else:
                    try:
                        response_text = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                        if response_text:
                            logger.debug(f"Gemini raw response text (from parts): {response_text}")
                            return response_text.strip()
                        else:
                            logger.warning("Gemini response parts were empty.")
                    except Exception as part_e:
                        logger.warning(f"Could not extract text from Gemini response parts: {part_e}")

                return None

        except Exception as e:
            logger.error(f"Error calling Gemini API (Attempt {current_attempt + 1}/{retry_attempts + 1}): {e}")
            current_attempt += 1
            if current_attempt <= retry_attempts:
                await asyncio.sleep(1.5 ** current_attempt)
            else:
                logger.error("Max retry attempts reached for Gemini API call.")
                return None

    return None

# --- Specific Helper for Selectors (Revised) ---

async def get_selectors_from_gemini(html_snippet: str, task_description: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Asks Gemini to find CSS selectors based on HTML and a task.
    Prioritizes JSON output format.

    Args:
        html_snippet: A string containing the relevant HTML structure.
        task_description: A clear description of what selectors are needed.

    Returns:
        A tuple containing (list_selector, item_selector) or (None, None) if failed.
    """
    max_html_length = 8000
    if len(html_snippet) > max_html_length:
        logger.warning(f"HTML snippet length ({len(html_snippet)}) exceeds limit ({max_html_length}) for selector finding. Truncating.")
        html_snippet = html_snippet[:max_html_length]

    prompt = f"""
Analyze the following HTML snippet, which likely represents a custom dropdown, autocomplete, or similar interactive list component from a web form:

html
{html_snippet}

Task: {task_description}

Identify the most specific and reliable CSS selectors for the dynamically appearing list and its items.
Provide the answer ONLY in JSON format with two keys: "list_selector" and "item_selector".
- "list_selector": A CSS selector for the container element that holds the list of options/suggestions (e.g., the <ul> or the <div> that appears). It should be specific enough to target the correct dropdown list if multiple exist.
- "item_selector": A CSS selector for a single option/suggestion item *within* that list (e.g., the <li> or the clickable <div> representing one choice).

Example Response:

json
{{
  "list_selector": "div.react-select__menu-list[role='listbox']",
  "item_selector": "div.react-select__option[role='option']"
}}

If you cannot reliably determine one or both selectors from the provided HTML, return null for that specific value (e.g., {{"list_selector": ".menu", "item_selector": null}}). Be precise and avoid overly generic selectors like 'div' or 'li' unless absolutely necessary and combined with context. Focus on unique classes, IDs, or attributes if available. Respond ONLY with the JSON object.
"""
    try:
        response_text = await get_gemini_response(prompt)
        if not response_text:
            logger.warning("Received no response text from Gemini for selector request.")
            return None, None

        logger.debug(f"Gemini raw response for selectors: {response_text}")

        json_str = None
        # Try regex for markdown code block first
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL | re.IGNORECASE)
        if json_match:
            json_str = json_match.group(1)
        else:
            try:
                start_index = response_text.find('{')
                end_index = response_text.rfind('}')
                if start_index != -1 and end_index != -1 and end_index > start_index:
                    potential_json = response_text[start_index : end_index + 1]
                    # Validate if it's actually JSON before assigning
                    json.loads(potential_json)
                    json_str = potential_json
                else:
                    logger.warning("Could not find valid JSON object delimiters {} in Gemini response for selectors.")
            except json.JSONDecodeError:
                logger.warning("Text between {} was not valid JSON in Gemini selector response.")
            except Exception as e:
                logger.warning(f"Error attempting to extract raw JSON from Gemini selector response: {e}")

        if not json_str:
            logger.error("Could not extract valid JSON block from Gemini response for selectors.")
            return None, None

        try:
            data = json.loads(json_str)
            list_selector = data.get("list_selector")
            item_selector = data.get("item_selector")

            # Basic validation: ensure they are non-empty strings if not None
            if isinstance(list_selector, str) and not list_selector.strip():
                list_selector = None
            if isinstance(item_selector, str) and not item_selector.strip():
                item_selector = None

            if list_selector or item_selector:  # Return even if only one is found
                logger.info(f"Gemini suggested selectors - List: '{list_selector}', Item: '{item_selector}'")
                return list_selector, item_selector
            else:
                logger.warning("Gemini did not provide any valid selectors in the JSON response.")
                return None, None

        except json.JSONDecodeError as json_e:
            logger.error(f"Failed to decode extracted JSON response from Gemini: {json_e}\nJSON String: {json_str}")
            return None, None
        except Exception as e:
            logger.error(f"Error parsing Gemini JSON data for selectors: {e}")
            return None, None

    except Exception as e:
        logger.error(f"General error getting selectors from Gemini: {e}", exc_info=True)
        return None, None

# Example Usage (Optional - Can be run directly for testing)
async def _test_gemini():
    logging.basicConfig(level=logging.DEBUG)  # Use DEBUG for testing this module
    logger.info("Testing Gemini Helper...")
    if not _configure_gemini():
        return

    # Test selector finding (using dummy HTML)
    dummy_html = """
    <div class="location-selector css-123 stuff another-class">
        <label for="loc-input-id">Location</label>
        <div>
          <input type="text" id="loc-input-id" class="select-input" role="combobox" aria-expanded="true" aria-controls="loc-suggestions-xyz">
        </div>
        <div class="suggestions-wrapper css-abc" id="loc-suggestions-xyz" style="display: block;">
            <ul class="suggestion-list suggestion-list--active css-xyz" role="listbox">
                <li class="suggestion-item suggestion-item--first css-789" role="option" id="opt-1">San Jose, CA</li>
                <li class="suggestion-item css-789" role="option" id="opt-2">Seattle, WA</li>
                <li class="suggestion-item suggestion-item--last css-789" role="option" id="opt-3">New York, NY</li>
            </ul>
        </div>
    </div>
    """
    task_desc = "Find CSS selectors for the suggestion list container (ul) and a single suggestion item (li) inside it."
    print("\nTesting Selector Finding...")
    list_sel, item_sel = await get_selectors_from_gemini(dummy_html, task_desc)
    print(f"Test Selectors Result:\nList: {list_sel}\nItem: {item_sel}\n")

if __name__ == "__main__":
    asyncio.run(_test_gemini())

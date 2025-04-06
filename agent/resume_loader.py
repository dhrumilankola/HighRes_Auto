import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("resume_loader")

def load_config() -> Dict[str, Any]:
    """Loads the YAML configuration."""
    import yaml # Import here to avoid making it a top-level dependency if not used elsewhere
    config_path = os.path.abspath("./config.yaml")
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found at {config_path}")
        raise FileNotFoundError(f"config.yaml not found at {config_path}")
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Configuration loaded from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Error loading config file {config_path}: {e}")
        raise

def load_resume_data(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Loads resume data from a JSON file specified in the config or default path.

    Args:
        config (Optional): Loaded configuration dictionary. If None, it attempts to load it.

    Returns:
        Dict[str, Any]: The loaded resume data.

    Raises:
        FileNotFoundError: If the config or resume JSON file is not found.
        ValueError: If the resume JSON file is invalid.
    """
    if config is None:
        config = load_config()

    resume_dir = config.get('paths', {}).get('resume_dir', './resume_data')
    resume_filename = config.get('paths', {}).get('resume_json', 'resume_data.json')
    resume_path = os.path.abspath(os.path.join(resume_dir, resume_filename))

    if not os.path.exists(resume_path):
        logger.error(f"Resume data file not found: {resume_path}")
        raise FileNotFoundError(f"Resume data file not found: {resume_path}")

    try:
        with open(resume_path, 'r') as f:
            resume_data = json.load(f)
        logger.info(f"Resume data loaded successfully from {resume_path}")
        # Basic validation (presence of key sections)
        required_keys = ["personal_info", "education", "work_experience"]
        if not all(key in resume_data for key in required_keys):
             logger.warning(f"Resume data might be missing key sections: {required_keys}")
        # Ensure education and work_experience are lists, even if empty
        if not isinstance(resume_data.get("education"), list):
            logger.warning("Resume 'education' section is not a list. Converting to empty list.")
            resume_data["education"] = []
        if not isinstance(resume_data.get("work_experience"), list):
            logger.warning("Resume 'work_experience' section is not a list. Converting to empty list.")
            resume_data["work_experience"] = []

        return resume_data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in resume file {resume_path}: {e}")
        raise ValueError(f"Invalid JSON in resume file: {e}")
    except Exception as e:
        logger.error(f"Error reading resume file {resume_path}: {e}")
        raise

def get_resume_pdf_path(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Gets the absolute path to the resume PDF file from config."""
    if config is None:
        config = load_config()

    resume_dir = config.get('paths', {}).get('resume_dir', './resume_data')
    resume_filename = config.get('paths', {}).get('resume_pdf', 'resume_data.pdf')
    resume_pdf_path = os.path.abspath(os.path.join(resume_dir, resume_filename))

    if not os.path.exists(resume_pdf_path):
        logger.warning(f"Resume PDF not found at: {resume_pdf_path}")
        logger.warning("Upload functionality will not work without the PDF file.")
        return None
    return resume_pdf_path

# Example usage (optional)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        cfg = load_config()
        resume = load_resume_data(cfg)
        pdf_path = get_resume_pdf_path(cfg)
        print("Config loaded.")
        # print("Resume data:", json.dumps(resume, indent=2))
        print(f"Resume PDF path: {pdf_path}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
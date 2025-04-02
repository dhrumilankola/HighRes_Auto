#!/usr/bin/env python3
"""
greenhouse.py

Purpose: Scrape tech job listings from Greenhouse ATS and classify them using a Gemma3 model via Ollama.
Focuses on tech roles (software engineering, data science, etc.) posted within the last 2 days,
with 0-3 years of experience, and located in the US or remote.
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
import pandas as pd
from dateutil.parser import parse as parse_date
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import random
import re
from bs4 import BeautifulSoup

# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("job_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('greenhouse_jobs')

# ------------------------------------------------------------------------------
# Global Session and Configuration
# ------------------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; GreenhouseJobScraper/1.0)",
    "Accept": "application/json",
    "Referer": "https://boards.greenhouse.io/"
})

MAX_RETRIES = 3
INITIAL_BACKOFF = 1  # seconds
JOB_PAGE_CACHE = {}

# ------------------------------------------------------------------------------
# Ollama Configuration (Environment Driven)
# ------------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "gemma3:12b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", 60))

# ------------------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------------------
def retry_request(method: str, url: str, **kwargs) -> Optional[requests.Response]:
    """Retry HTTP requests with exponential backoff."""
    backoff = INITIAL_BACKOFF
    for attempt in range(MAX_RETRIES):
        try:
            time.sleep(random.uniform(0.1, 0.5))
            response = SESSION.request(method, url, **kwargs)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', backoff))
                logger.warning(f"Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            elif response.status_code >= 500:
                logger.warning(f"Server error {response.status_code}. Retrying in {backoff}s...")
                time.sleep(backoff)
                backoff *= 2
                continue
            return response
        except requests.RequestException as e:
            logger.error(f"Request failed: {e}. Retrying in {backoff}s...")
            time.sleep(backoff)
            backoff *= 2
    logger.error(f"Max retries reached for {url}")
    return None

def fetch_job_page_text(job_url: str) -> str:
    """Fetch and cache full job page text."""
    if job_url in JOB_PAGE_CACHE:
        return JOB_PAGE_CACHE[job_url]
    response = retry_request("GET", job_url, timeout=10)
    if response and response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup(["script", "style"]):
            script.extract()
        content = soup.find('div', {'class': 'content'}) or soup
        text = content.get_text(separator=" ", strip=True)
        text = re.sub(r'\s+', ' ', text)
        JOB_PAGE_CACHE[job_url] = text
        return text
    logger.warning(f"Failed to fetch job page: {job_url}")
    return ""

# ------------------------------------------------------------------------------
# Ollama Server and Model Health Check
# ------------------------------------------------------------------------------
def check_ollama_model_ready() -> bool:
    """
    Check that the Ollama server is reachable and that the specified model is available.
    For local servers, we attempt to fetch tags or models.
    """
    try:
        # This endpoint may vary—consult the latest Ollama API docs if needed.
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        response.raise_for_status()
        models = response.json().get("models", [])
        available = any(m.get("name") == MODEL_NAME for m in models)
        if not available:
            logger.error(f"Model '{MODEL_NAME}' not found on the Ollama server. Please run:\n  ollama pull {MODEL_NAME}")
        return available
    except requests.RequestException as e:
        logger.error(f"Could not connect to Ollama server: {e}")
        return False

# ------------------------------------------------------------------------------
# LLM Integration with Ollama
# ------------------------------------------------------------------------------
def classify_job_with_llm(title: str, description: str, max_tokens: int = 300) -> dict:
    """
    Classify a job posting using the Gemma3 model via Ollama.
    Returns a dict with 'is_tech_role' (bool) and 'experience_years' (float or None).
    """
    # Truncate description to control prompt length.
    truncated_desc = description[:max_tokens]
    prompt = f"""
    Analyze this job posting:
    Job Title: {title}
    Job Description: {truncated_desc}
    
    Determine:
    1. Is it a tech role (software engineering, data science, machine learning, etc.)? (yes/no)
    2. Required experience in years (0 if not specified, null if unclear)
    
    Return only the JSON: {{"is_tech_role": bool, "experience_years": float or null}}
    """.strip()
    
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "options": {
            "temperature": 0.3,
            "top_p": 0.9
        },
        "stream": False
    }
    
    try:
        response = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT)
        response.raise_for_status()
        result = response.json().get("response", "")
        # Extract JSON from the generated text using regex
        match = re.search(r'\{.*\}', result, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            logger.error(f"No JSON found in LLM response:\n{result}")
            return {"is_tech_role": False, "experience_years": None}
    except requests.RequestException as e:
        logger.error(f"Failed to connect to Ollama server: {e}")
        return {"is_tech_role": False, "experience_years": None}
    except json.JSONDecodeError:
        logger.error(f"Failed to parse JSON from LLM response: {result}")
        return {"is_tech_role": False, "experience_years": None}

# ------------------------------------------------------------------------------
# Data Loading and Fetching
# ------------------------------------------------------------------------------
def load_company_tokens(filename: str) -> List[Dict[str, str]]:
    """Load company board tokens from CSV."""
    df = pd.read_csv(filename)
    companies = [{"name": row['company_name'], "token": row['board_token']} for _, row in df.iterrows()]
    logger.info(f"Loaded {len(companies)} companies from {filename}")
    return companies

def fetch_company_jobs(company: Dict[str, str]) -> List[Dict[str, Any]]:
    """Fetch jobs from a company's Greenhouse board."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{company['token']}/jobs"
    response = retry_request("GET", url, params={"content": "true"}, timeout=10)
    if response and response.status_code == 200:
        jobs = response.json().get("jobs", [])
        for job in jobs:
            job["company_name"] = company["name"]
            job["board_token"] = company["token"]
        logger.info(f"Fetched {len(jobs)} jobs for {company['name']}")
        return jobs
    logger.error(f"Failed to fetch jobs for {company['name']}: {response.status_code if response else 'No response'}")
    return []

def fetch_all_companies_jobs(companies: List[Dict[str, str]], max_workers: int = 8) -> List[Dict[str, Any]]:
    """Fetch jobs from all companies concurrently."""
    all_jobs = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_company_jobs, c): c for c in companies}
        for future in as_completed(futures):
            try:
                all_jobs.extend(future.result())
            except Exception as e:
                logger.error(f"Error fetching jobs for {futures[future]['name']}: {e}")
    logger.info(f"Total jobs fetched: {len(all_jobs)}")
    return all_jobs

# ------------------------------------------------------------------------------
# Job Filtering
# ------------------------------------------------------------------------------
def is_recent_job(job: Dict[str, Any], days: int = 2) -> bool:
    """Check if job was posted within the last `days`."""
    date_str = job.get("updated_at")
    if not date_str:
        return False
    job_date = parse_date(date_str)
    cutoff = datetime.now(job_date.tzinfo) - timedelta(days=days)
    return job_date >= cutoff

def is_valid_location(job: Dict[str, Any], us_only: bool = False, remote_only: bool = False) -> bool:
    """Check if job location matches criteria."""
    loc = job.get('location', {}).get('name', 'Remote/Unknown').lower()
    is_remote = any(x in loc for x in ['remote', 'wfh', 'virtual', 'anywhere'])
    is_us = any(x in loc for x in ['united states', 'usa', 'u.s.', 'new york', 'california'])
    if remote_only:
        return is_remote
    elif us_only:
        return is_us
    return is_remote or is_us

def filter_tech_jobs(jobs: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filter jobs using LLM and other criteria."""
    filtered = []
    for job in jobs:
        title = job.get('title', '')
        description = job.get('content', '') or fetch_job_page_text(job.get('absolute_url', ''))
        
        # LLM classification via Ollama
        llm_result = classify_job_with_llm(title, description)
        if not llm_result.get('is_tech_role', False):
            continue
        exp_years = llm_result.get('experience_years')
        if exp_years is not None and exp_years > config['max_years']:
            continue
        
        # Additional filters
        if not (is_recent_job(job, config['days']) and 
                is_valid_location(job, config['us_only'], config['remote_only'])):
            continue
        
        filtered.append({
            'id': job.get('id'),
            'title': title,
            'company': job.get('company_name'),
            'location': job.get('location', {}).get('name', 'Remote/Unknown'),
            'posted_at': job.get('updated_at'),
            'job_url': job.get('absolute_url', ''),
            'apply_url': f"https://boards.greenhouse.io/{job['board_token']}/jobs/{job['id']}"
        })
    logger.info(f"Filtered to {len(filtered)} jobs")
    return filtered

# ------------------------------------------------------------------------------
# Data Export
# ------------------------------------------------------------------------------
def save_jobs_to_file(jobs: List[Dict[str, Any]], output: str) -> None:
    """Save jobs to JSON and CSV."""
    with open(f"{output}.json", 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2)
    pd.DataFrame(jobs).to_csv(f"{output}.csv", index=False)
    logger.info(f"Saved {len(jobs)} jobs to {output}.json and {output}.csv")

# ------------------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='Greenhouse Job Scraper with Ollama and Gemma')
    parser.add_argument('--company-file', type=str, required=True, help='CSV with company tokens')
    parser.add_argument('--days', type=int, default=2, help='Days to consider recent')
    parser.add_argument('--output', type=str, default='tech_jobs', help='Output file prefix')
    parser.add_argument('--max-years', type=float, default=3.0, help='Max experience years')
    parser.add_argument('--us-only', action='store_true', help='US jobs only')
    parser.add_argument('--remote-only', action='store_true', help='Remote jobs only')
    args = parser.parse_args()

    config = {
        'days': args.days,
        'max_years': args.max_years,
        'us_only': args.us_only,
        'remote_only': args.remote_only
    }

    # Check that the Ollama server is reachable and the model is loaded.
    if not check_ollama_model_ready():
        logger.error("Ollama server or model not available. Please ensure the server is running and the model is pulled (e.g., `ollama pull {MODEL_NAME}`). Exiting.")
        return

    companies = load_company_tokens(args.company_file)
    all_jobs = fetch_all_companies_jobs(companies)
    tech_jobs = filter_tech_jobs(all_jobs, config)
    save_jobs_to_file(tech_jobs, args.output)

    print(f"Found {len(tech_jobs)} tech jobs:")
    for job in tech_jobs[:5]:
        print(f"- {job['title']} | {job['company']} | {job['location']}")
    if len(tech_jobs) > 5:
        print(f"... and {len(tech_jobs) - 5} more")

if __name__ == "__main__":
    main()

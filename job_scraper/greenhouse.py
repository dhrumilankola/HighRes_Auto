#!/usr/bin/env python3
"""
enhanced_greenhouse.py

An improved version of the Greenhouse job scraper that addresses several issues identified in the analysis:
1. More accurate experience detection
2. Better job role categorization
3. Duplicate job detection and handling
4. Enhanced content analysis
5. Expanded tech stack detection
6. Smart location filtering
7. Performance improvements
"""

import os
import time
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
import requests
import pandas as pd
from dateutil.parser import parse as parse_date
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import random
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass, field, asdict

# ------------------------------------------------------------------------------
# Logging Configuration with Rotation
# ------------------------------------------------------------------------------
from logging.handlers import RotatingFileHandler

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = "job_scraper.log"
file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
file_handler.setFormatter(log_formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

logger = logging.getLogger('greenhouse_jobs')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

# ------------------------------------------------------------------------------
# Global Session and Retry Configuration
# ------------------------------------------------------------------------------
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; GreenhouseJobScraper/1.0; +https://example.com/)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://boards.greenhouse.io/"
})

MAX_RETRIES = 3
INITIAL_BACKOFF = 1  # seconds

# Cache for job page content to avoid re-fetching
JOB_PAGE_CACHE = {}

# ------------------------------------------------------------------------------
# Job Data Structure
# ------------------------------------------------------------------------------
@dataclass
class JobListing:
    """Structured data class for job listings with validation"""
    id: str
    title: str
    company: str
    company_token: str
    location: str = "Unknown"
    department: str = ""
    posted_at: str = ""
    job_url: str = ""
    apply_url: str = ""
    content_snippet: str = ""
    content_full: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    experience_years: Optional[float] = None
    experience_required: bool = False
    is_remote: bool = False
    is_us_based: bool = False
    tech_stack: List[str] = field(default_factory=list)
    role_category: str = "other"
    job_hash: str = ""
    
    def __post_init__(self):
        """Calculate a job hash based on title and content for de-duplication"""
        key_data = f"{self.title}|{self.company}|{self.content_snippet[:100]}"
        self.job_hash = hashlib.md5(key_data.encode('utf-8')).hexdigest()
        
        # Categorize job role
        self._categorize_role()
        
        # Detect location type
        self._detect_location_type()
    
    def _categorize_role(self):
        """Categorize the job role based on title"""
        title_lower = self.title.lower()
        
        if any(term in title_lower for term in ['data scientist', 'data analyst', 'data engineer']):
            self.role_category = 'data'
        elif any(term in title_lower for term in ['fullstack', 'full stack', 'full-stack']):
            self.role_category = 'fullstack'
        elif any(term in title_lower for term in ['frontend', 'front end', 'front-end']):
            self.role_category = 'frontend'
        elif any(term in title_lower for term in ['backend', 'back end', 'back-end']):
            self.role_category = 'backend'
        elif any(term in title_lower for term in ['mobile', 'ios', 'android']):
            self.role_category = 'mobile'
        elif any(term in title_lower for term in ['ml', 'machine learning', 'ai', 'artificial intelligence']):
            self.role_category = 'ml_ai'
        elif any(term in title_lower for term in ['devops', 'site reliability', 'platform']):
            self.role_category = 'devops'
        elif any(term in title_lower for term in ['software engineer', 'software developer']):
            self.role_category = 'software_engineer'
        elif any(term in title_lower for term in ['qa', 'test', 'quality']):
            self.role_category = 'qa_test'
        else:
            self.role_category = 'other'
    
    def _detect_location_type(self):
        """Determine if job is remote or US-based with improved filtering"""
        if not self.location:
            return
            
        location_lower = self.location.lower()
        
        # Check for non-US countries explicitly to exclude them
        non_us_countries = [
            'india', 'canada', 'united kingdom', 'australia', 'germany', 
            'france', 'spain', 'italy', 'japan', 'china', 'brazil', 'mexico',
            'singapore', 'netherlands', 'sweden', 'ireland', 'poland', 
            'romania', 'bulgaria', 'ukraine', 'russia', 'israel'
        ]
        
        # Check if any non-US country is in the location
        is_non_us_location = any(country in location_lower for country in non_us_countries)
        
        # Check for locations like "Remote-Spain" which are international remote
        if 'remote-' in location_lower or 'remote -' in location_lower or 'remote,' in location_lower:
            parts = re.split(r'remote[\s-,]+', location_lower)
            if len(parts) > 1 and any(country in parts[1] for country in non_us_countries):
                is_non_us_location = True
                
        # Only mark as US-based if it's explicitly US
        self.is_us_based = False
        
        # Define clear US markers
        us_indicators = [
            'united states', 'usa', 'us', 'u.s.', 'u.s.a', 'america',
            'san francisco', 'new york', 'chicago', 'seattle', 'boston',
            'austin', 'denver', 'atlanta', 'los angeles', 'portland'
        ]
        
        # US state codes with context (to avoid false positives)
        us_state_patterns = [
            r'\b(ca|ny|wa|ma|il|tx|co|ga|fl|pa)\b',  # State codes as whole words
            r'([,\s])(al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy)([,\s]|$)'  # State with delimiters
        ]
        
        # Check for US indicators
        if any(indicator in location_lower for indicator in us_indicators):
            self.is_us_based = True
        
        # Check for state codes with context
        elif any(re.search(pattern, location_lower) for pattern in us_state_patterns):
            self.is_us_based = True
        
        # If it's explicitly non-US, override the US flag
        if is_non_us_location:
            self.is_us_based = False
        
        # Determine remote status - only count as remote if US-based or explicitly Remote US
        self.is_remote = False
        remote_indicators = ['remote', 'work from home', 'wfh', 'virtual', 'anywhere']
        
        if any(term in location_lower for term in remote_indicators):
            # Only count as remote if US-based or explicitly Remote US
            if self.is_us_based or 'remote us' in location_lower or 'remote-us' in location_lower or 'remote united states' in location_lower:
                self.is_remote = True
                self.is_us_based = True  # If it's Remote US, it's definitely US-based
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)

# ------------------------------------------------------------------------------
# Enhanced Retry Logic with Rate Limiting
# ------------------------------------------------------------------------------
def retry_request(method, url, **kwargs):
    """
    Enhanced retry with better rate limiting.
    """
    retries = 0
    backoff = INITIAL_BACKOFF
    
    while retries < MAX_RETRIES:
        try:
            # Add a small random delay to avoid hitting rate limits
            time.sleep(random.uniform(0.1, 0.5))
            
            response = SESSION.request(method, url, **kwargs)
            
            # Check for rate limiting response codes
            if response.status_code == 429:
                # Extract retry-after header if available
                retry_after = int(response.headers.get('Retry-After', backoff))
                logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                retries += 1
                continue
                
            # Check for server errors
            elif response.status_code in (500, 502, 503, 504):
                logger.warning(f"Server error {response.status_code}. Retrying in {backoff}s")
                time.sleep(backoff)
                retries += 1
                backoff *= 2
                continue
                
            return response
            
        except requests.RequestException as e:
            logger.error(f"Request exception for {url}: {str(e)}. Retrying...")
            time.sleep(backoff)
            retries += 1
            backoff *= 2
            
    logger.error(f"Max retries reached for {url}")
    return None

# ------------------------------------------------------------------------------
# Utility: Fetch Full Job Page Text with Improved Content Extraction
# ------------------------------------------------------------------------------
def fetch_job_page_text(job_url: str) -> str:
    """
    Fetch the full text of a job posting page with improved content extraction.
    
    Args:
        job_url: URL of the job posting
        
    Returns:
        str: Text content of the job page.
    """
    if job_url in JOB_PAGE_CACHE:
        return JOB_PAGE_CACHE[job_url]
        
    try:
        response = retry_request("GET", job_url, timeout=15)
        if response and response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove script and style elements that don't contain useful content
            for script in soup(["script", "style"]):
                script.extract()
                
            # Try to find the job content container
            job_container = soup.find('div', {'id': re.compile(r'(job-?content|description|content)', re.I)}) or \
                           soup.find('div', {'class': re.compile(r'(job-?content|description|content)', re.I)}) or \
                           soup.find('section', {'id': re.compile(r'(job-?content|description|content)', re.I)}) or \
                           soup.find('section', {'class': re.compile(r'(job-?content|description|content)', re.I)}) or \
                           soup
            
            # Process lists with proper spacing to ensure we catch bullet points
            for ul in job_container.find_all(['ul', 'ol']):
                for li in ul.find_all('li'):
                    li.insert_before(soup.new_string(' • '))
                    li.append(soup.new_string('. '))
                    
            # Get the text with proper spacing
            text = job_container.get_text(separator=" ", strip=True)
            
            # Clean up double spaces
            text = re.sub(r'\s+', ' ', text)
            
            JOB_PAGE_CACHE[job_url] = text
            return text
        else:
            logger.warning(f"Failed to fetch job page from {job_url}")
            return ""
    except Exception as e:
        logger.error(f"Error fetching job page {job_url}: {str(e)}")
        return ""

# ------------------------------------------------------------------------------
# Company Board Tokens
# ------------------------------------------------------------------------------
def load_company_tokens(filename: str) -> List[Dict[str, str]]:
    """
    Load company board tokens from a specified CSV file.
    
    Args:
        filename: Path to the CSV file with company tokens
        
    Returns:
        List[Dict[str, str]]: List of company dictionaries with name and token.
    """
    companies = []
    try:
        df = pd.read_csv(filename)
        for _, row in df.iterrows():
            companies.append({
                "name": row['company_name'],
                "token": row['board_token']
            })
        logger.info(f"Loaded {len(companies)} companies from {filename}")
        return companies
    except Exception as e:
        logger.error(f"Error loading company tokens from {filename}: {str(e)}")
        raise

# ------------------------------------------------------------------------------
# Job Board API Functions
# ------------------------------------------------------------------------------
def fetch_company_jobs(company: Dict[str, str], include_content: bool = True) -> List[Dict[str, Any]]:
    """
    Fetch all published jobs for a specific company using their board token.
    
    Args:
        company: Company dictionary with name and token.
        include_content: Whether to include full job description.
        
    Returns:
        List[Dict[str, Any]]: List of job dictionaries.
    """
    company_name = company["name"]
    board_token = company["token"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    params = {"content": "true"} if include_content else {}
    
    response = retry_request("GET", url, params=params, timeout=15)
    if response and response.status_code == 200:
        try:
            data = response.json()
            jobs = data.get("jobs", [])
            logger.info(f"Found {len(jobs)} jobs for {company_name} (token: {board_token})")
            for job in jobs:
                job["company_name"] = company_name
                job["board_token"] = board_token
            return jobs
        except Exception as e:
            logger.error(f"Error parsing JSON for {company_name}: {str(e)}")
            return []
    else:
        if response:
            logger.error(f"Error fetching jobs for {company_name}: {response.status_code}")
            logger.error(f"Response: {response.text}")
        return []

def get_job_details(company: Dict[str, str], job_id: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific job.
    
    Args:
        company: Company dictionary with name and token.
        job_id: The ID of the job.
        
    Returns:
        Optional[Dict[str, Any]]: Job details or None if not found.
    """
    board_token = company["token"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
    params = {"questions": "true"}
    
    response = retry_request("GET", url, params=params, timeout=15)
    if response and response.status_code == 200:
        try:
            job_details = response.json()
            job_details["company_name"] = company["name"]
            job_details["board_token"] = board_token
            return job_details
        except Exception as e:
            logger.error(f"Error parsing job details for job {job_id}: {str(e)}")
            return None
    else:
        if response:
            logger.error(f"Error fetching job details: {response.status_code}")
            logger.error(f"Response: {response.text}")
        return None

def fetch_all_companies_jobs(companies: List[Dict[str, str]], max_workers: int = 8) -> List[Dict[str, Any]]:
    """
    Fetch jobs from all provided companies concurrently.
    
    Args:
        companies: List of company dictionaries with name and token.
        max_workers: Maximum number of concurrent workers.
        
    Returns:
        List[Dict[str, Any]]: Combined list of jobs with company information.
    """
    all_jobs = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_company = {executor.submit(fetch_company_jobs, company): company for company in companies}
        completed = 0
        for future in as_completed(future_to_company):
            company = future_to_company[future]
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
                completed += 1
                logger.info(f"Progress: {completed}/{len(companies)} companies processed")
            except Exception as e:
                logger.error(f"Error fetching jobs for {company['name']}: {str(e)}")
            time.sleep(0.2)  # Small delay between companies
    logger.info(f"Fetched a total of {len(all_jobs)} jobs from {len(companies)} companies")
    return all_jobs

# ------------------------------------------------------------------------------
# Job Filtering
# ------------------------------------------------------------------------------
def is_recent_job(job: Dict[str, Any], days: int = 2) -> bool:
    """
    Check if a job was posted within the specified number of days.
    
    Args:
        job: Job dictionary.
        days: Number of days to consider as recent.
        
    Returns:
        bool: True if the job is recent, False otherwise.
    """
    date_str = job.get("updated_at")
    if not date_str:
        return False
    try:
        job_date = parse_date(date_str)
        cutoff_date = datetime.now(job_date.tzinfo) - timedelta(days=days)
        return job_date >= cutoff_date
    except Exception as e:
        logger.warning(f"Date parsing error for job {job.get('id')}: {str(e)}")
        return True  # When in doubt, include it

def detect_experience_requirements(text: str, max_years: float = 3.0) -> Tuple[bool, Optional[float]]:
    """
    Detect experience requirements in text.
    
    Args:
        text: Text to analyze
        max_years: Maximum years of experience to consider as entry-level
        
    Returns:
        Tuple of (exceeds_max, detected_years)
    """
    if not text:
        return False, None
        
    text = text.lower()
    
    # Define a comprehensive set of patterns to match experience requirements
    patterns = [
        # The "X+" patterns - explicit pattern for minimum years
        (r'(\d+\.?\d*)\+\s*years?(?:\s+of)?\s+(?:\w+\s+)*experience', lambda m: float(m.group(1))),
        
        # Range patterns
        (r'(\d+\.?\d*)\s*-\s*(\d+\.?\d*)\s*years?(?:\s+of)?\s+(?:\w+\s+)*experience', 
         lambda m: float(m.group(2))),  # Upper bound for ranges
        (r'(\d+\.?\d*)\s*to\s*(\d+\.?\d*)\s*years?(?:\s+of)?\s+(?:\w+\s+)*experience', 
         lambda m: float(m.group(2))),  # Upper bound for ranges
         
        # Single value patterns
        (r'(\d+\.?\d*)\s*years?(?:\s+of)?\s+(?:\w+\s+)*experience', 
         lambda m: float(m.group(1))),
        (r'minimum\s+(?:of\s+)?(\d+\.?\d*)\s*years?', 
         lambda m: float(m.group(1))),
        (r'at\s+least\s+(\d+\.?\d*)\s*years?', 
         lambda m: float(m.group(1))),
        (r'(\d+\.?\d*)\s*years?(?:\s+or\s+more)(?:\s+of)?\s+(?:\w+\s+)*experience', 
         lambda m: float(m.group(1))),
        (r'requires\s+(\d+\.?\d*)\s*years?', 
         lambda m: float(m.group(1))),
         
        # Bullet point experience requirements
        (r'[•\*-]\s*(\d+\.?\d*)\+?\s*years?(?:\s+of)?\s+(?:\w+\s+)*experience', 
         lambda m: float(m.group(1))),
         
        # Patterns with "experience" at the beginning
        (r'experience:?\s*(\d+\.?\d*)\+?\s*years?', 
         lambda m: float(m.group(1))),
        (r'experience\s+of\s+(\d+\.?\d*)\+?\s*years?', 
         lambda m: float(m.group(1))),
    ]
    
    # Additional patterns for "no experience required"
    no_exp_patterns = [
        r'no\s+(?:prior\s+|previous\s+)?experience\s+(?:necessary|required|needed)',
        r'experience\s+(?:not|isn[\'’]t)\s+(?:necessary|required|needed)',
        r'(?:0|zero)\s+years?\s+(?:of\s+)?experience',
        r'entry[\s-]?level',
        r'\bjunior\b',
        r'no\s+experience\s+required'
    ]
    
    # Check if "no experience required" is explicitly mentioned
    for pattern in no_exp_patterns:
        if re.search(pattern, text):
            return False, 0
    
    # Check for experience requirements
    highest_years = None
    
    for pattern, extractor in patterns:
        for match in re.finditer(pattern, text):
            try:
                years = extractor(match)
                if highest_years is None or years > highest_years:
                    highest_years = years
            except (ValueError, IndexError):
                continue
    
    # Return whether the experience exceeds max and the detected years
    if highest_years is not None:
        return highest_years > max_years, highest_years
        
    return False, None

def is_entry_level(job: Dict[str, Any], max_years: float = 3.0) -> Tuple[bool, Optional[float]]:
    """
    Check if a job is entry-level (0-3 years experience) or if no experience is mentioned.
    
    Args:
        job: Job dictionary.
        max_years: Maximum years of experience to consider as entry-level.
        
    Returns:
        Tuple of (is_entry_level, detected_years)
    """
    # Negative keywords in the job title
    negative_keywords = {
        'senior', 'staff', 'lead', 'director', 'principal', 'manager', 
        'architect', 'consultant', 'vp', 'head', 'chief', 'sr.'
    }
    
    title = job.get('title', '').lower()
    
    # Check for negative keywords in title (as whole words)
    if any(re.search(r'\b' + re.escape(neg) + r'\b', title) for neg in negative_keywords):
        return False, None
    
    # Positive keywords that indicate entry-level
    positive_keywords = {
        'entry', 'junior', 'associate', 'entry-level', 'entry level', 
        'new grad', 'new graduate', 'recent graduate', 'early career', 
        'university grad', 'campus', 'graduate', 'intern', 'internship',
        'l1', 'level 1', 'level i', 'level one', 'tier 1', 'tier i',
        'sde i', 'sde 1', 'se i', 'se 1', 
        'software engineer i', 'software engineer 1',
        'junior developer', 'associate developer',
        'fresh', 'fresher', 'trainee', 'apprentice'
    }
    
    # Check for positive keywords in title
    if any(re.search(r'\b' + re.escape(pos) + r'\b', title) for pos in positive_keywords):
        return True, 0
    
    # Check the API content
    content = job.get('content', '').lower() if job.get('content') else ''
    exceeds_max, years = detect_experience_requirements(content, max_years)
    
    if exceeds_max:
        return False, years
    
    # Then check the full job page
    job_url = job.get('absolute_url', '')
    if job_url:
        full_text = fetch_job_page_text(job_url).lower()
        exceeds_max, years = detect_experience_requirements(full_text, max_years)
        
        if exceeds_max:
            return False, years
    
    # If we didn't find any disqualifying experience requirements
    return True, years

def extract_tech_stack(text: str) -> List[str]:
    """
    Extract tech stack keywords from job description text.
    
    Args:
        text: Job description text
        
    Returns:
        List[str]: List of detected technologies
    """
    if not text:
        return []
        
    tech_keywords = {
        # Programming languages
        'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'golang', 'ruby', 
        'php', 'swift', 'kotlin', 'scala', 'rust', 'r', 'matlab', 'perl', 'shell', 'bash',
        
        # Web frameworks
        'react', 'angular', 'vue', 'node', 'express', 'django', 'flask', 'spring', 'rails',
        'laravel', 'symfony', 'asp.net', 'fastapi', 'next.js', 'gatsby', 'svelte',
        
        # Databases
        'sql', 'nosql', 'mongodb', 'postgresql', 'mysql', 'oracle', 'redis', 'cassandra',
        'dynamodb', 'couchdb', 'firebase', 'neo4j', 'elasticsearch', 'sqlite',
        
        # Cloud providers & DevOps
        'aws', 'azure', 'gcp', 'kubernetes', 'docker', 'terraform', 'jenkins', 'gitlab',
        'github actions', 'circleci', 'ansible', 'chef', 'puppet', 'prometheus', 'grafana',
        
        # Data science & ML
        'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy', 'scipy',
        'hadoop', 'spark', 'kafka', 'airflow', 'tableau', 'power bi', 'dbt', 'looker',
        
        # Mobile
        'ios', 'android', 'react native', 'flutter', 'xamarin', 'swift', 'objective-c',
        
        # Other
        'graphql', 'rest', 'soap', 'microservices', 'serverless', 'etl', 'ci/cd'
    }
    
    text_lower = text.lower()
    found_tech = set()
    
    for tech in tech_keywords:
        if re.search(r'\b' + re.escape(tech) + r'\b', text_lower):
            found_tech.add(tech)
    
    return sorted(list(found_tech))

def extract_salary_range(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract salary range information from job text.
    
    Args:
        text: Job description text
        
    Returns:
        Tuple of (min_salary, max_salary) in USD
    """
    if not text:
        return None, None
        
    # Common salary patterns
    salary_patterns = [
        # USD patterns with comma formatting
        r'\$(\d{2,3}(?:,\d{3})+)\s*-\s*\$(\d{2,3}(?:,\d{3})+)',
        r'\$(\d{2,3}(?:,\d{3})+)\s*to\s*\$(\d{2,3}(?:,\d{3})+)',
        r'(\d{2,3}(?:,\d{3})+)\s*-\s*(\d{2,3}(?:,\d{3})+)\s*USD',
        r'salary range:?\s*\$?(\d{2,3}(?:,\d{3})+)\s*-\s*\$?(\d{2,3}(?:,\d{3})+)',
        
        # USD patterns without commas
        r'\$(\d{4,6})\s*-\s*\$(\d{4,6})',
        r'\$(\d{4,6})\s*to\s*\$(\d{4,6})',
        
        # K notation
        r'\$(\d{2,3})k\s*-\s*\$(\d{2,3})k',
        r'(\d{2,3})k\s*-\s*(\d{2,3})k',
        r'(\d{2,3})-(\d{2,3})k'
    ]
    
    text_lower = text.lower()
    
    for pattern in salary_patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                min_salary = match.group(1).replace(',', '')
                max_salary = match.group(2).replace(',', '')
                
                # Handle K notation
                if 'k' in min_salary.lower() or 'k' in max_salary.lower():
                    min_salary = float(min_salary.lower().replace('k', '')) * 1000
                    max_salary = float(max_salary.lower().replace('k', '')) * 1000
                
                return int(float(min_salary)), int(float(max_salary))
            except (ValueError, IndexError):
                continue
    
    return None, None

def is_duplicate_job(job: JobListing, existing_jobs: List[JobListing]) -> bool:
    """
    Check if a job is a duplicate of an existing job.
    
    Args:
        job: The job to check.
        existing_jobs: List of existing jobs.
        
    Returns:
        bool: True if the job is a duplicate, False otherwise.
    """
    for existing_job in existing_jobs:
        # Check by hash
        if job.job_hash == existing_job.job_hash:
            return True
            
        # Check by title and company
        if (job.title == existing_job.title and 
            job.company == existing_job.company):
            return True
    
    return False

def create_job_listing(raw_job: Dict[str, Any], config: Dict[str, Any]) -> Optional[JobListing]:
    """
    Create a structured JobListing object from a raw job dictionary.
    
    Args:
        raw_job: Raw job dictionary.
        config: Configuration dictionary.
        
    Returns:
        Optional[JobListing]: JobListing object or None if not valid.
    """
    # Get basic job data
    job_id = raw_job.get('id')
    title = raw_job.get('title', '')
    company = raw_job.get('company_name', '')
    company_token = raw_job.get('board_token', '')
    
    # Skip jobs with missing essential data
    if not job_id or not title or not company:
        logger.warning(f"Skipping job with missing essential data: {job_id}")
        return None
    
    # Check if we have a location, otherwise set to Unknown
    location_obj = raw_job.get('location')
    if isinstance(location_obj, dict) and location_obj.get('name'):
        location = location_obj.get('name')
    else:
        location = "Unknown"
    
    # Get department
    departments = raw_job.get('departments', [])
    department = departments[0].get('name', '') if departments else ''
    
    # Get content and posted date
    content = raw_job.get('content', '')
    posted_at = raw_job.get('updated_at', '')
    
    # Get URLs
    job_url = raw_job.get('absolute_url', '')
    apply_url = f"https://boards.greenhouse.io/{company_token}/jobs/{job_id}" if company_token else ''
    
    # Create content snippet
    content_snippet = content[:500] + '...' if content and len(content) > 500 else content
    
    # Fetch full content from job page if needed
    content_full = ""
    if job_url and config.get('fetch_full_content', False):
        content_full = fetch_job_page_text(job_url)
    
    # Extract tech stack
    tech_stack = []
    if config.get('extract_tech_stack', True):
        tech_stack = extract_tech_stack(content or content_full)
    
    # Extract salary range
    salary_min, salary_max = None, None
    if config.get('extract_salary', True):
        salary_min, salary_max = extract_salary_range(content or content_full)
    
    # Check experience requirements
    is_entry, experience_years = is_entry_level(raw_job, config.get('max_years', 3.0))
    
    # Skip if not entry level and we're filtering for entry level
    if config.get('entry_level_only', True) and not is_entry:
        logger.debug(f"Skipping non-entry level job: {title} ({company})")
        return None
    
    # Create a JobListing object
    job_listing = JobListing(
        id=str(job_id),
        title=title,
        company=company,
        company_token=company_token,
        location=location,
        department=department,
        posted_at=posted_at,
        job_url=job_url,
        apply_url=apply_url,
        content_snippet=content_snippet,
        content_full=content_full,
        salary_min=salary_min,
        salary_max=salary_max,
        experience_years=experience_years,
        experience_required=experience_years is not None,
        tech_stack=tech_stack
    )
    
    return job_listing

def filter_tech_jobs(all_jobs: List[Dict[str, Any]], config: Dict[str, Any]) -> List[JobListing]:
    """
    Filter jobs to only include tech-related positions that match criteria and
    transform to structured JobListing objects.
    
    Filters applied:
    - Must be a tech-related role based on title or department
    - Must be posted within the last X days
    - Must not require more than max_years of experience
    - Must be US-based (if us_only is True)
    - Must be remote US-based (if remote_only is True)
    - Must match specific tech stack (if specific_tech is provided)
    
    Args:
        all_jobs: List of all job dictionaries.
        config: Dictionary with filtering configuration.
        
    Returns:
        List[JobListing]: Filtered list of JobListing objects.
    """
    # Enhanced tech title keywords - multi-word included
    TECH_TITLE_KEYWORDS = {
        # Core engineering roles
        'software engineer', 'software developer', 'swe', 'sde', 
        'full-stack', 'fullstack', 'full stack', 
        'backend', 'back-end', 'back end',
        'frontend', 'front-end', 'front end',
        
        # Specialized roles
        'data engineer', 'data analyst', 'data scientist',
        'machine learning', 'ml engineer', 'ai engineer',
        'devops', 'cloud engineer', 'site reliability',
        'systems engineer', 'platform engineer',
        
        # Tech stack specific titles
        'python developer', 'python engineer',
        'java developer', 'java engineer',
        'javascript developer', 'js developer',
        'react developer', 'react engineer',
        'node developer', 'node engineer',
        'angular developer', 'vue developer',
        'php developer', 'laravel developer',
        'ios developer', 'android developer', 'mobile developer',
        'api engineer', 'api developer',
        'application engineer', 'web developer',
        'qa engineer', 'test engineer', 'automation engineer',
        'infrastructure engineer', 'networking engineer',
        'computer vision', 'nlp engineer', 'robotics engineer',
        'embedded engineer', 'firmware engineer', 'hardware engineer',
    }
    
    TECH_DEPARTMENT_KEYWORDS = {
        'engineering', 'software', 'technology', 'development', 'product', 
        'data', 'tech', 'research', 'r&d', 'information technology', 'it',
        'ai research', 'infrastructure', 'devops', 'machine learning',
        'artificial intelligence'
    }
    
    filtered_jobs = []
    excluded_jobs = []
    processed_ids = set()  # To track duplicates by ID
    
    # Display progress for long operations
    total_jobs = len(all_jobs)
    processed = 0
    
    for job in all_jobs:
        processed += 1
        if processed % 100 == 0:
            logger.info(f"Processed {processed}/{total_jobs} jobs...")
        
        job_id = job.get('id')
        
        # Skip duplicates by ID (if already processed)
        if job_id in processed_ids:
            continue
        
        processed_ids.add(job_id)
        
        # Check if it's a tech role
        title = job.get('title', '').lower() if job.get('title') else ''
        departments = job.get('departments', [])
        dept = departments[0].get('name', '').lower() if departments else ''
        
        # Excluded departments - even if title sounds technical
        EXCLUDED_DEPARTMENTS = {
            'sales', 'sales development', 'business development', 'marketing',
            'customer success', 'account management', 'recruitment', 'hr',
            'human resources', 'finance', 'legal', 'administration'
        }
        
        # Excluded title patterns - even if in a technical department
        EXCLUDED_TITLE_PATTERNS = {
            'pre-sales', 'pre sales', 'sales engineer', 'solutions engineer',
            'sales representative', 'business development', 'account manager',
            'account executive', 'recruiter', 'talent', 'customer success',
            'marketing specialist', 'marketing manager'
        }
        
        # Skip if in an excluded department
        if not config.get('include_sales_roles', False) and any(excluded_dept == dept for excluded_dept in EXCLUDED_DEPARTMENTS):
            exclusion_reason = f"Non-tech department: {dept}"
            if config.get('save_excluded_jobs', False):
                excluded_jobs.append({
                    'id': job_id,
                    'title': job.get('title', ''),
                    'company': job.get('company_name', ''),
                    'department': dept,
                    'reason': exclusion_reason
                })
            continue
            
        # Skip if title matches excluded patterns
        if not config.get('include_sales_roles', False) and any(excluded_pattern in title for excluded_pattern in EXCLUDED_TITLE_PATTERNS):
            exclusion_reason = f"Non-tech role pattern in title: {job.get('title', '')}"
            if config.get('save_excluded_jobs', False):
                excluded_jobs.append({
                    'id': job_id,
                    'title': job.get('title', ''),
                    'company': job.get('company_name', ''),
                    'department': dept,
                    'reason': exclusion_reason
                })
            continue
        
        # Enhanced tech role detection - check for keywords more carefully
        is_tech_role = False
        for keyword in TECH_TITLE_KEYWORDS:
            if keyword in title:
                is_tech_role = True
                break
                
        if not is_tech_role:
            for keyword in TECH_DEPARTMENT_KEYWORDS:
                if dept and keyword in dept:
                    is_tech_role = True
                    break
        
        # Skip if not a tech role
        if not is_tech_role:
            exclusion_reason = "Not a tech role"
            if config.get('save_excluded_jobs', False):
                excluded_jobs.append({
                    'id': job_id,
                    'title': job.get('title', ''),
                    'company': job.get('company_name', ''),
                    'reason': exclusion_reason
                })
            continue
        
        # Check if recent (skip old jobs)
        if not is_recent_job(job, config.get('days', 2)):
            exclusion_reason = f"Not posted within last {config.get('days', 2)} days"
            if config.get('save_excluded_jobs', False):
                excluded_jobs.append({
                    'id': job_id,
                    'title': job.get('title', ''),
                    'company': job.get('company_name', ''),
                    'reason': exclusion_reason
                })
            continue
        
        # Create a structured JobListing
        try:
            job_listing = create_job_listing(job, config)
            
            # Skip if the job was filtered out during creation
            if not job_listing:
                continue
            
            # Check for specific tech requirements if provided
            if config.get('specific_tech'):
                if not any(tech in job_listing.tech_stack for tech in config['specific_tech']):
                    exclusion_reason = f"Doesn't match required tech stack: {config['specific_tech']}"
                    if config.get('save_excluded_jobs', False):
                        excluded_jobs.append({
                            'id': job_id,
                            'title': job.get('title', ''),
                            'company': job.get('company_name', ''),
                            'reason': exclusion_reason
                        })
                    continue
            
            # Skip based on location preferences
            # Always enforce US-based jobs
            if not job_listing.is_us_based:
                exclusion_reason = "Not US-based"
                if config.get('save_excluded_jobs', False):
                    excluded_jobs.append({
                        'id': job_id,
                        'title': job.get('title', ''),
                        'company': job.get('company_name', ''),
                        'location': job_listing.location,
                        'reason': exclusion_reason
                    })
                logger.debug(f"Skipping non-US job: {job_listing.title} at {job_listing.location}")
                continue
                
            # Skip if remote-only option is set but job isn't remote
            if config.get('remote_only', False) and not job_listing.is_remote:
                exclusion_reason = "Not a remote job"
                if config.get('save_excluded_jobs', False):
                    excluded_jobs.append({
                        'id': job_id,
                        'title': job.get('title', ''),
                        'company': job.get('company_name', ''),
                        'location': job_listing.location,
                        'reason': exclusion_reason
                    })
                logger.debug(f"Skipping non-remote job: {job_listing.title} at {job_listing.location}")
                continue
            
            # Check for duplicates with fuzzy matching
            if config.get('remove_duplicates', True) and is_duplicate_job(job_listing, filtered_jobs):
                logger.debug(f"Skipping duplicate job: {job_listing.title} ({job_listing.company})")
                continue
                
            # If we got here, add the job to our filtered list
            filtered_jobs.append(job_listing)
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {str(e)}")
            continue
    
    logger.info(f"Filtered to {len(filtered_jobs)} recent tech jobs")
    
    # Save excluded jobs if requested
    if config.get('save_excluded_jobs', False) and excluded_jobs:
        try:
            excluded_filename = f"{config.get('output', 'tech_jobs')}_excluded.json"
            with open(excluded_filename, 'w', encoding='utf-8') as f:
                json.dump(excluded_jobs, f, indent=2)
            logger.info(f"Saved {len(excluded_jobs)} excluded jobs to {excluded_filename}")
        except Exception as e:
            logger.error(f"Error saving excluded jobs: {str(e)}")
    
    return filtered_jobs

# ------------------------------------------------------------------------------
# Data Export
# ------------------------------------------------------------------------------
def save_jobs_to_file(jobs: List[JobListing], output_prefix: str) -> None:
    """
    Save jobs to CSV, JSON, and Excel files.
    
    Args:
        jobs: List of JobListing objects.
        output_prefix: Prefix for output filenames.
    """
    try:
        # Convert to dictionaries for JSON serialization
        job_dicts = [job.to_dict() for job in jobs]
        
        json_filename = f"{output_prefix}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(job_dicts, f, indent=2)
        logger.info(f"Successfully saved {len(jobs)} jobs to {json_filename}")
        
        csv_filename = f"{output_prefix}.csv"
        df = pd.DataFrame(job_dicts)
        df.to_csv(csv_filename, index=False)
        logger.info(f"Successfully saved {len(jobs)} jobs to {csv_filename}")
        
        excel_filename = f"{output_prefix}.xlsx"
        df.to_excel(excel_filename, index=False, sheet_name='Tech Jobs')
        logger.info(f"Successfully saved {len(jobs)} jobs to {excel_filename}")
    except Exception as e:
        logger.error(f"Error saving jobs to file: {str(e)}")

def generate_job_report(jobs: List[JobListing], output_prefix: str, config: Dict) -> None:
    """
    Generate a detailed report about the jobs.

    Args:
        jobs: List of JobListing objects.
        output_prefix: Prefix for output filenames.
        config: Dictionary containing filter options like max_years, remote_only, etc.
    """
    try:
        # Company distribution
        company_counts = {}
        for job in jobs:
            company_counts[job.company] = company_counts.get(job.company, 0) + 1

        # Role category distribution
        role_counts = {}
        for job in jobs:
            role_counts[job.role_category] = role_counts.get(job.role_category, 0) + 1

        # Location distribution
        location_counts = {'remote': 0, 'us': 0, 'other': 0}
        for job in jobs:
            if job.is_remote:
                location_counts['remote'] += 1
            elif job.is_us_based:
                location_counts['us'] += 1
            else:
                location_counts['other'] += 1

        # Tech stack distribution
        tech_counts = {}
        for job in jobs:
            for tech in job.tech_stack:
                tech_counts[tech] = tech_counts.get(tech, 0) + 1

        # Experience requirement distribution
        exp_counts = {'required': 0, 'not_specified': 0}
        exp_distribution = {'0': 0, '1': 0, '2': 0, '3': 0}
        for job in jobs:
            if job.experience_required:
                exp_counts['required'] += 1
                if job.experience_years is not None:
                    year_bucket = min(3, max(0, int(job.experience_years)))
                    exp_distribution[str(year_bucket)] += 1
            else:
                exp_counts['not_specified'] += 1

        # Salary distribution
        salary_ranges = []
        for job in jobs:
            if job.salary_min and job.salary_max:
                salary_ranges.append((job.salary_min, job.salary_max))

        avg_min = sum(min_sal for min_sal, _ in salary_ranges) / len(salary_ranges) if salary_ranges else 0
        avg_max = sum(max_sal for _, max_sal in salary_ranges) / len(salary_ranges) if salary_ranges else 0

        # Generate the report
        report_str = "# Job Analysis Report\n\n"
        report_str += f"Analysis of {len(jobs)} tech jobs\n\n"
        report_str += "## Search Criteria\n"
        report_str += f"- Experience limit: {config.get('max_years', 3.0)} years\n"
        report_str += f"- Posted within: {config.get('days', 2)} days\n"
        report_str += f"- Location: {'US only' if config.get('us_only', True) else 'International'}\n"
        report_str += f"- Work type: {'Remote only' if config.get('remote_only', False) else 'Remote and on-site'}\n"
        report_str += f"- Include sales roles: {'Yes' if config.get('include_sales_roles', False) else 'No'}\n"
        if config.get('specific_tech'):
            report_str += f"- Required tech: {', '.join(config.get('specific_tech'))}\n"
        report_str += "\n"

        report_str += "## Company Distribution\n"
        for company, count in sorted(company_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
            report_str += f"- {company}: {count} jobs ({count/len(jobs)*100:.1f}%)\n"

        report_str += "\n## Role Category Distribution\n"
        for role, count in sorted(role_counts.items(), key=lambda x: x[1], reverse=True):
            report_str += f"- {role.replace('_', ' ')}: {count} jobs ({count/len(jobs)*100:.1f}%)\n"

        report_str += "\n## Location Distribution\n"
        for loc, count in location_counts.items():
            report_str += f"- {loc}: {count} jobs ({count/len(jobs)*100:.1f}%)\n"

        report_str += "\n## Top 20 Tech Skills\n"
        for tech, count in sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:20]:
            report_str += f"- {tech}: {count} jobs ({count/len(jobs)*100:.1f}%)\n"

        report_str += "\n## Experience Requirements\n"
        for category, count in exp_counts.items():
            report_str += f"- {category}: {count} jobs ({count/len(jobs)*100:.1f}%)\n"

        report_str += "\n### Experience Distribution\n"
        for years, count in sorted(exp_distribution.items()):
            report_str += f"- {years} year(s): {count} jobs\n"

        if salary_ranges:
            report_str += "\n## Salary Information\n"
            report_str += f"- Jobs with salary info: {len(salary_ranges)} ({len(salary_ranges)/len(jobs)*100:.1f}%)\n"
            report_str += f"- Average salary range: ${avg_min:.0f} - ${avg_max:.0f}\n"

        # Save the report
        report_filename = f"{output_prefix}_report.md"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(report_str)

        logger.info(f"Successfully generated job report: {report_filename}")

    except Exception as e:
        logger.error(f"Error generating job report: {str(e)}")

# ------------------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='Enhanced Greenhouse Job Scraper')
    parser.add_argument('--company-file', type=str, required=True,
                        help='Path to the company CSV file with board tokens')
    parser.add_argument('--days', type=int, default=2,
                        help='Number of days to consider jobs as recent')
    parser.add_argument('--output', type=str, default='tech_jobs',
                        help='Output file prefix (e.g., "tech_jobs")')
    parser.add_argument('--experience-limit', type=float, default=3.0,
                        help='Maximum years of experience to include (default: 3.0)')
    parser.add_argument('--remote-only', action='store_true',
                        help='Only include remote jobs (US-based remote only)')
    parser.add_argument('--max-workers', type=int, default=8,
                        help='Maximum number of concurrent workers')
    parser.add_argument('--include-tech', type=str, default='',
                        help='Only include jobs with specific tech stack (comma-separated)')
    parser.add_argument('--fetch-full-content', action='store_true',
                        help='Fetch and process full job description pages')
    parser.add_argument('--extract-salary', action='store_true',
                        help='Extract salary information')
    parser.add_argument('--remove-duplicates', action='store_true',
                        help='Remove duplicate job listings')
    parser.add_argument('--save-excluded-jobs', action='store_true',
                        help='Save details of excluded jobs for debugging')
    parser.add_argument('--generate-report', action='store_true',
                        help='Generate a detailed report of job statistics')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug logging')
    parser.add_argument('--allow-international', action='store_true',
                        help='Allow international jobs (default: US only)')
    parser.add_argument('--include-sales-roles', action='store_true',
                        help='Include sales engineering and solutions engineering roles')
    args = parser.parse_args()
    
    # Set debug level if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)
    
    # Process additional args
    specific_tech = [tech.strip().lower() for tech in args.include_tech.split(',') if tech.strip()]
    
    # Create config dict for filtering
    config = {
        'days': args.days,
        'max_years': args.experience_limit,
        'us_only': not args.allow_international,  # Default to US only unless --allow-international is specified
        'remote_only': args.remote_only,
        'specific_tech': specific_tech if specific_tech else None,
        'fetch_full_content': args.fetch_full_content,
        'extract_salary': args.extract_salary,
        'remove_duplicates': args.remove_duplicates,
        'save_excluded_jobs': args.save_excluded_jobs,
        'entry_level_only': True,
        'extract_tech_stack': True,
        'output': args.output,
        'include_sales_roles': args.include_sales_roles,
    }
    
    start_time = time.time()
    
    try:
        # Load company tokens
        companies = load_company_tokens(args.company_file)
        print(f"Processing jobs from {len(companies)} companies")
        
        # Fetch all jobs
        all_jobs = fetch_all_companies_jobs(companies, max_workers=args.max_workers)
        print(f"Fetched {len(all_jobs)} total jobs")
        
        # Filter tech jobs
        filtered_jobs = filter_tech_jobs(all_jobs, config)
        print(f"Filtered to {len(filtered_jobs)} relevant tech jobs")
        
        # Save jobs to files
        save_jobs_to_file(filtered_jobs, args.output)
        
        # Generate report if requested
        if args.generate_report:
            generate_job_report(filtered_jobs, args.output)
        
        # Print job summary
        print(f"\nFound {len(filtered_jobs)} relevant positions posted in the last {args.days} days:")
        
        # Group by company
        jobs_by_company = {}
        for job in filtered_jobs:
            jobs_by_company.setdefault(job.company, []).append(job)
        
        # Display top companies
        for company, jobs in sorted(jobs_by_company.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            print(f"\n{company} ({len(jobs)} jobs):")
            for i, job in enumerate(jobs[:5], 1):
                print(f"  {i}. {job.title} | {job.location}")
            if len(jobs) > 5:
                print(f"  ... and {len(jobs) - 5} more jobs")
        
        # Show tech stack distribution
        tech_counts = {}
        for job in filtered_jobs:
            for tech in job.tech_stack:
                tech_counts[tech] = tech_counts.get(tech, 0) + 1
        
        print("\nTop 10 technologies in demand:")
        for tech, count in sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  - {tech}: {count} jobs")
        
        # Print command example
        print(f"\nCommand to reproduce this search:")
        cmd = f"python enhanced_greenhouse.py --company-file {args.company_file} --days {args.days} --experience-limit {args.experience_limit} --output {args.output}"
        
        if args.remote_only:
            cmd += " --remote-only"
        if args.allow_international:
            cmd += " --allow-international"
        if args.include_sales_roles:
            cmd += " --include-sales-roles"
        if args.fetch_full_content:
            cmd += " --fetch-full-content"
        if args.extract_salary:
            cmd += " --extract-salary"
        if args.remove_duplicates:
            cmd += " --remove-duplicates"
        if args.save_excluded_jobs:
            cmd += " --save-excluded-jobs"
        if args.generate_report:
            cmd += " --generate-report"
        if args.debug:
            cmd += " --debug"
        if args.include_tech:
            cmd += f" --include-tech \"{args.include_tech}\""
            
        print(cmd)
        
        execution_time = time.time() - start_time
        print(f"\nExecution completed in {execution_time:.2f} seconds")
        print(f"Job details saved to {args.output}.json, {args.output}.csv, and {args.output}.xlsx")
        
    except Exception as e:
        logger.error(f"An error occurred in main: {str(e)}")
        raise

if __name__ == "__main__":
    main()
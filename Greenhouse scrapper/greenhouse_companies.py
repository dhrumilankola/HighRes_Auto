# #!/usr/bin/env python3
# """
# greenhouse_companies.py

# Sole purpose: Discover board tokens of all companies using Greenhouse ATS.
# This script continuously scrapes company board tokens from across the web,
# saving them in batches of 100.
# """

# import re
# import time
# import json
# import os
# import logging
# import random
# import pandas as pd
# import requests
# from datetime import datetime
# from bs4 import BeautifulSoup
# from typing import List, Dict, Any, Set, Optional
# from urllib.parse import urlparse

# # Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler("company_scraper.log"),
#         logging.StreamHandler()
#     ]
# )
# logger = logging.getLogger('greenhouse_companies')

# # Headers to mimic a browser
# USER_AGENTS = [
#     'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
#     'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
#     'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
#     'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
#     'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
# ]

# def get_random_headers():
#     """Get random headers to avoid detection"""
#     return {
#         'User-Agent': random.choice(USER_AGENTS),
#         'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
#         'Accept-Language': 'en-US,en;q=0.5',
#         'Connection': 'keep-alive',
#         'Upgrade-Insecure-Requests': '1',
#         'Cache-Control': 'max-age=0',
#     }

# # ------------------------------------------------------------------------------
# # File Management
# # ------------------------------------------------------------------------------

# def load_discovered_tokens() -> Set[str]:
#     """
#     Load all previously discovered tokens from existing output files
    
#     Returns:
#         Set[str]: Set of already discovered board tokens
#     """
#     known_tokens = set()
    
#     if not os.path.exists('output'):
#         os.makedirs('output')
#         return known_tokens
    
#     for filename in os.listdir('output'):
#         if filename.startswith('greenhouse_companies_batch_') and filename.endswith('.csv'):
#             try:
#                 df = pd.read_csv(os.path.join('output', filename))
#                 if 'board_token' in df.columns:
#                     tokens = set(df['board_token'].tolist())
#                     known_tokens.update(tokens)
#                     logger.info(f"Loaded {len(tokens)} tokens from {filename}")
#             except Exception as e:
#                 logger.error(f"Error loading file {filename}: {str(e)}")
    
#     logger.info(f"Loaded a total of {len(known_tokens)} previously discovered tokens")
#     return known_tokens

# def save_companies_batch(companies: List[Dict[str, Any]], batch_num: int) -> None:
#     """
#     Save a batch of companies to CSV and JSON files
    
#     Args:
#         companies: List of company dictionaries
#         batch_num: Batch number for the filename
#     """
#     if not companies:
#         logger.info("No companies to save in this batch")
#         return
    
#     if not os.path.exists('output'):
#         os.makedirs('output')
    
#     try:
#         # Save as CSV
#         csv_filename = f"output/greenhouse_companies_batch_{batch_num:03d}.csv"
#         df = pd.DataFrame(companies)
#         df = df.sort_values('company_name')
#         df.to_csv(csv_filename, index=False)
        
#         # Save as JSON
#         json_filename = f"output/greenhouse_companies_batch_{batch_num:03d}.json"
#         with open(json_filename, 'w', encoding='utf-8') as f:
#             json.dump(companies, f, indent=2)
        
#         logger.info(f"Successfully saved {len(companies)} companies to batch {batch_num:03d}")
#     except Exception as e:
#         logger.error(f"Error saving companies batch {batch_num}: {str(e)}")

# # ------------------------------------------------------------------------------
# # Token Discovery Functions
# # ------------------------------------------------------------------------------

# def extract_greenhouse_tokens_from_html(html_content: str) -> Set[str]:
#     """
#     Extract Greenhouse board tokens from HTML content.
    
#     Args:
#         html_content: HTML content to search
        
#     Returns:
#         Set[str]: Set of unique board tokens found
#     """
#     patterns = [
#         r'boards\.greenhouse\.io\/([a-zA-Z0-9_-]+)',            # Direct board URL
#         r'boards-api\.greenhouse\.io\/v1\/boards\/([a-zA-Z0-9_-]+)', # API URL
#         r'greenhouse\.io\/boards\/([a-zA-Z0-9_-]+)',             # Alternate URL format
#         r'"boardToken":\s*"([a-zA-Z0-9_-]+)"',                   # JSON config
#         r'data-board-token="([a-zA-Z0-9_-]+)"',                  # HTML attribute
#         r'greenhouse\.io/embed/job_board/\?for=([a-zA-Z0-9_-]+)',  # Embed URL
#         r'gh_src=([a-zA-Z0-9_-]+)'                               # Source parameter
#     ]
    
#     tokens = set()
    
#     for pattern in patterns:
#         matches = re.findall(pattern, html_content)
#         tokens.update(matches)
    
#     false_positives = {'api', 'v1', 'boards', 'www', 'jobs', 'job', 'careers', 'career', 
#                          'embed', 'postings', 'src', 'for', 'token', 'true', 'false'}
#     tokens = {token for token in tokens if token not in false_positives and len(token) > 2}
    
#     return tokens

# def check_valid_token(token: str) -> bool:
#     """
#     Verify if a token is valid by checking if it returns jobs from the API.
    
#     Args:
#         token: Greenhouse board token to check
        
#     Returns:
#         bool: True if valid, False otherwise
#     """
#     url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    
#     try:
#         response = requests.get(url, headers=get_random_headers(), timeout=10)
#         if response.status_code == 200:
#             data = response.json()
#             if 'jobs' in data:
#                 return True
#     except Exception:
#         pass
    
#     return False

# def extract_company_name_from_token(token: str) -> str:
#     """
#     Try to derive a company name from the board token.
    
#     Args:
#         token: Greenhouse board token
        
#     Returns:
#         str: Estimated company name
#     """
#     name = token.replace('_', ' ').replace('-', ' ')
#     name = ' '.join(word.capitalize() for word in name.split())
#     return name

# def get_company_info_from_token(token: str) -> Dict[str, Any]:
#     """
#     Get company information from a board token.
    
#     Args:
#         token: Greenhouse board token
        
#     Returns:
#         Dict[str, Any]: Company information
#     """
#     company_name = extract_company_name_from_token(token)
#     job_count = 0
    
#     try:
#         url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
#         response = requests.get(url, headers=get_random_headers(), timeout=10)
#         if response.status_code == 200:
#             data = response.json()
#             job_count = len(data.get('jobs', []))
#     except Exception:
#         pass
    
#     try:
#         url = f"https://boards-api.greenhouse.io/v1/boards/{token}"
#         response = requests.get(url, headers=get_random_headers(), timeout=10)
#         if response.status_code == 200:
#             data = response.json()
#             if 'name' in data:
#                 company_name = data['name']
#     except Exception:
#         pass
    
#     return {
#         'board_token': token,
#         'company_name': company_name,
#         'job_count': job_count,
#         'careers_url': f"https://boards.greenhouse.io/{token}",
#         'discovered_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     }

# # ------------------------------------------------------------------------------
# # Search Methods
# # ------------------------------------------------------------------------------

# def search_for_greenhouse_boards(known_tokens: Set[str]) -> List[Dict[str, Any]]:
#     """
#     Use search engines to find Greenhouse job boards.
    
#     Args:
#         known_tokens: Set of already discovered tokens to avoid duplicates
        
#     Returns:
#         List[Dict[str, Any]]: List of newly discovered companies
#     """
#     new_companies = []
    
#     # Expanded search queries for broader discovery
#     search_queries = [
#         "site:boards.greenhouse.io",
#         "greenhouse.io/boards",
#         "careers greenhouse.io",
#         "jobs greenhouse.io",
#         "apply greenhouse.io",
#         "careers software engineering greenhouse",
#         "careers data science greenhouse",
#         "careers machine learning greenhouse",
#         "tech jobs greenhouse.io",
#         "greenhouse job board",
#         "job opportunities greenhouse",
#         "startup careers greenhouse",
#         "tech company jobs greenhouse",
#         "engineering jobs greenhouse",
#     ]
    
#     random.shuffle(search_queries)
    
#     # Use all available queries (you may choose to limit if needed)
#     for query in search_queries:
#         logger.info(f"Searching for: {query}")
        
#         # Try both search engines for each query
#         search_engines = ["duckduckgo", "google"]
#         random.shuffle(search_engines)
        
#         for engine in search_engines:
#             try:
#                 if engine == "duckduckgo":
#                     search_url = f"https://html.duckduckgo.com/html/?q={query}"
#                     response = requests.get(search_url, headers=get_random_headers(), timeout=15)
#                     if response.status_code == 200:
#                         soup = BeautifulSoup(response.text, 'html.parser')
#                         results = soup.select('.result__url')
#                         for result in results:
#                             link = result.text.strip()
#                             process_search_result(link, known_tokens, new_companies)
                
#                 elif engine == "google":
#                     search_url = f"https://www.google.com/search?q={query}&num=100"
#                     response = requests.get(search_url, headers=get_random_headers(), timeout=15)
#                     if response.status_code == 200:
#                         soup = BeautifulSoup(response.text, 'html.parser')
#                         results = soup.select('a')
#                         for result in results:
#                             href = result.get('href', '')
#                             if href.startswith('/url?q='):
#                                 link = href.split('/url?q=')[1].split('&')[0]
#                                 process_search_result(link, known_tokens, new_companies)
                
#                 # Reduced delay between search engine calls
#                 time.sleep(random.uniform(5, 10))
#             except Exception as e:
#                 logger.error(f"Error searching with {engine}: {str(e)}")
#                 time.sleep(random.uniform(5, 10))
                
#     logger.info(f"Discovered {len(new_companies)} new companies from search")
#     return new_companies

# def process_search_result(url: str, known_tokens: Set[str], new_companies: List[Dict[str, Any]]) -> None:
#     """
#     Process a search result URL to extract board tokens.
    
#     Args:
#         url: URL from search results
#         known_tokens: Set of already discovered tokens
#         new_companies: List to append newly discovered companies
#     """
#     try:
#         tokens = extract_greenhouse_tokens_from_html(url)
        
#         try:
#             response = requests.get(url, headers=get_random_headers(), timeout=10)
#             if response.status_code == 200:
#                 more_tokens = extract_greenhouse_tokens_from_html(response.text)
#                 tokens.update(more_tokens)
#         except Exception:
#             pass
        
#         for token in tokens:
#             if token not in known_tokens and check_valid_token(token):
#                 company_info = get_company_info_from_token(token)
#                 new_companies.append(company_info)
#                 known_tokens.add(token)
#                 logger.info(f"Discovered board token: {token} ({company_info['company_name']})")
#     except Exception as e:
#         logger.error(f"Error processing search result: {str(e)}")

# def check_tech_company_lists(known_tokens: Set[str]) -> List[Dict[str, Any]]:
#     """
#     Check tech company lists and YC companies for Greenhouse usage.
    
#     Args:
#         known_tokens: Set of already discovered tokens
        
#     Returns:
#         List[Dict[str, Any]]: List of newly discovered companies
#     """
#     new_companies = []
#     tech_company_sources = [
#         "https://raw.githubusercontent.com/hankcs/AverageSalaryOfTechCompanies/master/companies.csv",
#         "https://raw.githubusercontent.com/garethdmm/hn_who_is_hiring_keywords/master/companylist.csv",
#         "https://raw.githubusercontent.com/krishnadey30/JobTracker/master/Data/companies.csv",
#     ]
    
#     random.shuffle(tech_company_sources)
    
#     for source_url in tech_company_sources:
#         try:
#             logger.info(f"Checking tech company list from: {source_url}")
#             response = requests.get(source_url, headers=get_random_headers(), timeout=15)
#             if response.status_code == 200:
#                 content = response.text
#                 if ',' in content:
#                     company_names = []
#                     for line in content.split('\n'):
#                         if ',' in line:
#                             company_names.append(line.split(',')[0].strip().lower())
#                     process_company_names(company_names, known_tokens, new_companies)
#         except Exception as e:
#             logger.error(f"Error fetching tech company list: {str(e)}")
#         time.sleep(random.uniform(5, 10))
    
#     try:
#         logger.info("Checking Y Combinator companies")
#         response = requests.get(
#             "https://www.ycombinator.com/companies", 
#             headers=get_random_headers(), 
#             timeout=20
#         )
#         if response.status_code == 200:
#             soup = BeautifulSoup(response.text, 'html.parser')
#             company_elements = soup.select('.CompanyCard_name__jYJGE')
#             company_names = [elem.text.strip().lower() for elem in company_elements]
#             process_company_names(company_names, known_tokens, new_companies)
#     except Exception as e:
#         logger.error(f"Error checking Y Combinator companies: {str(e)}")
    
#     logger.info(f"Discovered {len(new_companies)} new companies from tech lists")
#     return new_companies

# def process_company_names(company_names: List[str], known_tokens: Set[str], new_companies: List[Dict[str, Any]]) -> None:
#     """
#     Process a list of company names to check if they use Greenhouse.
    
#     Args:
#         company_names: List of company names to check
#         known_tokens: Set of already discovered tokens
#         new_companies: List to append newly discovered companies
#     """
#     for company_name in company_names:
#         if not company_name or len(company_name) < 3:
#             continue
            
#         potential_tokens = [
#             company_name.lower().replace(' ', ''),
#             company_name.lower().replace(' ', '-'),
#             company_name.lower().replace(' ', '_'),
#             ''.join(w[0] for w in company_name.split()).lower() if ' ' in company_name else None
#         ]
#         potential_tokens = [t for t in potential_tokens if t and len(t) > 2]
        
#         for token in potential_tokens:
#             if token not in known_tokens and check_valid_token(token):
#                 company_info = get_company_info_from_token(token)
#                 new_companies.append(company_info)
#                 known_tokens.add(token)
#                 logger.info(f"Discovered board token from company name: {token} ({company_info['company_name']})")
#                 break
        
#         try:
#             website_url = f"https://{company_name.lower().replace(' ', '')}.com"
#             check_company_website(website_url, known_tokens, new_companies)
#         except Exception:
#             pass
        
#         time.sleep(random.uniform(0.5, 1.5))

# def check_company_website(website_url: str, known_tokens: Set[str], new_companies: List[Dict[str, Any]]) -> None:
#     """
#     Check a company website for Greenhouse integration.
    
#     Args:
#         website_url: URL of the company website
#         known_tokens: Set of already discovered tokens
#         new_companies: List to append newly discovered companies
#     """
#     try:
#         response = requests.get(website_url, headers=get_random_headers(), timeout=10)
#         if response.status_code == 200:
#             tokens = extract_greenhouse_tokens_from_html(response.text)
#             for careers_path in ['/careers', '/jobs', '/join-us', '/join', '/work-with-us']:
#                 try:
#                     careers_url = website_url.rstrip('/') + careers_path
#                     careers_response = requests.get(careers_url, headers=get_random_headers(), timeout=10)
#                     if careers_response.status_code == 200:
#                         careers_tokens = extract_greenhouse_tokens_from_html(careers_response.text)
#                         tokens.update(careers_tokens)
#                 except Exception:
#                     pass
            
#             for token in tokens:
#                 if token not in known_tokens and check_valid_token(token):
#                     company_info = get_company_info_from_token(token)
#                     new_companies.append(company_info)
#                     known_tokens.add(token)
#                     logger.info(f"Discovered board token from website: {token} ({company_info['company_name']})")
#     except Exception:
#         pass

# # ------------------------------------------------------------------------------
# # Main Execution
# # ------------------------------------------------------------------------------

# def run_scraper(batch_size: int = 100) -> None:
#     """
#     Run the token scraper to discover companies.
    
#     Args:
#         batch_size: Number of companies to save in each batch file
#     """
#     known_tokens = load_discovered_tokens()
    
#     next_batch = 0
#     if os.path.exists('output'):
#         for filename in os.listdir('output'):
#             if filename.startswith('greenhouse_companies_batch_') and filename.endswith('.csv'):
#                 try:
#                     batch_num = int(filename.split('_batch_')[1].split('.')[0])
#                     next_batch = max(next_batch, batch_num + 1)
#                 except ValueError:
#                     pass
    
#     current_batch = []
#     logger.info(f"Starting company scraper (batch size: {batch_size}, next batch: {next_batch:03d})")
    
#     try:
#         while True:
#             if len(current_batch) < batch_size:
#                 logger.info(f"Current batch has {len(current_batch)}/{batch_size} companies")
                
#                 method = random.choice(["search", "tech_lists"])
#                 if method == "search":
#                     new_companies = search_for_greenhouse_boards(known_tokens)
#                 else:
#                     new_companies = check_tech_company_lists(known_tokens)
                
#                 current_batch.extend(new_companies)
#                 for company in new_companies:
#                     known_tokens.add(company['board_token'])
            
#             if len(current_batch) >= batch_size:
#                 logger.info(f"Batch complete with {len(current_batch)} companies")
#                 save_companies_batch(current_batch, next_batch)
#                 next_batch += 1
#                 current_batch = []
#             elif len(current_batch) > 0 and random.random() < 0.1:
#                 logger.info(f"Saving intermediate batch with {len(current_batch)} companies")
#                 save_companies_batch(current_batch, next_batch)
            
#             sleep_time = random.uniform(5, 10)  # reduced sleep time for faster iterations
#             logger.info(f"Pausing for {sleep_time:.1f} seconds")
#             time.sleep(sleep_time)
            
#     except KeyboardInterrupt:
#         logger.info("Scraper interrupted by user")
#     except Exception as e:
#         logger.error(f"Scraper error: {str(e)}")
#     finally:
#         if current_batch:
#             logger.info(f"Saving final batch with {len(current_batch)} companies")
#             save_companies_batch(current_batch, next_batch)
#         logger.info("Scraper finished")

# def main():
#     """Main execution function"""
#     if not os.path.exists('output'):
#         os.makedirs('output')
    
#     import argparse
#     parser = argparse.ArgumentParser(description='Greenhouse Company Token Scraper')
#     parser.add_argument('--batch-size', type=int, default=100,
#                         help='Number of companies to save in each batch file')
#     parser.add_argument('--continuous', action='store_true',
#                         help='Run continuously in a loop')
#     args = parser.parse_args()
    
#     if args.continuous:
#         logger.info("Starting continuous scraper...")
#         while True:
#             try:
#                 run_scraper(args.batch_size)
#                 logger.info("Continuous scraper restarting after completion...")
#                 time.sleep(60)  # Wait before restarting
#             except Exception as e:
#                 logger.error(f"Continuous scraper error: {str(e)}")
#                 logger.info("Restarting in 5 minutes...")
#                 time.sleep(300)
#     else:
#         run_scraper(args.batch_size)

# if __name__ == "__main__":
#     main()

#!/usr/bin/env python3
#!/usr/bin/env python3
"""
greenhouse_companies.py

Sole purpose: Discover board tokens of all companies using Greenhouse ATS.
This script continuously scrapes company board tokens from across the web,
saving them in batches of 100 in the 'output_latest' folder.
"""

import re
import json
import os
import logging
import random
import pandas as pd
import asyncio
import aiohttp
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Set
from urllib.parse import urlparse

# External library for robust retries
from tenacity import retry, wait_random_exponential, stop_after_attempt, RetryError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("company_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('greenhouse_companies')

# List of user agents to mimic a browser
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
]

def get_random_headers():
    """Return random headers for each request."""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }

# Optionally, set up a list of proxies (format: "http://ip:port"). Leave empty if not used.
PROXIES = [
    # "http://proxy1.example.com:8080",
    # "http://proxy2.example.com:8080"
]

# Folder for output
OUTPUT_FOLDER = 'output_latest'

# ------------------------------------------------------------------------------
# Robust HTTP GET using Tenacity for automatic retries and optional proxy rotation
# ------------------------------------------------------------------------------

@retry(wait=wait_random_exponential(min=1, max=10), stop=stop_after_attempt(3), reraise=True)
async def robust_get(url: str, session: aiohttp.ClientSession, **kwargs) -> aiohttp.ClientResponse:
    """
    Perform an HTTP GET request with automatic retries.
    Optionally uses a random proxy from the PROXIES list.
    """
    proxy = random.choice(PROXIES) if PROXIES else None
    async with session.get(url, proxy=proxy, **kwargs) as response:
        response.raise_for_status()
        return response

# ------------------------------------------------------------------------------
# File Management Functions
# ------------------------------------------------------------------------------

def load_discovered_tokens() -> Set[str]:
    """
    Load all previously discovered board tokens from CSV files in OUTPUT_FOLDER.
    """
    known_tokens = set()
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        return known_tokens

    for filename in os.listdir(OUTPUT_FOLDER):
        if filename.startswith('greenhouse_companies_batch_') and filename.endswith('.csv'):
            try:
                df = pd.read_csv(os.path.join(OUTPUT_FOLDER, filename))
                if 'board_token' in df.columns:
                    tokens = set(df['board_token'].tolist())
                    known_tokens.update(tokens)
                    logger.info(f"Loaded {len(tokens)} tokens from {filename}")
            except Exception as e:
                logger.error(f"Error loading file {filename}: {str(e)}")
    logger.info(f"Loaded a total of {len(known_tokens)} previously discovered tokens")
    return known_tokens

def save_companies_batch(companies: List[Dict[str, Any]], batch_num: int) -> None:
    """
    Save a batch of companies to CSV and JSON files in OUTPUT_FOLDER.
    """
    if not companies:
        logger.info("No companies to save in this batch")
        return

    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    try:
        csv_filename = f"{OUTPUT_FOLDER}/greenhouse_companies_batch_{batch_num:03d}.csv"
        df = pd.DataFrame(companies)
        df = df.sort_values('company_name')
        df.to_csv(csv_filename, index=False)

        json_filename = f"{OUTPUT_FOLDER}/greenhouse_companies_batch_{batch_num:03d}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(companies, f, indent=2)

        logger.info(f"Successfully saved {len(companies)} companies to batch {batch_num:03d}")
    except Exception as e:
        logger.error(f"Error saving companies batch {batch_num}: {str(e)}")

# ------------------------------------------------------------------------------
# Token Discovery Functions
# ------------------------------------------------------------------------------

def extract_greenhouse_tokens_from_html(html_content: str) -> Set[str]:
    """
    Extract potential Greenhouse board tokens from HTML content using regex.
    """
    patterns = [
        r'boards\.greenhouse\.io\/([a-zA-Z0-9_-]+)',
        r'boards-api\.greenhouse\.io\/v1\/boards\/([a-zA-Z0-9_-]+)',
        r'greenhouse\.io\/boards\/([a-zA-Z0-9_-]+)',
        r'"boardToken":\s*"([a-zA-Z0-9_-]+)"',
        r'data-board-token="([a-zA-Z0-9_-]+)"',
        r'greenhouse\.io/embed/job_board/\?for=([a-zA-Z0-9_-]+)',
        r'gh_src=([a-zA-Z0-9_-]+)'
    ]
    tokens = set()
    for pattern in patterns:
        matches = re.findall(pattern, html_content)
        tokens.update(matches)
    false_positives = {'api', 'v1', 'boards', 'www', 'jobs', 'job', 'careers',
                       'career', 'embed', 'postings', 'src', 'for', 'token', 'true', 'false'}
    return {token for token in tokens if token not in false_positives and len(token) > 2}

async def check_valid_token_async(token: str, session: aiohttp.ClientSession) -> bool:
    """
    Verify if a board token is valid by querying the jobs API.
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        response = await robust_get(url, session, timeout=10)
        data = await response.json()
        return 'jobs' in data
    except Exception:
        return False

def extract_company_name_from_token(token: str) -> str:
    """
    Derive an estimated company name from the board token.
    """
    name = token.replace('_', ' ').replace('-', ' ')
    return ' '.join(word.capitalize() for word in name.split())

async def get_company_info_from_token_async(token: str, session: aiohttp.ClientSession) -> Dict[str, Any]:
    """
    Retrieve company information (name, job count, etc.) from a board token.
    """
    company_name = extract_company_name_from_token(token)
    job_count = 0
    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        response = await robust_get(url, session, timeout=10)
        data = await response.json()
        job_count = len(data.get('jobs', []))
    except Exception:
        pass

    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}"
        response = await robust_get(url, session, timeout=10)
        data = await response.json()
        if 'name' in data:
            company_name = data['name']
    except Exception:
        pass

    return {
        'board_token': token,
        'company_name': company_name,
        'job_count': job_count,
        'careers_url': f"https://boards.greenhouse.io/{token}",
        'discovered_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ------------------------------------------------------------------------------
# Methods to Discover Board Tokens
# ------------------------------------------------------------------------------

async def process_search_result(url: str, known_tokens: Set[str], new_companies: List[Dict[str, Any]], session: aiohttp.ClientSession) -> None:
    """
    Process a search result URL to extract board tokens.
    If the URL already contains 'boards.greenhouse.io', extract token directly.
    Otherwise, fetch the page and extract tokens from its content.
    """
    try:
        # If URL already contains a direct board URL, extract token from the path.
        if "boards.greenhouse.io" in url:
            parsed = urlparse(url)
            token = parsed.path.strip("/").split("/")[-1]
            if token and token not in known_tokens:
                if await check_valid_token_async(token, session):
                    company_info = await get_company_info_from_token_async(token, session)
                    new_companies.append(company_info)
                    known_tokens.add(token)
                    logger.info(f"Discovered board token from URL: {token} ({company_info['company_name']})")
            return

        # Otherwise, fetch the page content and extract tokens.
        response = await robust_get(url, session, timeout=10)
        html = await response.text()
        tokens = extract_greenhouse_tokens_from_html(html)
        for token in tokens:
            if token not in known_tokens:
                if await check_valid_token_async(token, session):
                    company_info = await get_company_info_from_token_async(token, session)
                    new_companies.append(company_info)
                    known_tokens.add(token)
                    logger.info(f"Discovered board token from page: {token} ({company_info['company_name']})")
    except Exception as e:
        logger.error(f"Error processing search result {url}: {str(e)}")

async def search_for_greenhouse_boards(known_tokens: Set[str], session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Use search engines (DuckDuckGo and Google) to find Greenhouse job boards.
    The queries now include phrases like "Powered by Greenhouse" and "Greenhouse ATS".
    """
    new_companies = []
    tasks = []
    
    search_queries = [
        "site:boards.greenhouse.io",
        "greenhouse.io/boards",
        "careers greenhouse.io",
        "jobs greenhouse.io",
        "apply greenhouse.io",
        "tech jobs greenhouse.io",
        "greenhouse job board",
        "job opportunities greenhouse",
        "startup careers greenhouse",
        "tech company jobs greenhouse",
        "engineering jobs greenhouse",
        "intext:'Powered by Greenhouse'",
        "intext:'Greenhouse ATS'",
        "Greenhouse ATS careers"
    ]
    
    random.shuffle(search_queries)
    # For reduced rate-limiting, you may choose to use only DuckDuckGo.
    search_engine = "duckduckgo"
    
    for query in search_queries:
        logger.info(f"Searching for: {query}")
        if search_engine == "duckduckgo":
            search_url = f"https://html.duckduckgo.com/html/?q={query}"
            try:
                response = await robust_get(search_url, session, headers=get_random_headers(), timeout=15)
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                results = soup.select('.result__url')
                for result in results:
                    link = result.get_text().strip()
                    tasks.append(process_search_result(link, known_tokens, new_companies, session))
            except Exception as e:
                logger.error(f"Error searching with DuckDuckGo for query '{query}': {str(e)}")
        await asyncio.sleep(random.uniform(7, 12))
    
    if tasks:
        await asyncio.gather(*tasks)
    logger.info(f"Discovered {len(new_companies)} new companies from search")
    return new_companies

async def scrape_greenhouse_customers(known_tokens: Set[str], session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    Scrape the official Greenhouse customers page to extract board tokens.
    """
    new_companies = []
    url = "https://www.greenhouse.io/customers"
    try:
        response = await robust_get(url, session, headers=get_random_headers(), timeout=15)
        html = await response.text()
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all("a", href=True)
        for link in links:
            href = link['href']
            if "boards.greenhouse.io" in href:
                parsed = urlparse(href)
                token = parsed.path.strip("/").split("/")[-1]
                if token and token not in known_tokens:
                    if await check_valid_token_async(token, session):
                        company_info = await get_company_info_from_token_async(token, session)
                        new_companies.append(company_info)
                        known_tokens.add(token)
                        logger.info(f"Discovered board token from customers page: {token} ({company_info['company_name']})")
        if not new_companies:
            logger.info("No new companies found on the customers page.")
    except Exception as e:
        logger.error(f"Error scraping customers page: {str(e)}")
    return new_companies

async def scrape_company_directory(known_tokens: Set[str], session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """
    If a 'company_directory.csv' file exists (with a 'domain' column), read it and for each company,
    crawl the company's careers page to look for Greenhouse board tokens.
    """
    new_companies = []
    directory_file = "company_directory.csv"
    if not os.path.exists(directory_file):
        logger.info("No company_directory.csv found; skipping company directory scraping.")
        return new_companies

    try:
        df = pd.read_csv(directory_file)
        if 'domain' not in df.columns:
            logger.error("company_directory.csv must contain a 'domain' column.")
            return new_companies
        domains = df['domain'].dropna().unique()
        for domain in domains:
            url = f"https://{domain}/careers"
            try:
                response = await robust_get(url, session, headers=get_random_headers(), timeout=10)
                html = await response.text()
                tokens = extract_greenhouse_tokens_from_html(html)
                for token in tokens:
                    if token not in known_tokens:
                        if await check_valid_token_async(token, session):
                            company_info = await get_company_info_from_token_async(token, session)
                            new_companies.append(company_info)
                            known_tokens.add(token)
                            logger.info(f"Discovered board token from company directory: {token} ({company_info['company_name']})")
            except Exception as e:
                logger.info(f"Error processing company {domain}: {e}")
            await asyncio.sleep(random.uniform(1, 3))
    except Exception as e:
        logger.error(f"Error reading company_directory.csv: {e}")
    return new_companies

# ------------------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------------------

async def run_scraper_async(batch_size: int = 100) -> None:
    """
    Run the token scraper to continuously discover companies using Greenhouse ATS.
    """
    known_tokens = load_discovered_tokens()
    next_batch = 0
    if os.path.exists(OUTPUT_FOLDER):
        for filename in os.listdir(OUTPUT_FOLDER):
            if filename.startswith('greenhouse_companies_batch_') and filename.endswith('.csv'):
                try:
                    batch_num = int(filename.split('_batch_')[1].split('.')[0])
                    next_batch = max(next_batch, batch_num + 1)
                except ValueError:
                    pass

    current_batch = []
    logger.info(f"Starting company scraper (batch size: {batch_size}, next batch: {next_batch:03d})")

    async with aiohttp.ClientSession(headers=get_random_headers()) as session:
        try:
            while True:
                if len(current_batch) < batch_size:
                    logger.info(f"Current batch has {len(current_batch)}/{batch_size} companies")
                    # Randomly choose among three methods: search, customers, or company directory
                    method = random.choice(["search", "customers", "directory"])
                    if method == "search":
                        new_companies = await search_for_greenhouse_boards(known_tokens, session)
                    elif method == "customers":
                        new_companies = await scrape_greenhouse_customers(known_tokens, session)
                    elif method == "directory":
                        new_companies = await scrape_company_directory(known_tokens, session)
                    
                    current_batch.extend(new_companies)
                    for company in new_companies:
                        known_tokens.add(company['board_token'])
                
                if len(current_batch) >= batch_size:
                    logger.info(f"Batch complete with {len(current_batch)} companies")
                    save_companies_batch(current_batch, next_batch)
                    next_batch += 1
                    current_batch = []
                elif current_batch and random.random() < 0.1:
                    logger.info(f"Saving intermediate batch with {len(current_batch)} companies")
                    save_companies_batch(current_batch, next_batch)
                
                sleep_time = random.uniform(7, 12)
                logger.info(f"Pausing for {sleep_time:.1f} seconds")
                await asyncio.sleep(sleep_time)
        except KeyboardInterrupt:
            logger.info("Scraper interrupted by user")
        except Exception as e:
            logger.error(f"Scraper error: {str(e)}")
        finally:
            if current_batch:
                logger.info(f"Saving final batch with {len(current_batch)} companies")
                save_companies_batch(current_batch, next_batch)
            logger.info("Scraper finished")

def main():
    """Main execution function."""
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
    import argparse
    parser = argparse.ArgumentParser(description='Greenhouse Company Token Scraper')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Number of companies to save in each batch file')
    parser.add_argument('--continuous', action='store_true',
                        help='Run continuously in a loop')
    args = parser.parse_args()
    if args.continuous:
        logger.info("Starting continuous scraper...")
        async def continuous_scraper():
            while True:
                try:
                    await run_scraper_async(args.batch_size)
                    logger.info("Continuous scraper restarting after completion...")
                    await asyncio.sleep(60)
                except Exception as e:
                    logger.error(f"Continuous scraper error: {str(e)}")
                    logger.info("Restarting in 5 minutes...")
                    await asyncio.sleep(300)
        asyncio.run(continuous_scraper())
    else:
        asyncio.run(run_scraper_async(args.batch_size))

if __name__ == "__main__":
    main()

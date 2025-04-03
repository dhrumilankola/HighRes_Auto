# Greenhouse Job Scraper

This script (`greenhouse.py`) is designed to scrape tech job listings from Greenhouse ATS using company board tokens. It focuses on software engineering, data science, and machine learning roles posted within the last 2 days that require 0-2 years of experience (or do not mention experience), and only includes jobs located in the United States or marked as remote. For each job, the script fetches the full job description page and scans it to ensure that any disqualifying experience requirements are filtered out.

## Commands

python greenhouse.py --company-file "{file or filePath}"

Fetch jobs that have been posted in the last 1 day:

    python greenhouse.py --company-file "{file or filePath}" --days 1

Save the output files with a custom prefix:

    python greenhouse.py --company-file "{file or filePath}" --days 1 --output my_tech_jobs

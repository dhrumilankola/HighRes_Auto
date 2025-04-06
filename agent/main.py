import asyncio
import logging
import argparse
import os
import sys
import traceback
import yaml 
from job_processor import job_processing_service, process_job
from queue_manager import QueueManager
from resume_loader import load_resume_data, get_resume_pdf_path, load_config

# --- Configuration Loading ---
try:
    config = load_config()
except (FileNotFoundError, Exception) as e:
    print(f"FATAL: Could not load config.yaml. Error: {e}", file=sys.stderr)
    sys.exit(1)

# --- Configure logging ---
log_file_path = os.path.join("logs", "log.txt")
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
# Try forcing UTF-8 for the stream handler
try:
    stream_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf8', buffering=1)
except: # Fallback if overriding sys.stdout fails
     pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, encoding='utf-8'), # Also ensure file handler uses utf-8
        stream_handler # Use the potentially encoding-corrected stream handler
    ]
)
logger = logging.getLogger("agent_main")

logger.info("Agent starting...") # Log after basicConfig is set up

async def check_environment():
    """Check if the environment is properly set up based on config."""
    global config # Use the globally loaded config
    logger.info("Performing environment checks...")
    try:
        # Check for required directories from config
        screenshots_dir = config.get('paths', {}).get('screenshots_dir', 'screenshots')
        queue_dir = config.get('paths', {}).get('queue_dir', 'queue_system')
        resume_dir = config.get('paths', {}).get('resume_dir', 'resume_data')

        os.makedirs(screenshots_dir, exist_ok=True)
        logger.info(f"✅ Screenshots directory check: {screenshots_dir}")
        os.makedirs(queue_dir, exist_ok=True)
        logger.info(f"✅ Queue directory check: {queue_dir}")
        if not os.path.isdir(resume_dir):
             logger.error(f"Resume directory not found: {resume_dir}")
             return False
        logger.info(f"✅ Resume directory check: {resume_dir}")

        # Check for required files (using resume_loader functions that use config)
        try:
            load_resume_data(config) # Checks for resume JSON
        except FileNotFoundError:
             # Error already logged by load_resume_data
             return False
        except ValueError:
             logger.error("Resume JSON is invalid.")
             return False

        # Check for PDF (optional, handled by get_resume_pdf_path)
        get_resume_pdf_path(config) # Logs warning if not found

        # Check if Playwright is installed
        try:
            from playwright.async_api import async_playwright
            logger.info("Attempting Playwright browser launch...")
            async with async_playwright() as p:
                # Use chromium, firefox, or webkit - maybe make configurable later?
                browser = await p.chromium.launch(headless=True)
                await browser.close()
            logger.info("✅ Playwright is properly installed and browser launched successfully.")
        except ImportError:
             logger.error("Playwright library not found. Please install it: pip install playwright")
             return False
        except Exception as e:
            logger.error(f"Playwright installation issue: {str(e)}")
            logger.error("Could not launch browser. Try running 'playwright install' if browsers are missing.")
            # logger.error(traceback.format_exc()) # Uncomment for detailed install errors
            return False

        logger.info("✅ Environment check successful.")
        return True
    except Exception as e:
        logger.error(f"Environment check failed: {str(e)}")
        logger.error(traceback.format_exc())
        return False

async def single_job_mode(job_id: str):
    """Process a single job by ID."""
    global config
    try:
        logger.info("Initializing for single job mode...")
        queue_manager = QueueManager(config) # Pass config
        resume = load_resume_data(config) # Pass config

        # Find the job in the queued jobs
        queued_jobs = queue_manager._read_queue(queue_manager.queued_path)
        job = next((j for j in queued_jobs if j.get('id') == job_id), None)

        if not job:
            logger.error(f"Job {job_id} not found in the queue")
            return

        # Process the job without moving it between queues
        logger.info(f"Processing single job {job_id}")
        # Use testing_mode from config to control submission
        headless = not config.get('agent_settings', {}).get('testing_mode', False)
        # process_job expects config now
        success, message, details = await process_job(job, resume, config, headless=headless)

        logger.info(f"Job processing result: Success={success}")
        if message: logger.info(f"Message: {message}")
        if details: logger.info(f"Details: {details}")
    except (FileNotFoundError, ValueError) as e:
         logger.error(f"Configuration or Resume data error: {e}")
    except Exception as e:
        logger.error(f"Error in single job mode: {str(e)}")
        logger.error(traceback.format_exc())

async def direct_url_mode(url: str):
    """Process a job directly from a URL."""
    global config
    try:
        logger.info("Initializing for direct URL mode...")
        resume = load_resume_data(config) # Pass config

        # Create a mock job object
        job = {
            'id': f"direct_{int(asyncio.get_event_loop().time())}",
            'job_data': {
                'title': 'Direct URL Job',
                'company': 'Unknown',
                'apply_url': url
            },
            'attempts': 0 # Add attempts
        }

        # Process the job - always run non-headless for direct URL debugging? Or make it configurable?
        # Let's keep it non-headless for now for easier debugging of ad-hoc URLs.
        # But use testing_mode from config to decide on actual submission.
        logger.info(f"Processing job from URL: {url}")
        # process_job expects config now
        success, message, details = await process_job(job, resume, config, headless=False) # Keep headless=False for URL mode

        logger.info(f"Job processing result: Success={success}")
        if message: logger.info(f"Message: {message}")
        if details: logger.info(f"Details: {details}")
    except (FileNotFoundError, ValueError) as e:
         logger.error(f"Configuration or Resume data error: {e}")
    except Exception as e:
        logger.error(f"Error in direct URL mode: {str(e)}")
        logger.error(traceback.format_exc())

async def main():
    """Main entry point for the application."""
    global config # Use global config loaded at start

    parser = argparse.ArgumentParser(description='HIGHRES Job Application Automation')
    parser.add_argument('--mode', choices=['service', 'single', 'url'], default='service',
                       help='Run as service, process a single job, or process a URL (default: service)')
    parser.add_argument('--job-id', help='Job ID to process (required for single mode)')
    parser.add_argument('--url', help='URL to process (required for url mode)')
    parser.add_argument('--check-env', action='store_true', help='Check environment setup and exit')
    args = parser.parse_args()

    # --- Environment Check ---
    # Run check first if requested or if running service mode
    if args.check_env or args.mode == 'service':
        env_ok = await check_environment()
        if not env_ok:
            logger.error("Environment check failed. Please fix the issues before running the agent.")
            sys.exit(1) # Exit if check fails
        if args.check_env:
             logger.info("Environment check passed. Exiting as requested.")
             return # Exit after successful check if --check-env was passed

    # --- Choose action based on mode ---
    try:
        if args.mode == 'single':
            if not args.job_id:
                logger.error("Job ID (--job-id) is required for single mode")
                return
            await single_job_mode(args.job_id)

        elif args.mode == 'url':
            if not args.url:
                logger.error("URL (--url) is required for url mode")
                return
            await direct_url_mode(args.url)

        elif args.mode == 'service':
            logger.info("Starting job processing service...")
            await job_processing_service(config) # Pass config

        else:
            logger.error(f"Invalid mode selected: {args.mode}")
            parser.print_help()

    except (FileNotFoundError, ValueError) as e:
         # Catch config/resume loading errors that might occur during initialization within modes
         logger.error(f"FATAL: Configuration or Resume data error: {e}")
         sys.exit(1)
    except Exception as e:
         # Catch unexpected errors within the modes themselves
         logger.error(f"An unexpected error occurred in mode '{args.mode}': {e}")
         logger.error(traceback.format_exc())
         sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
    except Exception as e:
        # Catch errors during asyncio.run(main()) itself, though most should be caught inside main()
        logger.critical(f"Unhandled exception during agent execution: {str(e)}")
        logger.critical(traceback.format_exc())
        sys.exit(1)
    finally:
        logger.info("Agent shutting down.")
        logging.shutdown() # Ensure logs are flushed
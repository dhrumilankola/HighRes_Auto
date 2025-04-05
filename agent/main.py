# agent/main.py

import asyncio
import logging
import argparse
from job_processor import job_processing_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("agent_main")

async def main():
    parser = argparse.ArgumentParser(description='HIGHRES Job Application Automation')
    parser.add_argument('--mode', choices=['service', 'single'], default='service',
                      help='Run as service or process a single job (default: service)')
    parser.add_argument('--job-id', help='Job ID to process (required for single mode)')
    args = parser.parse_args()
    
    if args.mode == 'single':
        if not args.job_id:
            logger.error("Job ID is required for single mode")
            return
        
        from queue_manager import QueueManager
        from resume_loader import load_resume_data
        
        queue_manager = QueueManager()
        resume = load_resume_data()
        
        # Find the job in the queued jobs
        queued_jobs = queue_manager._read_queue(queue_manager.queued_path)
        job = next((j for j in queued_jobs if j.get('id') == args.job_id), None)
        
        if not job:
            logger.error(f"Job {args.job_id} not found in the queue")
            return
        
        from job_processor import process_job
        
        # Process the job without moving it between queues
        logger.info(f"Processing single job {args.job_id}")
        success, message, details = await process_job(job, resume)
        
        logger.info(f"Job processing result: {success}")
        logger.info(f"Message: {message}")
        logger.info(f"Details: {details}")
        
    else:
        # Run as a service
        logger.info("Starting job processing service")
        await job_processing_service()

if __name__ == "__main__":
    asyncio.run(main())
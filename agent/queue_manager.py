import os
import json
import logging
import time
from typing import List, Dict, Any, Optional
from filelock import FileLock, Timeout

logger = logging.getLogger("queue_manager")

class QueueManager:
    """Manages job queues using JSON files and file locks."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initializes the QueueManager.

        Args:
            config: The loaded agent configuration dictionary.
        """
        if config is None:
            from resume_loader import load_config # Avoid circular import if possible
            config = load_config()
            logger.warning("QueueManager initialized without config, loading dynamically.")

        base_path = config.get('paths', {}).get('queue_dir', 'queue_system')
        os.makedirs(base_path, exist_ok=True)

        self.queued_path = os.path.join(base_path, "queued_jobs.json")
        self.processing_path = os.path.join(base_path, "processing_jobs.json")
        self.completed_path = os.path.join(base_path, "completed_jobs.json")
        self.failed_path = os.path.join(base_path, "failed_jobs.json")
        self.review_path = os.path.join(base_path, "review_jobs.json") # For manual review

        # Initialize queue files if they don't exist
        for path in [self.queued_path, self.processing_path, self.completed_path, self.failed_path, self.review_path]:
            if not os.path.exists(path):
                self._write_queue(path, [])

        # File locks to prevent race conditions
        self.queued_lock_path = self.queued_path + ".lock"
        self.processing_lock_path = self.processing_path + ".lock"
        self.completed_lock_path = self.completed_path + ".lock"
        self.failed_lock_path = self.failed_path + ".lock"
        self.review_lock_path = self.review_path + ".lock"

        self.lock_timeout = 10 # seconds

        logger.info(f"QueueManager initialized. Queues in: {base_path}")

    def _read_queue(self, file_path: str) -> List[Dict[str, Any]]:
        """Reads a queue file safely."""
        try:
            # Check if file exists, if not return empty list
            if not os.path.exists(file_path):
                logger.warning(f"Queue file {file_path} not found during read, returning empty list.")
                return []
            # Check if file is empty or invalid JSON
            if os.path.getsize(file_path) == 0:
                 logger.warning(f"Queue file {file_path} is empty, returning empty list.")
                 return []

            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    if not isinstance(data, list):
                         logger.error(f"Invalid format in queue file {file_path}. Expected list, got {type(data)}. Returning empty list.")
                         return []
                    return data
                except json.JSONDecodeError:
                     logger.error(f"JSON decode error in queue file {file_path}. Returning empty list.")
                     # Optionally: backup the corrupted file here
                     # os.rename(file_path, f"{file_path}.corrupted_{int(time.time())}")
                     # self._write_queue(file_path, []) # Recreate empty
                     return []
        except FileNotFoundError:
             logger.warning(f"Queue file {file_path} disappeared during read, returning empty list.")
             return []
        except Exception as e:
            logger.error(f"Unexpected error reading queue file {file_path}: {e}")
            return [] # Return empty list on error

    def _write_queue(self, file_path: str, data: List[Dict[str, Any]]) -> None:
        """Writes data to a queue file safely."""
        # Write to a temporary file first, then rename to make it atomic
        temp_file_path = file_path + ".tmp"
        try:
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            os.replace(temp_file_path, file_path) # Atomic rename
        except Exception as e:
            logger.error(f"Error writing queue file {file_path}: {e}")
            # Clean up temp file if it exists
            if os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except OSError as remove_err:
                     logger.error(f"Error removing temporary queue file {temp_file_path}: {remove_err}")

    def _acquire_lock(self, lock_path: str) -> FileLock:
        """Acquires a file lock."""
        lock = FileLock(lock_path, timeout=self.lock_timeout)
        try:
            lock.acquire()
            return lock
        except Timeout:
            logger.error(f"Could not acquire lock on {lock_path} within {self.lock_timeout} seconds.")
            raise Timeout(f"Could not acquire lock for {os.path.basename(lock_path)}")


    def add_job(self, job_data: Dict[str, Any]) -> bool:
        """Adds a new job to the queued list."""
        if not job_data.get('id'):
             job_data['id'] = f"job_{int(time.time() * 1000)}" # Generate simple ID if missing
             logger.warning(f"Job added without ID, generated: {job_data['id']}")

        job_data['status'] = 'queued'
        job_data['attempts'] = 0
        job_data['added_timestamp'] = time.time()

        try:
            with self._acquire_lock(self.queued_lock_path):
                queued_jobs = self._read_queue(self.queued_path)
                # Check for duplicates
                if any(j.get('id') == job_data['id'] for j in queued_jobs):
                     logger.warning(f"Job with ID {job_data['id']} already exists in queue. Skipping add.")
                     return False
                queued_jobs.append(job_data)
                self._write_queue(self.queued_path, queued_jobs)
                logger.info(f"Job {job_data['id']} added to queue.")
                return True
        except (Timeout, Exception) as e:
            logger.error(f"Failed to add job {job_data.get('id', 'N/A')}: {e}")
            return False


    def get_next_job(self) -> Optional[Dict[str, Any]]:
        """
        Gets the next job from the queue and moves it to processing.
        Returns None if the queue is empty or locked.
        """
        job_to_process = None
        try:
            # Lock both queued and processing queues to ensure atomicity
            with self._acquire_lock(self.queued_lock_path), \
                 self._acquire_lock(self.processing_lock_path):

                queued_jobs = self._read_queue(self.queued_path)
                if not queued_jobs:
                    return None # Queue is empty

                # Get the first job (FIFO)
                job_to_process = queued_jobs.pop(0)
                job_to_process['status'] = 'processing'
                job_to_process['start_processing_timestamp'] = time.time()

                processing_jobs = self._read_queue(self.processing_path)
                processing_jobs.append(job_to_process)

                # Write changes back
                self._write_queue(self.queued_path, queued_jobs)
                self._write_queue(self.processing_path, processing_jobs)

                logger.info(f"Moved job {job_to_process['id']} from queued to processing.")
                return job_to_process

        except Timeout:
            logger.warning("Could not acquire locks to get next job. Will retry later.")
            return None
        except Exception as e:
            logger.error(f"Error getting next job: {e}")
            # Rollback potential partial move if job_to_process was assigned but failed after
            if job_to_process:
                logger.error(f"Attempting rollback for job {job_to_process.get('id', 'N/A')}")
                try:
                    # This rollback is complex and might fail itself. Needs careful thought.
                    # Simplest approach: just log the error, the job might be stuck in processing.
                    # A more robust system would have recovery mechanisms.
                    pass
                except Exception as rb_e:
                    logger.error(f"Rollback failed: {rb_e}")
            return None

    def _move_job(self, job_id: str, from_path: str, from_lock_path: str, to_path: str, to_lock_path: str, new_status: str, details: Optional[Dict] = None) -> bool:
        """Helper function to move a job between files atomically."""
        moved_job = None
        try:
            with self._acquire_lock(from_lock_path), self._acquire_lock(to_lock_path):
                from_jobs = self._read_queue(from_path)
                to_jobs = self._read_queue(to_path)

                job_index = -1
                for i, job in enumerate(from_jobs):
                    if job.get('id') == job_id:
                        job_index = i
                        break

                if job_index == -1:
                    logger.warning(f"Job {job_id} not found in {os.path.basename(from_path)} to move.")
                    return False # Job might have been moved already

                moved_job = from_jobs.pop(job_index)
                moved_job['status'] = new_status
                moved_job['end_processing_timestamp'] = time.time()
                if details:
                    moved_job['result_details'] = details

                to_jobs.append(moved_job)

                self._write_queue(from_path, from_jobs)
                self._write_queue(to_path, to_jobs)
                logger.info(f"Moved job {job_id} from {os.path.basename(from_path)} to {os.path.basename(to_path)} with status '{new_status}'.")
                return True

        except (Timeout, Exception) as e:
            logger.error(f"Failed moving job {job_id} from {os.path.basename(from_path)} to {os.path.basename(to_path)}: {e}")
            # Potential rollback needed here if files were partially written?
            # The atomic write helps, but the read/modify/write isn't fully atomic across files without a distributed transaction concept.
            # For file-based queue, log the error and potentially require manual cleanup.
            return False


    def mark_job_complete(self, job_id: str, details: Optional[Dict] = None) -> bool:
        """Moves a job from processing to completed."""
        return self._move_job(job_id, self.processing_path, self.processing_lock_path,
                              self.completed_path, self.completed_lock_path, 'completed', details)

    def mark_job_failed(self, job_id: str, reason: str, details: Optional[Dict] = None, retry: bool = False, max_retries: int = 2) -> bool:
        """Moves a job from processing to failed or back to queued if retry=True."""
        job = None
        # First, get the job data to check attempts
        try:
            with self._acquire_lock(self.processing_lock_path):
                processing_jobs = self._read_queue(self.processing_path)
                job = next((j for j in processing_jobs if j.get('id') == job_id), None)

                if not job:
                    logger.warning(f"Job {job_id} not found in processing to mark as failed/retry.")
                    return False # Already moved?

                current_attempts = job.get('attempts', 0)
                job['last_error_reason'] = reason
                if details:
                    if 'result_details' not in job: job['result_details'] = {}
                    job['result_details'].update(details) # Merge details

            # Decide destination based on retry logic
            if retry and current_attempts < max_retries:
                job['attempts'] = current_attempts + 1
                job['status'] = 'queued' # Reset status
                logger.info(f"Retrying job {job_id} (Attempt {job['attempts'] + 1}/{max_retries + 1}). Moving back to queue.")
                # Move from processing back to queued
                # Need to lock processing and queued
                moved = False
                try:
                    with self._acquire_lock(self.processing_lock_path), self._acquire_lock(self.queued_lock_path):
                        processing_jobs = self._read_queue(self.processing_path)
                        queued_jobs = self._read_queue(self.queued_path)

                        job_index = -1
                        for i, j in enumerate(processing_jobs):
                            if j.get('id') == job_id:
                                job_index = i
                                break

                        if job_index == -1:
                            logger.warning(f"Job {job_id} disappeared from processing before retry move.")
                            return False

                        # Remove from processing and add back to queued (usually at the end for retry)
                        retry_job = processing_jobs.pop(job_index)
                        retry_job.update(job) # Apply updated attempts, status, error reason
                        queued_jobs.append(retry_job)

                        self._write_queue(self.processing_path, processing_jobs)
                        self._write_queue(self.queued_path, queued_jobs)
                        moved = True
                except (Timeout, Exception) as e:
                    logger.error(f"Error moving job {job_id} back to queue for retry: {e}")
                    return False
                return moved
            else:
                # Move to failed queue permanently
                logger.info(f"Job {job_id} failed permanently after {current_attempts + 1} attempts. Reason: {reason}")
                return self._move_job(job_id, self.processing_path, self.processing_lock_path,
                                      self.failed_path, self.failed_lock_path, 'failed', job.get('result_details', details)) # Pass accumulated details

        except (Timeout, Exception) as e:
            logger.error(f"Error during mark_job_failed for {job_id}: {e}")
            return False


    def mark_job_needs_review(self, job_id: str, reason: str, details: Optional[Dict] = None) -> bool:
        """Moves a job from processing to the needs_review queue."""
        job_details = {'review_reason': reason}
        if details:
            job_details.update(details)
        return self._move_job(job_id, self.processing_path, self.processing_lock_path,
                              self.review_path, self.review_lock_path, 'needs_review', job_details)


    def get_queue_stats(self) -> Dict[str, int]:
        """Returns the number of jobs in each queue."""
        stats = {}
        queues = {
            "queued": (self.queued_path, self.queued_lock_path),
            "processing": (self.processing_path, self.processing_lock_path),
            "completed": (self.completed_path, self.completed_lock_path),
            "failed": (self.failed_path, self.failed_lock_path),
            "needs_review": (self.review_path, self.review_lock_path),
        }
        for name, (path, lock_path) in queues.items():
            try:
                # Use a shorter timeout for stats reading to avoid blocking service
                with FileLock(lock_path, timeout=1):
                    jobs = self._read_queue(path)
                    stats[name] = len(jobs)
            except Timeout:
                 logger.warning(f"Could not acquire lock for {name} queue stats, returning -1.")
                 stats[name] = -1 # Indicate unavailable
            except Exception as e:
                 logger.error(f"Error reading stats for {name} queue: {e}")
                 stats[name] = -1
        return stats

    def check_stale_processing_jobs(self, stale_threshold_seconds: int = 3600) -> List[str]:
        """Finds jobs stuck in processing for too long."""
        stale_jobs = []
        try:
            with self._acquire_lock(self.processing_lock_path):
                processing_jobs = self._read_queue(self.processing_path)
                current_time = time.time()
                for job in processing_jobs:
                    start_time = job.get('start_processing_timestamp')
                    if start_time and (current_time - start_time) > stale_threshold_seconds:
                        stale_jobs.append(job.get('id', 'Unknown ID'))
                        logger.warning(f"Job {job.get('id', 'Unknown ID')} is stale (processing for over {stale_threshold_seconds}s).")
            return stale_jobs
        except (Timeout, Exception) as e:
            logger.error(f"Error checking for stale jobs: {e}")
            return [] # Return empty list on error


# Example Usage (optional)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        # Assumes config.yaml exists in parent directory
        cfg_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
        import yaml
        with open(cfg_path, 'r') as f:
            test_config = yaml.safe_load(f)

        qm = QueueManager(test_config)

        # Add a test job
        test_job = {"id": f"test_{int(time.time())}", "job_data": {"title": "Test Job", "company": "Test Inc", "apply_url": "http://example.com"}}
        qm.add_job(test_job)

        print("Initial Stats:", qm.get_queue_stats())

        # Process a job
        next_j = qm.get_next_job()
        if next_j:
            print(f"Processing job: {next_j['id']}")
            print("Stats after getting job:", qm.get_queue_stats())
            # Simulate completion
            qm.mark_job_complete(next_j['id'], {"result": "simulated success"})
            print(f"Stats after completing job:", qm.get_queue_stats())
        else:
            print("No job found in queue.")

        # Simulate failure
        fail_job = {"id": f"fail_{int(time.time())}", "job_data": {"title": "Fail Job", "company": "Fail Co", "apply_url": "http://example.com/fail"}}
        qm.add_job(fail_job)
        next_f = qm.get_next_job()
        if next_f:
            print(f"Processing job to fail: {next_f['id']}")
            qm.mark_job_failed(next_f['id'], "Simulated failure reason", retry=True, max_retries=1) # Retry once
            print(f"Stats after first failure (retry=True):", qm.get_queue_stats())
            # Get it again
            next_f_retry = qm.get_next_job()
            if next_f_retry and next_f_retry['id'] == next_f['id']:
                 print(f"Processing failed job again: {next_f_retry['id']}")
                 qm.mark_job_failed(next_f_retry['id'], "Simulated permanent failure", retry=False) # Fail permanently
                 print(f"Stats after permanent failure:", qm.get_queue_stats())
            else:
                 print("Failed to get job for retry.")


    except Exception as e:
        print(f"Error in QueueManager example: {e}")
        traceback.print_exc()
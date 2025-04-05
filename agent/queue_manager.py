# agent/queue_manager.py

import json
import os
import time
from typing import Dict, List, Any, Optional, Union

class QueueManager:
    """Manager for interacting with the job queue system."""
    
    def __init__(self, queue_dir: str = "queue_system"):
        self.queue_dir = os.path.abspath(queue_dir)
        self.queued_path = os.path.join(self.queue_dir, "queued.json")
        self.in_progress_path = os.path.join(self.queue_dir, "in_progress.json")
        self.applied_path = os.path.join(self.queue_dir, "applied.json")
        self.failed_path = os.path.join(self.queue_dir, "failed.json")
        self.manual_review_path = os.path.join(self.queue_dir, "manual_review.json")
        
        # Ensure all queue files exist
        self._initialize_queues()
    
    def _initialize_queues(self) -> None:
        """Initialize queue files if they don't exist."""
        os.makedirs(self.queue_dir, exist_ok=True)
        
        for path in [self.queued_path, self.in_progress_path, 
                     self.applied_path, self.failed_path, 
                     self.manual_review_path]:
            if not os.path.exists(path):
                with open(path, 'w') as f:
                    json.dump([], f)
    
    def _read_queue(self, file_path: str) -> List[Dict[str, Any]]:
        """Read and parse a queue file."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error reading queue file {file_path}: {str(e)}")
            return []
    
    def _write_queue(self, file_path: str, data: List[Dict[str, Any]]) -> bool:
        """Write data to a queue file."""
        try:
            # Create a temporary file and then rename to avoid corruption
            temp_path = f"{file_path}.tmp"
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # On Windows, we might need to remove the target file first
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
                    
            os.rename(temp_path, file_path)
            return True
        except Exception as e:
            print(f"Error writing to queue file {file_path}: {str(e)}")
            return False
    
    def get_next_job(self) -> Optional[Dict[str, Any]]:
        """Get the next job from the queue and move it to in_progress."""
        queued_jobs = self._read_queue(self.queued_path)
        
        if not queued_jobs:
            return None
        
        # Get the oldest job (first in the list)
        next_job = queued_jobs[0]
        
        # Remove from queued list
        queued_jobs.pop(0)
        self._write_queue(self.queued_path, queued_jobs)
        
        # Update the job status and timestamp
        next_job['status'] = 'in_progress'
        next_job['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        next_job['attempts'] = next_job.get('attempts', 0) + 1
        
        # Add to in_progress list
        in_progress_jobs = self._read_queue(self.in_progress_path)
        in_progress_jobs.append(next_job)
        self._write_queue(self.in_progress_path, in_progress_jobs)
        
        return next_job
    
    def mark_job_complete(self, job_id: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Mark a job as successfully completed (applied)."""
        return self._move_job(job_id, self.in_progress_path, self.applied_path, 
                             status='applied', details=details)
    
    def mark_job_failed(self, job_id: str, error: str, 
                       retry: bool = False) -> bool:
        """Mark a job as failed."""
        if retry:
            # Move back to queued for retry
            return self._move_job(job_id, self.in_progress_path, self.queued_path, 
                                 status='queued', 
                                 details={'error': error, 'last_error': error})
        else:
            # Move to failed queue
            return self._move_job(job_id, self.in_progress_path, self.failed_path, 
                                 status='failed', 
                                 details={'error': error})
    
    def mark_job_needs_review(self, job_id: str, reason: str) -> bool:
        """Mark a job as needing manual review."""
        return self._move_job(job_id, self.in_progress_path, self.manual_review_path, 
                             status='manual_review', 
                             details={'notes': reason})
    
    def _move_job(self, job_id: str, from_path: str, to_path: str, 
                 status: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """Move a job from one queue to another with status update."""
        from_queue = self._read_queue(from_path)
        to_queue = self._read_queue(to_path)
        
        # Find the job in the source queue
        job_index = None
        for i, job in enumerate(from_queue):
            if job.get('id') == job_id:
                job_index = i
                break
        
        if job_index is None:
            print(f"Job {job_id} not found in {from_path}")
            return False
        
        # Get the job and remove it from source queue
        job = from_queue.pop(job_index)
        
        # Update job details
        job['status'] = status
        job['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        if details:
            for key, value in details.items():
                job[key] = value
        
        # Add to destination queue
        to_queue.append(job)
        
        # Write both queues
        source_result = self._write_queue(from_path, from_queue)
        dest_result = self._write_queue(to_path, to_queue)
        
        return source_result and dest_result
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get statistics about all queues."""
        return {
            'queued': len(self._read_queue(self.queued_path)),
            'in_progress': len(self._read_queue(self.in_progress_path)),
            'applied': len(self._read_queue(self.applied_path)),
            'failed': len(self._read_queue(self.failed_path)),
            'manual_review': len(self._read_queue(self.manual_review_path))
        }
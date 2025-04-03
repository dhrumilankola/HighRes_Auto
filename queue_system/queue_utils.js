// queue_system/queue_utils.js

const fs = require('fs');
const path = require('path');

// Define paths for queue files
const QUEUE_DIR = path.join(process.cwd(), 'queue_system');
const QUEUED_PATH = path.join(QUEUE_DIR, 'queued.json');
const IN_PROGRESS_PATH = path.join(QUEUE_DIR, 'in_progress.json');
const APPLIED_PATH = path.join(QUEUE_DIR, 'applied.json');
const FAILED_PATH = path.join(QUEUE_DIR, 'failed.json');
const MANUAL_REVIEW_PATH = path.join(QUEUE_DIR, 'manual_review.json');

// Initialize queue files if they don't exist or are empty
const initializeQueues = () => {
  if (!fs.existsSync(QUEUE_DIR)) {
    fs.mkdirSync(QUEUE_DIR, { recursive: true });
  }
  
  const initFile = (filePath) => {
    if (
      !fs.existsSync(filePath) || 
      fs.readFileSync(filePath, 'utf8').trim() === ''
    ) {
      fs.writeFileSync(filePath, JSON.stringify([]));
    }
  };
  
  initFile(QUEUED_PATH);
  initFile(IN_PROGRESS_PATH);
  initFile(APPLIED_PATH);
  initFile(FAILED_PATH);
  initFile(MANUAL_REVIEW_PATH);
};

// Helper to read a queue file and return an array
const readQueue = (filePath) => {
  try {
    if (!fs.existsSync(filePath)) {
      // If file doesn't exist, initialize it and return an empty array
      fs.writeFileSync(filePath, JSON.stringify([]));
      return [];
    }
    const data = fs.readFileSync(filePath, 'utf8').trim();
    if (!data) {
      return [];
    }
    return JSON.parse(data);
  } catch (error) {
    console.error(`Error reading queue file ${filePath}:`, error);
    return [];
  }
};

// Helper to write to a queue file
const writeQueue = (filePath, data) => {
  try {
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
    return true;
  } catch (error) {
    console.error(`Error writing to queue file ${filePath}:`, error);
    return false;
  }
};

// Add a job to the queue
const addToQueue = (job) => {
  const queued = readQueue(QUEUED_PATH);
  const jobEntry = {
    id: job.id,
    job_data: job,
    status: 'queued',
    added_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    attempts: 0,
    error: null,
    notes: null
  };
  
  // Check if job already exists in any queue
  if (isJobInAnyQueue(job.id)) {
    return { success: false, message: 'Job already exists in queue' };
  }
  
  queued.push(jobEntry);
  if (writeQueue(QUEUED_PATH, queued)) {
    return { success: true, job: jobEntry };
  }
  return { success: false, message: 'Failed to write to queue' };
};

// Check if a job exists in any queue
const isJobInAnyQueue = (jobId) => {
  const queues = [
    readQueue(QUEUED_PATH),
    readQueue(IN_PROGRESS_PATH),
    readQueue(APPLIED_PATH),
    readQueue(FAILED_PATH),
    readQueue(MANUAL_REVIEW_PATH)
  ];
  
  return queues.some(queue => 
    queue.some(item => item.id === jobId)
  );
};

// Move a job from one queue to another
const moveJob = (jobId, fromPath, toPath, updates = {}) => {
  const fromQueue = readQueue(fromPath);
  const toQueue = readQueue(toPath);
  
  const jobIndex = fromQueue.findIndex(job => job.id === jobId);
  if (jobIndex === -1) {
    return { success: false, message: 'Job not found in source queue' };
  }
  
  const job = { ...fromQueue[jobIndex], ...updates, updated_at: new Date().toISOString() };
  fromQueue.splice(jobIndex, 1);
  toQueue.push(job);
  
  const writeFromSuccess = writeQueue(fromPath, fromQueue);
  const writeToSuccess = writeQueue(toPath, toQueue);
  
  if (writeFromSuccess && writeToSuccess) {
    return { success: true, job };
  }
  return { success: false, message: 'Failed to update queues' };
};

// Get all jobs with a specific status
const getJobsByStatus = (status) => {
    let result;
    switch (status) {
      case 'queued':
        result = readQueue(QUEUED_PATH);
        break;
      case 'in_progress':
        result = readQueue(IN_PROGRESS_PATH);
        break;
      case 'applied':
        result = readQueue(APPLIED_PATH);
        break;
      case 'failed':
        result = readQueue(FAILED_PATH);
        break;
      case 'manual_review':
        result = readQueue(MANUAL_REVIEW_PATH);
        break;
      case 'all':
        result = {
          queued: readQueue(QUEUED_PATH),
          in_progress: readQueue(IN_PROGRESS_PATH),
          applied: readQueue(APPLIED_PATH),
          failed: readQueue(FAILED_PATH),
          manual_review: readQueue(MANUAL_REVIEW_PATH)
        };
        break;
      default:
        result = [];
    }
    // Ensure that when not 'all', we return an array.
    if (status !== 'all' && !Array.isArray(result)) {
      console.error(`Expected an array for status "${status}" but got:`, result);
      result = [];
    }
    return result;
  };

// Update a job's status
const updateJobStatus = (jobId, newStatus, details = {}) => {
  // Determine current location of job
  let currentPath;
  let found = false;
  
  const queues = [
    { path: QUEUED_PATH, status: 'queued' },
    { path: IN_PROGRESS_PATH, status: 'in_progress' },
    { path: APPLIED_PATH, status: 'applied' },
    { path: FAILED_PATH, status: 'failed' },
    { path: MANUAL_REVIEW_PATH, status: 'manual_review' }
  ];
  
  for (const queue of queues) {
    const jobs = readQueue(queue.path);
    if (jobs.some(job => job.id === jobId)) {
      currentPath = queue.path;
      found = true;
      break;
    }
  }
  
  if (!found) {
    return { success: false, message: 'Job not found in any queue' };
  }
  
  // Determine target path based on new status
  let targetPath;
  switch (newStatus) {
    case 'queued':
      targetPath = QUEUED_PATH;
      break;
    case 'in_progress':
      targetPath = IN_PROGRESS_PATH;
      break;
    case 'applied':
      targetPath = APPLIED_PATH;
      break;
    case 'failed':
      targetPath = FAILED_PATH;
      break;
    case 'manual_review':
      targetPath = MANUAL_REVIEW_PATH;
      break;
    default:
      return { success: false, message: 'Invalid status' };
  }
  
  return moveJob(jobId, currentPath, targetPath, { 
    status: newStatus,
    ...details
  });
};

// Get job statistics
const getQueueStats = () => {
  return {
    queued: readQueue(QUEUED_PATH).length,
    in_progress: readQueue(IN_PROGRESS_PATH).length,
    applied: readQueue(APPLIED_PATH).length,
    failed: readQueue(FAILED_PATH).length,
    manual_review: readQueue(MANUAL_REVIEW_PATH).length
  };
};

// Initialize on module load
initializeQueues();

module.exports = {
  addToQueue,
  getJobsByStatus,
  updateJobStatus,
  getQueueStats,
  isJobInAnyQueue
};

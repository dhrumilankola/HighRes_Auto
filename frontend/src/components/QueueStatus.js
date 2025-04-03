// src/components/QueueStatus.js

'use client';

import React, { useEffect, useState } from 'react';
import { FaClipboardList, FaRocket, FaClock, FaCheck, FaTimes, FaExclamationTriangle } from 'react-icons/fa';

const QueueStatus = ({ selectedJobs, onSubmitQueue }) => {
  const [queueStats, setQueueStats] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch queue stats
  const fetchQueueStats = async () => {
    try {
      const response = await fetch('/api/queue');
      const data = await response.json();
      setQueueStats(data.queue_stats);
    } catch (error) {
      console.error('Error fetching queue stats:', error);
    }
  };

  // Fetch stats when component mounts
  useEffect(() => {
    fetchQueueStats();
    // Set up interval to refresh stats every 30 seconds
    const interval = setInterval(fetchQueueStats, 30000);
    return () => clearInterval(interval);
  }, []);

  // Handle queue submission
  const handleSubmit = async () => {
    setLoading(true);
    await onSubmitQueue(selectedJobs);
    await fetchQueueStats(); // Refresh stats after submission
    setLoading(false);
  };

  // Handle clearing the selection
  const handleClear = async () => {
    await onSubmitQueue([]);
    await fetchQueueStats();
  };

  if (selectedJobs.length === 0 && (!queueStats || Object.values(queueStats).every(val => val === 0))) {
    return null; // Don't show anything if no jobs are selected and queue is empty
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg p-4 z-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row justify-between items-center">
          <div className="flex flex-col mb-3 sm:mb-0">
            {selectedJobs.length > 0 && (
              <div className="flex items-center mb-2">
                <FaClipboardList className="h-5 w-5 text-blue-600 mr-2" />
                <span className="font-medium">
                  {selectedJobs.length} {selectedJobs.length === 1 ? 'job' : 'jobs'} selected
                </span>
                <span className="text-sm text-gray-500 ml-2">
                  Ready to add to queue
                </span>
              </div>
            )}
            
            {queueStats && (
              <div className="flex flex-wrap gap-3 text-sm">
                <div className="flex items-center">
                  <FaClock className="h-4 w-4 text-yellow-500 mr-1" />
                  <span>{queueStats.queued} queued</span>
                </div>
                <div className="flex items-center">
                  <FaRocket className="h-4 w-4 text-blue-500 mr-1" />
                  <span>{queueStats.in_progress} in progress</span>
                </div>
                <div className="flex items-center">
                  <FaCheck className="h-4 w-4 text-green-500 mr-1" />
                  <span>{queueStats.applied} applied</span>
                </div>
                <div className="flex items-center">
                  <FaTimes className="h-4 w-4 text-red-500 mr-1" />
                  <span>{queueStats.failed} failed</span>
                </div>
                <div className="flex items-center">
                  <FaExclamationTriangle className="h-4 w-4 text-orange-500 mr-1" />
                  <span>{queueStats.manual_review} need review</span>
                </div>
              </div>
            )}
          </div>
          
          {selectedJobs.length > 0 && (
            <div className="flex space-x-3">
              <button
                className="btn-secondary"
                onClick={handleClear}
                disabled={loading}
              >
                Clear Selection
              </button>
              <button
                onClick={handleSubmit}
                className="btn-primary"
                disabled={loading}
              >
                <FaRocket className="mr-2 h-4 w-4" />
                {loading ? 'Processing...' : 'Add to Queue'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default QueueStatus;
'use client';

import React from 'react';
import { FaClipboardList, FaRocket } from 'react-icons/fa';

const QueueStatus = ({ selectedJobs, onSubmitQueue }) => {
  if (selectedJobs.length === 0) {
    return null;
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg p-4 z-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row justify-between items-center">
          <div className="flex items-center mb-3 sm:mb-0">
            <FaClipboardList className="h-5 w-5 text-blue-600 mr-2" />
            <span className="font-medium">
              {selectedJobs.length} {selectedJobs.length === 1 ? 'job' : 'jobs'} selected
            </span>
            <span className="text-sm text-gray-500 ml-2">
              Ready to apply
            </span>
          </div>
          
          <div className="flex space-x-3">
            <button
              className="btn-secondary"
              onClick={() => onSubmitQueue([])}
            >
              Clear All
            </button>
            <button
              onClick={() => onSubmitQueue(selectedJobs)}
              className="btn-primary"
            >
              <FaRocket className="mr-2 h-4 w-4" />
              Start Applications
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default QueueStatus;
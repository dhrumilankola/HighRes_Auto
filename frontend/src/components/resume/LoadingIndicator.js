'use client';

import React from 'react';
import { FaSpinner, FaRobot } from 'react-icons/fa';

const LoadingIndicator = ({ message = 'Processing...' }) => {
  return (
    <div className="flex flex-col items-center justify-center p-8">
      <div className="mb-4 relative">
        <FaRobot className="text-blue-600 h-16 w-16" />
        <div className="absolute top-0 right-0 rounded-full bg-blue-100 p-1">
          <FaSpinner className="text-blue-600 h-6 w-6 animate-spin" />
        </div>
      </div>
      <h3 className="text-lg font-medium text-gray-900 mb-2">{message}</h3>
      <p className="text-sm text-gray-500 text-center max-w-md">
        Our AI is analyzing your resume. This may take a few moments as we extract and categorize all your information.
      </p>
    </div>
  );
};

export default LoadingIndicator;
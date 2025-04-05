'use client';

import React, { useState, useEffect } from 'react';
import { FaGithub, FaTwitter, FaLinkedin } from 'react-icons/fa';

const Footer = () => {
  const [queueCount, setQueueCount] = useState(0);

  // Fetch queue count from the backend API
  useEffect(() => {
    const fetchQueueCount = async () => {
      try {
        const response = await fetch('/api/queue');
        const data = await response.json();
        // Expecting data to have the shape:
        // { queue_stats: { queued, in_progress, applied, failed, manual_review }, total }
        setQueueCount(data.total || 0);
      } catch (error) {
        console.error('Error fetching queue count:', error);
      }
    };

    fetchQueueCount();
    // Refresh the count every 10 seconds
    const intervalId = setInterval(fetchQueueCount, 10000);
    return () => clearInterval(intervalId);
  }, []);

  return (
    <footer
      className="text-white py-6"
      style={{ backgroundColor: '#1B1C1D' }}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-center">
          <div className="mb-4 md:mb-0">
            <p className="text-center md:text-left">© {new Date().getFullYear()} HIGHRES. All rights reserved.</p>
            <p className="text-sm text-gray-200 text-center md:text-left">
              Automate your job applications with AI
            </p>
            {queueCount > 0 && (
              <p className="text-xs text-gray-300 text-center md:text-left">
                Active Queue Count: {queueCount}
              </p>
            )}
          </div>
          <div className="flex space-x-6">
            <a href="#" className="text-gray-200 hover:text-white">
              <FaGithub className="h-6 w-6" />
            </a>
            <a href="#" className="text-gray-200 hover:text-white">
              <FaTwitter className="h-6 w-6" />
            </a>
            <a href="#" className="text-gray-200 hover:text-white">
              <FaLinkedin className="h-6 w-6" />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
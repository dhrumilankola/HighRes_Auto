'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { FaRobot, FaBriefcase, FaClipboardList, FaFileAlt } from 'react-icons/fa';

const Header = () => {
  const pathname = usePathname();
  const [queueCount, setQueueCount] = useState(0);

  // Fetch queue count from the backend API
  useEffect(() => {
    const fetchQueueCount = async () => {
      try {
        const response = await fetch('/api/queue');
        const data = await response.json();
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
    <header className="shadow" style={{ backgroundColor: '#1B1C1D' }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              <FaRobot className="h-8 w-8" style={{ color: '#4E82EE' }} />
              <span className="ml-2 text-xl font-bold" style={{ color: '#FFFFFF' }}>
                HIGHRES
              </span>
            </div>
            <nav className="ml-6 flex space-x-8">
              <Link
                href="/"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  pathname === '/' 
                    ? 'border-[#4E82EE] text-white' 
                    : 'border-transparent text-gray-300 hover:text-[#9773CD] hover:border-[#9773CD]'
                }`}
              >
                <FaBriefcase className="mr-1" />
                Jobs
              </Link>
              <Link
                href="/queue"
                className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  pathname === '/queue'
                    ? 'border-[#4E82EE] text-white'
                    : 'border-transparent text-gray-300 hover:text-[#9773CD] hover:border-[#9773CD]'
                }`}
              >
                <FaClipboardList className="mr-1" />
                My Queue
                {queueCount > 0 && (
                  <span
                    className="ml-1 px-2 py-0.5 text-xs rounded-full"
                    style={{ backgroundColor: '#D96570', color: '#FFFFFF' }}
                  >
                    {queueCount}
                  </span>
                )}
              </Link>
              <Link href="/resume" className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                  pathname === '/resume'
                    ? 'border-[#4E82EE] text-white'
                    : 'border-transparent text-gray-300 hover:text-[#9773CD] hover:border-[#9773CD]'
                }`}
              >
                <FaClipboardList className="mr-1" />
                My Resume
              </Link>
            </nav>
          </div>
          <div className="flex items-center">
            <button
              type="button"
              className="px-4 py-2 rounded"
              style={{ backgroundColor: '#4E82EE', color: '#FFFFFF' }}
            >
              Get Started
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;

'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { FaRobot, FaBriefcase, FaClipboardList } from 'react-icons/fa';

const Header = () => {
  const pathname = usePathname();
  const [queueCount, setQueueCount] = useState(0);
  
  // Check if there are jobs in the queue
  useEffect(() => {
    try {
      const storedJobs = localStorage.getItem('queuedJobs');
      if (storedJobs) {
        const jobs = JSON.parse(storedJobs);
        setQueueCount(jobs.length);
      }
    } catch (error) {
      console.error('Error reading queue count:', error);
    }
  }, []);

  return (
    <header className="bg-white shadow">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              <FaRobot className="h-8 w-8 text-blue-600" />
              <span className="ml-2 text-xl font-bold text-gray-900">HIGHRES</span>
            </div>
            <nav className="ml-6 flex space-x-8">
              <Link href="/" className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                pathname === '/' ? 'border-blue-500 text-gray-900' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}>
                <FaBriefcase className="mr-1" />
                Jobs
              </Link>
              <Link href="/queue" className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                pathname === '/queue' ? 'border-blue-500 text-gray-900' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}>
                <FaClipboardList className="mr-1" />
                My Queue
                {queueCount > 0 && (
                  <span className="ml-1 px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-800">
                    {queueCount}
                  </span>
                )}
              </Link>
            </nav>
          </div>
          <div className="flex items-center">
            <button
              type="button"
              className="btn-primary"
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
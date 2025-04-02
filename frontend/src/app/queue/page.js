'use client';

import React, { useState, useEffect } from 'react';
import { FaSpinner, FaCheck, FaClock, FaExclamationTriangle, FaTimes } from 'react-icons/fa';

import Header from '../../components/Header';
import Footer from '../../components/Footer';

export default function QueuePage() {
  const [queuedJobs, setQueuedJobs] = useState([]);
  const [appliedJobs, setAppliedJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchQueuedJobs = async () => {
      try {
        // In a production app, this would be an API call
        // For now, we'll use localStorage as a mock backend
        const storedQueuedJobs = localStorage.getItem('queuedJobs');
        const storedAppliedJobs = localStorage.getItem('appliedJobs');
        
        if (storedQueuedJobs) {
          // Parse the stored jobs and add default status if not present
          const jobs = JSON.parse(storedQueuedJobs).map(job => ({
            ...job,
            status: job.status || 'Awaiting', // Default status is Awaiting
            statusMessage: job.statusMessage || 'Waiting to process',
          }));
          setQueuedJobs(jobs);
        }
        
        if (storedAppliedJobs) {
          setAppliedJobs(JSON.parse(storedAppliedJobs));
        }
      } catch (error) {
        console.error('Error fetching queued jobs:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchQueuedJobs();
  }, []);

  // Function to update job status (for demo purposes)
  const updateJobStatus = (jobId, newStatus, message = '') => {
    setQueuedJobs(prev => 
      prev.map(job => 
        job.id === jobId 
          ? { ...job, status: newStatus, statusMessage: message || job.statusMessage }
          : job
      )
    );
    
    // Save to localStorage
    localStorage.setItem('queuedJobs', JSON.stringify(
      queuedJobs.map(job => 
        job.id === jobId 
          ? { ...job, status: newStatus, statusMessage: message || job.statusMessage }
          : job
      )
    ));
  };

  // Function to move a job to applied list
  const moveToApplied = (jobId) => {
    const jobToMove = queuedJobs.find(job => job.id === jobId);
    if (!jobToMove) return;
    
    // Add to applied jobs
    const updatedAppliedJobs = [...appliedJobs, {...jobToMove, completedAt: new Date().toISOString()}];
    setAppliedJobs(updatedAppliedJobs);
    
    // Remove from queued jobs
    setQueuedJobs(prev => prev.filter(job => job.id !== jobId));
    
    // Update localStorage
    localStorage.setItem('appliedJobs', JSON.stringify(updatedAppliedJobs));
    localStorage.setItem('queuedJobs', JSON.stringify(queuedJobs.filter(job => job.id !== jobId)));
  };

  // Function to cancel a job
  const cancelJob = (jobId) => {
    updateJobStatus(jobId, 'Cancelled', 'Application cancelled by user');
  };

  // Function to simulate auto-applying for demo purposes
  const simulateAutoApply = () => {
    if (queuedJobs.length === 0) return;
    
    // Find the first Awaiting job
    const awaitingJob = queuedJobs.find(job => job.status === 'Awaiting');
    if (!awaitingJob) return; // No awaiting jobs
    
    // Set job to Applying
    updateJobStatus(awaitingJob.id, 'Applying', 'Bot is filling application form...');
    
    // Simulate process time
    setTimeout(() => {
      // 50% chance of success, 50% chance of needing interaction
      const needsInteraction = Math.random() > 0.5;
      
      if (needsInteraction) {
        updateJobStatus(
          awaitingJob.id, 
          'Human Required', 
          'This application requires human verification'
        );
        
        // Automatically process the next job without requiring button press
        setTimeout(() => simulateAutoApply(), 1000);
      } else {
        updateJobStatus(awaitingJob.id, 'Applied', 'Application submitted successfully');
        // Move to applied list after a short delay
        setTimeout(() => {
          moveToApplied(awaitingJob.id);
          
          // Automatically process the next job
          setTimeout(() => simulateAutoApply(), 1000);
        }, 1500);
      }
    }, 3000);
  };

  // For demo purposes, run the simulation when the page loads
  useEffect(() => {
    const hasAwaitingJobs = !loading && queuedJobs.some(job => job.status === 'Awaiting');
    
    // Only start auto-processing if there are awaiting jobs and no job is currently being applied
    if (hasAwaitingJobs && !queuedJobs.some(job => job.status === 'Applying')) {
      // Add a small delay before starting to process jobs
      const timer = setTimeout(() => {
        simulateAutoApply();
      }, 1000);
      
      return () => clearTimeout(timer);
    }
  }, [loading, queuedJobs]);

  // Status icon mapping
  const getStatusIcon = (status) => {
    switch (status) {
      case 'Applying':
        return <FaSpinner className="animate-spin text-blue-500" />;
      case 'Applied':
        return <FaCheck className="text-green-500" />;
      case 'Human Required':
        return <FaExclamationTriangle className="text-yellow-500" />;
      case 'Cancelled':
        return <FaTimes className="text-red-500" />;
      default:
        return <FaClock className="text-gray-500" />;
    }
  };

  // Status color mapping
  const getStatusColor = (status) => {
    switch (status) {
      case 'Applying':
        return 'bg-blue-100 text-blue-800';
      case 'Applied':
        return 'bg-green-100 text-green-800';
      case 'Human Required':
        return 'bg-yellow-100 text-yellow-800';
      case 'Cancelled':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Header />
        <main className="flex-grow flex justify-center items-center">
          <div className="flex items-center space-x-2">
            <FaSpinner className="animate-spin h-6 w-6 text-blue-500" />
            <span>Loading your application queue...</span>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />
      
      <main className="flex-grow">
        <div className="py-10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-gray-900 mb-2">Application Queue</h1>
              <p className="text-lg text-gray-600">
                Track the status of your automated job applications
              </p>
            </div>
            
            {/* Queue Section */}
            <div className="bg-white shadow overflow-hidden sm:rounded-lg mb-8">
              <div className="px-4 py-5 sm:px-6 flex justify-between items-center">
                <div>
                  <h2 className="text-lg font-medium text-gray-900">Active Queue</h2>
                  <p className="mt-1 text-sm text-gray-500">
                    Jobs currently in the application process
                    {queuedJobs.some(job => job.status === 'Applying') && (
                      <span className="ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        <FaSpinner className="animate-spin mr-1" />
                        Auto-Processing
                      </span>
                    )}
                  </p>
                </div>
                {queuedJobs.some(job => job.status === 'Awaiting') && !queuedJobs.some(job => job.status === 'Applying') && (
                  <button 
                    className="btn-primary"
                    onClick={simulateAutoApply}
                  >
                    Start Processing
                  </button>
                )}
              </div>
              
              {queuedJobs.length > 0 ? (
                <div className="border-t border-gray-200 divide-y divide-gray-200">
                  {queuedJobs.map(job => (
                    <div key={job.id} className="px-4 py-4 sm:px-6 hover:bg-gray-50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <div className="flex-shrink-0 mr-4">
                            {getStatusIcon(job.status)}
                          </div>
                          <div>
                            <h3 className="text-lg font-medium text-gray-900">{job.title}</h3>
                            <p className="text-sm text-gray-500">{job.company}</p>
                            <div className="mt-1 flex items-center">
                              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(job.status)}`}>
                                {job.status}
                              </span>
                              <span className="ml-2 text-sm text-gray-500">{job.statusMessage}</span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex space-x-2">
                          {job.status === 'Human Required' && (
                            <a 
                              href={job.job_url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="btn-secondary text-xs"
                            >
                              Complete Manually
                            </a>
                          )}
                          
                          {job.status !== 'Cancelled' && job.status !== 'Applied' && (
                            <button 
                              onClick={() => cancelJob(job.id)}
                              className="bg-red-600 hover:bg-red-700 text-white py-1 px-3 rounded text-xs"
                            >
                              Cancel
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="px-4 py-12 text-center border-t border-gray-200">
                  <p className="text-gray-500">No jobs currently in the queue</p>
                  <a href="/" className="mt-2 inline-block text-blue-600 hover:text-blue-800">
                    Browse available jobs
                  </a>
                </div>
              )}
            </div>
            
            {/* Applied Jobs Section */}
            <div className="bg-white shadow overflow-hidden sm:rounded-lg">
              <div className="px-4 py-5 sm:px-6">
                <h2 className="text-lg font-medium text-gray-900">Applied Jobs</h2>
                <p className="mt-1 text-sm text-gray-500">
                  Applications that have been successfully submitted
                </p>
              </div>
              
              {appliedJobs.length > 0 ? (
                <div className="border-t border-gray-200 divide-y divide-gray-200">
                  {appliedJobs.map(job => (
                    <div key={job.id} className="px-4 py-4 sm:px-6 hover:bg-gray-50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <div className="flex-shrink-0 mr-4">
                            <FaCheck className="text-green-500" />
                          </div>
                          <div>
                            <h3 className="text-lg font-medium text-gray-900">{job.title}</h3>
                            <p className="text-sm text-gray-500">{job.company}</p>
                            <div className="mt-1 flex items-center">
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                Applied
                              </span>
                              <span className="ml-2 text-sm text-gray-500">
                                {new Date(job.completedAt).toLocaleDateString()}
                              </span>
                            </div>
                          </div>
                        </div>
                        
                        <a 
                          href={job.job_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 text-sm"
                        >
                          View Job
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="px-4 py-12 text-center border-t border-gray-200">
                  <p className="text-gray-500">No jobs have been applied to yet</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  );
}
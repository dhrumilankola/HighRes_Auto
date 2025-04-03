// src/app/queue/page.js

'use client';

import React, { useState, useEffect } from 'react';
import { FaSpinner, FaClock, FaRocket, FaCheck, FaTimes, FaExclamationTriangle } from 'react-icons/fa';
import Header from '../../components/Header';
import Footer from '../../components/Footer';

export default function QueuePage() {
  const [jobs, setJobs] = useState({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/queue/jobs?status=${activeTab}`);
      const data = await response.json();
      setJobs(data.jobs);
    } catch (error) {
      console.error('Error fetching jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    // Refresh data every 10 seconds
    const interval = setInterval(fetchJobs, 10000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'queued':
        return <FaClock className="text-yellow-500" />;
      case 'in_progress':
        return <FaRocket className="text-blue-500" />;
      case 'applied':
        return <FaCheck className="text-green-500" />;
      case 'failed':
        return <FaTimes className="text-red-500" />;
      case 'manual_review':
        return <FaExclamationTriangle className="text-orange-500" />;
      default:
        return null;
    }
  };

  const renderJobList = (jobList, status) => {
    if (!jobList || jobList.length === 0) {
      return (
        <div className="text-center py-10 text-gray-500">
          No jobs with status: {status}
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {jobList.map((job) => (
          <div key={job.id} className="card p-4">
            <div className="flex justify-between items-start mb-2">
              <h3 className="text-lg font-semibold text-gray-900 truncate">
                {job.job_data.title}
              </h3>
              <div className="badge flex items-center gap-1">
                {getStatusIcon(job.status)}
                <span>{job.status}</span>
              </div>
            </div>
            <div className="text-sm text-gray-500 mb-2">
              {job.job_data.company} • {job.job_data.location}
            </div>
            <div className="text-xs text-gray-400 mb-2">
              Added: {new Date(job.added_at).toLocaleString()}
            </div>
            {job.attempts > 0 && (
              <div className="text-xs text-gray-400 mb-2">
                Attempts: {job.attempts}
              </div>
            )}
            {job.error && (
              <div className="text-xs text-red-500 mt-2 border-t pt-2">
                Error: {job.error}
              </div>
            )}
            {job.notes && (
              <div className="text-xs text-blue-500 mt-2 border-t pt-2">
                Notes: {job.notes}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />
      
      <main className="flex-grow">
        <div className="py-10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-gray-900 mb-4">
                Application Queue
              </h1>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                Monitor and manage your automated job applications
              </p>
            </div>

            <div className="flex justify-center mb-6 border-b">
              <button
                className={`px-4 py-2 font-medium ${activeTab === 'all' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
                onClick={() => setActiveTab('all')}
              >
                All
              </button>
              <button
                className={`px-4 py-2 font-medium ${activeTab === 'queued' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
                onClick={() => setActiveTab('queued')}
              >
                Queued
              </button>
              <button
                className={`px-4 py-2 font-medium ${activeTab === 'in_progress' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
                onClick={() => setActiveTab('in_progress')}
              >
                In Progress
              </button>
              <button
                className={`px-4 py-2 font-medium ${activeTab === 'applied' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
                onClick={() => setActiveTab('applied')}
              >
                Applied
              </button>
              <button
                className={`px-4 py-2 font-medium ${activeTab === 'failed' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
                onClick={() => setActiveTab('failed')}
              >
                Failed
              </button>
              <button
                className={`px-4 py-2 font-medium ${activeTab === 'manual_review' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500'}`}
                onClick={() => setActiveTab('manual_review')}
              >
                Needs Review
              </button>
            </div>

            {loading ? (
              <div className="flex justify-center items-center py-12">
                <FaSpinner className="animate-spin h-8 w-8 text-blue-500" />
                <span className="ml-2 text-gray-600">Loading jobs...</span>
              </div>
            ) : (
              <>
                {activeTab === 'all' ? (
                  <>
                    {Object.keys(jobs).length === 0 ? (
                      <div className="text-center py-10 text-gray-500">
                        No jobs in any queue
                      </div>
                    ) : (
                      <>
                        {jobs.queued?.length > 0 && (
                          <div className="mb-8">
                            <h2 className="text-xl font-semibold mb-4">Queued Jobs</h2>
                            {renderJobList(jobs.queued, 'queued')}
                          </div>
                        )}
                        
                        {jobs.in_progress?.length > 0 && (
                          <div className="mb-8">
                            <h2 className="text-xl font-semibold mb-4">In Progress</h2>
                            {renderJobList(jobs.in_progress, 'in_progress')}
                          </div>
                        )}
                        
                        {jobs.applied?.length > 0 && (
                          <div className="mb-8">
                            <h2 className="text-xl font-semibold mb-4">Applied</h2>
                            {renderJobList(jobs.applied, 'applied')}
                          </div>
                        )}
                        
                        {jobs.failed?.length > 0 && (
                          <div className="mb-8">
                            <h2 className="text-xl font-semibold mb-4">Failed</h2>
                            {renderJobList(jobs.failed, 'failed')}
                          </div>
                        )}
                        
                        {jobs.manual_review?.length > 0 && (
                          <div className="mb-8">
                            <h2 className="text-xl font-semibold mb-4">Needs Review</h2>
                            {renderJobList(jobs.manual_review, 'manual_review')}
                          </div>
                        )}
                      </>
                    )}
                  </>
                ) : (
                  renderJobList(jobs, activeTab)
                )}
              </>
            )}
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  );
}
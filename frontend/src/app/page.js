'use client';

import React, { useState, useEffect } from 'react';
import { FaBriefcase, FaRobot, FaCheckCircle } from 'react-icons/fa';

import Header from '../components/Header';
import Footer from '../components/Footer';
import JobList from '../components/JobList';
import QueueStatus from '../components/QueueStatus';

export default function Home() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedJobs, setSelectedJobs] = useState([]);
  const [queueSubmitted, setQueueSubmitted] = useState(false);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        // Fetch jobs from our API endpoint
        const response = await fetch('/api/jobs');
        const data = await response.json();
        
        // If API fails, try direct fetch from public directory as fallback
        if (!data || data.length === 0) {
          console.log('API endpoint returned no jobs, trying direct fetch...');
          const directResponse = await fetch('/job_data/tech_jobs.json');
          const directData = await directResponse.json();
          
          if (directData && directData.length > 0) {
            console.log(`Successfully loaded ${directData.length} jobs directly from public folder`);
            setJobs(directData);
          } else {
            console.error('Could not load any jobs from any source');
          }
        } else {
          console.log(`Successfully loaded ${data.length} jobs from API`);
          setJobs(data);
        }
      } catch (error) {
        console.error('Error fetching jobs:', error);
        
        // Last resort - try direct fetch
        try {
          const directResponse = await fetch('/job_data/tech_jobs.json');
          const directData = await directResponse.json();
          setJobs(directData);
        } catch (fallbackError) {
          console.error('Fallback fetch also failed:', fallbackError);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchJobs();
  }, []);

  const handleSelectJob = (job) => {
    setSelectedJobs(prev => {
      // Check if job is already selected
      const isSelected = prev.some(selectedJob => selectedJob.id === job.id);
      
      if (isSelected) {
        // Remove job from selected jobs
        return prev.filter(selectedJob => selectedJob.id !== job.id);
      } else {
        // Add job to selected jobs
        return [...prev, job];
      }
    });
  };

  const handleSubmitQueue = async (jobsToQueue) => {
    if (jobsToQueue.length === 0) {
      // If clearing the queue
      setSelectedJobs([]);
      setQueueSubmitted(false);
      return;
    }

    try {
      setLoading(true);
      // In production, you'd submit to a real API endpoint
      const response = await fetch('/api/queue', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ jobs: jobsToQueue }),
      });
      
      if (response.ok) {
        setQueueSubmitted(true);
        
        // In a real app, you'd likely redirect to a queue status page
        // For now, we'll just clear the selected jobs after a delay
        setTimeout(() => {
          setSelectedJobs([]);
          setQueueSubmitted(false);
          setLoading(false);
        }, 1500);
      } else {
        console.error('Error submitting jobs to queue:', await response.text());
        setLoading(false);
      }
    } catch (error) {
      console.error('Error submitting jobs to queue:', error);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />
      
      <main className="flex-grow">
        <div className="py-10">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-8">
              <h1 className="text-3xl font-bold text-gray-900 mb-4">
                <FaBriefcase className="inline-block mr-2 mb-1" />
                Job Application Automation
              </h1>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                Browse available jobs, select the ones you're interested in, and let our 
                <FaRobot className="inline-block mx-1 text-blue-600" /> 
                automate the application process for you.
              </p>
            </div>

            {queueSubmitted ? (
              <div className="bg-green-50 border border-green-200 rounded-lg p-6 mb-8 text-center">
                <FaCheckCircle className="mx-auto h-12 w-12 text-green-500 mb-3" />
                <h2 className="text-lg font-medium text-green-800 mb-2">Jobs Successfully Added to Queue!</h2>
                <p className="text-green-700">
                  Our system will now start applying to these jobs on your behalf.
                </p>
              </div>
            ) : (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
                <h2 className="text-lg font-medium text-blue-800 mb-2">How It Works</h2>
                <ol className="list-decimal list-inside text-blue-700 space-y-2">
                  <li>Browse through available job listings below</li>
                  <li>Select jobs you're interested in by clicking "Apply"</li>
                  <li>Review your selection and click "Start Applications"</li>
                  <li>Our automated system will apply on your behalf</li>
                </ol>
              </div>
            )}
            
            <div className="mb-6">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-900">
                  Available Jobs
                </h2>
                <div className="text-sm text-gray-500">
                  Showing {jobs.length} jobs
                </div>
              </div>
            </div>

            <JobList 
              jobs={jobs} 
              loading={loading} 
              onSelectJob={handleSelectJob}
              selectedJobs={selectedJobs}
            />
          </div>
        </div>
      </main>

      <QueueStatus 
        selectedJobs={selectedJobs} 
        onSubmitQueue={handleSubmitQueue} 
      />
      
      <Footer />
    </div>
  );
}
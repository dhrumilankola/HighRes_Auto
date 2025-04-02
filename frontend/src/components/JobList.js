'use client';

import React, { useState } from 'react';
import JobCard from './JobCard';
import { FaSearch, FaFilter, FaSortAmountDown, FaSpinner } from 'react-icons/fa';

const JobList = ({ jobs, loading, onSelectJob, selectedJobs }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('recent');

  const filteredJobs = jobs.filter(job => {
    // Search filter
    const matchesSearch = 
      job.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      job.company.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (job.content_snippet && job.content_snippet.toLowerCase().includes(searchTerm.toLowerCase()));
    
    // Category filter
    if (filter === 'all') return matchesSearch;
    if (filter === 'remote' && job.is_remote) return matchesSearch;
    if (filter === 'selected' && selectedJobs.some(selectedJob => selectedJob.id === job.id)) return matchesSearch;
    if (filter === 'tech' && job.tech_stack && job.tech_stack.length > 0) return matchesSearch;

    return false;
  });

  // Sort jobs
  const sortedJobs = [...filteredJobs].sort((a, b) => {
    if (sort === 'recent') {
      const dateA = a.posted_at ? new Date(a.posted_at) : new Date(0);
      const dateB = b.posted_at ? new Date(b.posted_at) : new Date(0);
      return dateB - dateA;
    } else if (sort === 'alphabetical') {
      return a.title.localeCompare(b.title);
    } else if (sort === 'company') {
      return a.company.localeCompare(b.company);
    }
    return 0;
  });

  const handleFilterChange = (e) => {
    setFilter(e.target.value);
  };

  const handleSortChange = (e) => {
    setSort(e.target.value);
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <FaSpinner className="animate-spin h-8 w-8 text-blue-500" />
        <span className="ml-2 text-gray-600">Loading jobs...</span>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 p-4 bg-white rounded-lg shadow">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <FaSearch className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              className="pl-10 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm h-10"
              placeholder="Search jobs by title, company, or description"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          
          <div className="flex gap-2">
            <div className="relative inline-flex">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <FaFilter className="h-4 w-4 text-gray-400" />
              </div>
              <select
                className="pl-10 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm h-10"
                value={filter}
                onChange={handleFilterChange}
              >
                <option value="all">All Jobs</option>
                <option value="remote">Remote Only</option>
                <option value="selected">Selected</option>
                <option value="tech">With Tech Stack</option>
              </select>
            </div>
            
            <div className="relative inline-flex">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <FaSortAmountDown className="h-4 w-4 text-gray-400" />
              </div>
              <select
                className="pl-10 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm h-10"
                value={sort}
                onChange={handleSortChange}
              >
                <option value="recent">Most Recent</option>
                <option value="alphabetical">Alphabetical</option>
                <option value="company">By Company</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {sortedJobs.length > 0 ? (
          sortedJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onSelect={onSelectJob}
              isSelected={selectedJobs.some(selectedJob => selectedJob.id === job.id)}
            />
          ))
        ) : (
          <div className="col-span-3 py-12 text-center text-gray-500">
            <p className="text-lg">No jobs match your current filters</p>
            <p className="text-sm mt-2">Try adjusting your search or filter criteria</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default JobList;
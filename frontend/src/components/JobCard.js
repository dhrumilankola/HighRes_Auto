'use client';

import React from 'react';
import { FaBuilding, FaMapMarkerAlt, FaClock, FaCode } from 'react-icons/fa';
import { formatDistanceToNow } from 'date-fns';

const JobCard = ({ job, onSelect, isSelected }) => {
  const postedAtDate = job.posted_at ? new Date(job.posted_at) : null;
  const timeAgo = postedAtDate ? formatDistanceToNow(postedAtDate, { addSuffix: true }) : 'Date unknown';

  return (
    <div className="card">
      <div className="p-5">
        <div className="flex justify-between items-start">
          <h3 className="text-lg font-semibold text-gray-900 mb-1 truncate">{job.title}</h3>
          <div className={`badge ${isSelected ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
            {isSelected ? 'Selected' : 'Available'}
          </div>
        </div>
        
        <div className="flex items-center text-sm text-gray-500 mb-2">
          <FaBuilding className="mr-1" />
          <span className="mr-3">{job.company}</span>
          {job.location && (
            <>
              <FaMapMarkerAlt className="mr-1" />
              <span>{job.location}</span>
            </>
          )}
        </div>
        
        <p className="text-sm text-gray-600 line-clamp-3 mb-3">
          {job.content_snippet || 'No description available'}
        </p>
        
        <div className="flex flex-wrap gap-2 mb-3">
          {job.tech_stack && job.tech_stack.slice(0, 5).map((tech, index) => (
            <span key={index} className="badge-primary flex items-center">
              <FaCode className="mr-1 h-3 w-3" />
              {tech}
            </span>
          ))}
          {job.tech_stack && job.tech_stack.length > 5 && (
            <span className="badge-secondary">+{job.tech_stack.length - 5} more</span>
          )}
        </div>
        
        <div className="flex justify-between items-center">
          <div className="text-xs text-gray-500 flex items-center">
            <FaClock className="mr-1" />
            {timeAgo}
          </div>
          
          <button
            onClick={() => onSelect(job)}
            className={`${
              isSelected 
                ? 'bg-red-600 hover:bg-red-700 focus:ring-red-200' 
                : 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-200'
            } px-3 py-1.5 text-xs text-white rounded-md focus:outline-none focus:ring-2 transition-colors`}
          >
            {isSelected ? 'Remove' : 'Apply'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default JobCard;
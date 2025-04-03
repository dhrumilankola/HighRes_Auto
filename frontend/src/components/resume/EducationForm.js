'use client';

import React, { useState } from 'react';
import { FaGraduationCap, FaSave, FaPlus, FaTrash } from 'react-icons/fa';

const EducationForm = ({ data, onSave }) => {
  const [education, setEducation] = useState(data || [
    {
      degree: '',
      university: '',
      dates: '',
      gpa: '',
      location: ''
    }
  ]);

  const handleChange = (index, field, value) => {
    const updatedEducation = [...education];
    updatedEducation[index] = {
      ...updatedEducation[index],
      [field]: value
    };
    setEducation(updatedEducation);
  };

  const handleAddEducation = () => {
    setEducation([
      ...education,
      {
        degree: '',
        university: '',
        dates: '',
        gpa: '',
        location: ''
      }
    ]);
  };

  const handleRemoveEducation = (index) => {
    if (education.length === 1) {
      alert('You must have at least one education entry');
      return;
    }
    
    const updatedEducation = education.filter((_, i) => i !== index);
    setEducation(updatedEducation);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(education);
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center justify-center">
          <FaGraduationCap className="mr-2" />
          Education
        </h2>
        <p className="mt-1 text-gray-600">
          Add your educational background, including degrees, institutions, and dates.
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        {education.map((edu, index) => (
          <div key={index} className="bg-gray-50 p-4 rounded-md mb-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-900">Education #{index + 1}</h3>
              <button
                type="button"
                onClick={() => handleRemoveEducation(index)}
                className="inline-flex items-center p-1 border border-transparent rounded-full text-red-600 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
              >
                <FaTrash />
              </button>
            </div>
            
            <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
              <div>
                <label htmlFor={`degree-${index}`} className="block text-sm font-medium text-gray-700">
                  Degree
                </label>
                <input
                  type="text"
                  id={`degree-${index}`}
                  value={edu.degree}
                  onChange={(e) => handleChange(index, 'degree', e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., BS in Computer Science"
                  required
                />
              </div>

              <div>
                <label htmlFor={`university-${index}`} className="block text-sm font-medium text-gray-700">
                  University
                </label>
                <input
                  type="text"
                  id={`university-${index}`}
                  value={edu.university}
                  onChange={(e) => handleChange(index, 'university', e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., University of California"
                  required
                />
              </div>

              <div>
                <label htmlFor={`dates-${index}`} className="block text-sm font-medium text-gray-700">
                  Dates
                </label>
                <input
                  type="text"
                  id={`dates-${index}`}
                  value={edu.dates}
                  onChange={(e) => handleChange(index, 'dates', e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., 2018 - 2022"
                  required
                />
              </div>

              <div>
                <label htmlFor={`gpa-${index}`} className="block text-sm font-medium text-gray-700">
                  GPA
                </label>
                <input
                  type="text"
                  id={`gpa-${index}`}
                  value={edu.gpa}
                  onChange={(e) => handleChange(index, 'gpa', e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., 3.8/4.0"
                />
              </div>

              <div>
                <label htmlFor={`location-${index}`} className="block text-sm font-medium text-gray-700">
                  Location
                </label>
                <input
                  type="text"
                  id={`location-${index}`}
                  value={edu.location}
                  onChange={(e) => handleChange(index, 'location', e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., Los Angeles, CA"
                />
              </div>
            </div>
          </div>
        ))}
        
        <div className="flex justify-between">
          <button
            type="button"
            onClick={handleAddEducation}
            className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaPlus className="mr-2" />
            Add Education
          </button>
          
          <button
            type="submit"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaSave className="mr-2" />
            Save Education
          </button>
        </div>
      </form>
    </div>
  );
};

export default EducationForm;
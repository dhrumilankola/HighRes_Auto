'use client';

import React, { useState } from 'react';
import { FaBriefcase, FaSave, FaPlus, FaTrash, FaListUl } from 'react-icons/fa';

const ExperienceForm = ({ data, onSave }) => {
  const [experience, setExperience] = useState(data || [
    {
      title: '',
      company: '',
      dates: '',
      bullets: ['']
    }
  ]);

  const handleChange = (index, field, value) => {
    const updatedExperience = [...experience];
    updatedExperience[index] = {
      ...updatedExperience[index],
      [field]: value
    };
    setExperience(updatedExperience);
  };

  const handleBulletChange = (expIndex, bulletIndex, value) => {
    const updatedExperience = [...experience];
    updatedExperience[expIndex].bullets[bulletIndex] = value;
    setExperience(updatedExperience);
  };

  const handleAddBullet = (expIndex) => {
    const updatedExperience = [...experience];
    updatedExperience[expIndex].bullets.push('');
    setExperience(updatedExperience);
  };

  const handleRemoveBullet = (expIndex, bulletIndex) => {
    if (experience[expIndex].bullets.length === 1) {
      alert('You must have at least one bullet point');
      return;
    }
    
    const updatedExperience = [...experience];
    updatedExperience[expIndex].bullets = updatedExperience[expIndex].bullets.filter((_, i) => i !== bulletIndex);
    setExperience(updatedExperience);
  };

  const handleAddExperience = () => {
    setExperience([
      ...experience,
      {
        title: '',
        company: '',
        dates: '',
        bullets: ['']
      }
    ]);
  };

  const handleRemoveExperience = (index) => {
    if (experience.length === 1) {
      alert('You must have at least one experience entry');
      return;
    }
    
    const updatedExperience = experience.filter((_, i) => i !== index);
    setExperience(updatedExperience);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(experience);
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center justify-center">
          <FaBriefcase className="mr-2" />
          Work Experience
        </h2>
        <p className="mt-1 text-gray-600">
          Add your work experience, including job titles, companies, and key responsibilities.
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        {experience.map((exp, expIndex) => (
          <div key={expIndex} className="bg-gray-50 p-4 rounded-md mb-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-900">Experience #{expIndex + 1}</h3>
              <button
                type="button"
                onClick={() => handleRemoveExperience(expIndex)}
                className="inline-flex items-center p-1 border border-transparent rounded-full text-red-600 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
              >
                <FaTrash />
              </button>
            </div>
            
            <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2 mb-4">
              <div>
                <label htmlFor={`title-${expIndex}`} className="block text-sm font-medium text-gray-700">
                  Job Title
                </label>
                <input
                  type="text"
                  id={`title-${expIndex}`}
                  value={exp.title}
                  onChange={(e) => handleChange(expIndex, 'title', e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., Software Engineer"
                  required
                />
              </div>

              <div>
                <label htmlFor={`company-${expIndex}`} className="block text-sm font-medium text-gray-700">
                  Company
                </label>
                <input
                  type="text"
                  id={`company-${expIndex}`}
                  value={exp.company}
                  onChange={(e) => handleChange(expIndex, 'company', e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., Acme Inc."
                  required
                />
              </div>

              <div className="sm:col-span-2">
                <label htmlFor={`dates-${expIndex}`} className="block text-sm font-medium text-gray-700">
                  Dates
                </label>
                <input
                  type="text"
                  id={`dates-${expIndex}`}
                  value={exp.dates}
                  onChange={(e) => handleChange(expIndex, 'dates', e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., January 2020 - Present"
                  required
                />
              </div>
            </div>
            
            <div className="mb-4">
              <div className="flex items-center mb-2">
                <FaListUl className="mr-2 text-gray-500" />
                <h4 className="text-sm font-medium text-gray-700">Responsibilities & Achievements</h4>
              </div>
              
              {exp.bullets.map((bullet, bulletIndex) => (
                <div key={bulletIndex} className="flex items-start mt-2">
                  <div className="w-full">
                    <div className="flex items-center">
                      <span className="text-gray-500 mr-2">•</span>
                      <input
                        type="text"
                        value={bullet}
                        onChange={(e) => handleBulletChange(expIndex, bulletIndex, e.target.value)}
                        className="mt-0 block w-full border-0 border-b border-gray-300 focus:ring-0 focus:border-blue-500 sm:text-sm"
                        placeholder="Add an accomplishment or responsibility"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => handleRemoveBullet(expIndex, bulletIndex)}
                        className="ml-2 text-red-500 hover:text-red-700"
                      >
                        <FaTrash size={12} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              
              <button
                type="button"
                onClick={() => handleAddBullet(expIndex)}
                className="mt-3 inline-flex items-center px-2 py-1 border border-gray-300 shadow-sm text-xs font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <FaPlus className="mr-1" size={10} />
                Add Bullet
              </button>
            </div>
          </div>
        ))}
        
        <div className="flex justify-between">
          <button
            type="button"
            onClick={handleAddExperience}
            className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaPlus className="mr-2" />
            Add Experience
          </button>
          
          <button
            type="submit"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaSave className="mr-2" />
            Save Experience
          </button>
        </div>
      </form>
    </div>
  );
};

export default ExperienceForm;
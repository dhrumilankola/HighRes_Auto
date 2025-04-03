'use client';

import React, { useState } from 'react';
import { FaCogs, FaSave } from 'react-icons/fa';

const SkillsForm = ({ data, onSave }) => {
  const [skills, setSkills] = useState(data || {
    languages: [],
    frameworks: [],
    cloud: [],
    databases: [],
    tools: []
  });

  const handleSkillChange = (category, value) => {
    // Convert comma-separated string to array of trimmed values
    const skillArray = value.split(',').map(skill => skill.trim()).filter(skill => skill !== '');
    
    setSkills(prevSkills => ({
      ...prevSkills,
      [category]: skillArray
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(skills);
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center justify-center">
          <FaCogs className="mr-2" />
          Skills
        </h2>
        <p className="mt-1 text-gray-600">
          Add your technical skills and competencies in various categories.
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-gray-50 p-4 rounded-md">
          <div className="grid grid-cols-1 gap-y-6 gap-x-4">
            <div>
              <label htmlFor="languages" className="block text-sm font-medium text-gray-700">
                Programming Languages
              </label>
              <input
                type="text"
                id="languages"
                value={skills.languages.join(', ')}
                onChange={(e) => handleSkillChange('languages', e.target.value)}
                className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                placeholder="e.g., JavaScript, Python, Java"
              />
              <p className="mt-1 text-xs text-gray-500">
                Separate skills with commas
              </p>
            </div>

            <div>
              <label htmlFor="frameworks" className="block text-sm font-medium text-gray-700">
                Frameworks & Libraries
              </label>
              <input
                type="text"
                id="frameworks"
                value={skills.frameworks.join(', ')}
                onChange={(e) => handleSkillChange('frameworks', e.target.value)}
                className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                placeholder="e.g., React, Node.js, Django"
              />
              <p className="mt-1 text-xs text-gray-500">
                Separate skills with commas
              </p>
            </div>

            <div>
              <label htmlFor="cloud" className="block text-sm font-medium text-gray-700">
                Cloud Services
              </label>
              <input
                type="text"
                id="cloud"
                value={skills.cloud.join(', ')}
                onChange={(e) => handleSkillChange('cloud', e.target.value)}
                className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                placeholder="e.g., AWS, Azure, Google Cloud"
              />
              <p className="mt-1 text-xs text-gray-500">
                Separate skills with commas
              </p>
            </div>

            <div>
              <label htmlFor="databases" className="block text-sm font-medium text-gray-700">
                Databases
              </label>
              <input
                type="text"
                id="databases"
                value={skills.databases.join(', ')}
                onChange={(e) => handleSkillChange('databases', e.target.value)}
                className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                placeholder="e.g., MongoDB, PostgreSQL, MySQL"
              />
              <p className="mt-1 text-xs text-gray-500">
                Separate skills with commas
              </p>
            </div>

            <div>
              <label htmlFor="tools" className="block text-sm font-medium text-gray-700">
                Tools & Technologies
              </label>
              <input
                type="text"
                id="tools"
                value={skills.tools.join(', ')}
                onChange={(e) => handleSkillChange('tools', e.target.value)}
                className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                placeholder="e.g., Git, Docker, Kubernetes"
              />
              <p className="mt-1 text-xs text-gray-500">
                Separate skills with commas
              </p>
            </div>
          </div>
        </div>
        
        <div className="flex justify-end">
          <button
            type="submit"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaSave className="mr-2" />
            Save Skills
          </button>
        </div>
      </form>
    </div>
  );
};

export default SkillsForm;
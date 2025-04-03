'use client';

import React, { useState } from 'react';
import { FaCode, FaSave, FaPlus, FaTrash } from 'react-icons/fa';

const ProjectsForm = ({ data, onSave }) => {
  const [projects, setProjects] = useState(data || [
    {
      name: '',
      technologies: [],
      description: '',
      link: ''
    }
  ]);

  const handleChange = (index, field, value) => {
    const updatedProjects = [...projects];
    updatedProjects[index] = {
      ...updatedProjects[index],
      [field]: value
    };
    setProjects(updatedProjects);
  };

  const handleTechnologiesChange = (index, value) => {
    const technologies = value.split(',').map(tech => tech.trim()).filter(tech => tech !== '');
    
    const updatedProjects = [...projects];
    updatedProjects[index].technologies = technologies;
    setProjects(updatedProjects);
  };

  const handleAddProject = () => {
    setProjects([
      ...projects,
      {
        name: '',
        technologies: [],
        description: '',
        link: ''
      }
    ]);
  };

  const handleRemoveProject = (index) => {
    if (projects.length === 1) {
      alert('You must have at least one project entry');
      return;
    }
    
    const updatedProjects = projects.filter((_, i) => i !== index);
    setProjects(updatedProjects);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(projects);
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center justify-center">
          <FaCode className="mr-2" />
          Projects
        </h2>
        <p className="mt-1 text-gray-600">
          Add your notable projects, including technologies used and descriptions.
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        {projects.map((project, index) => (
          <div key={index} className="bg-gray-50 p-4 rounded-md mb-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-medium text-gray-900">Project #{index + 1}</h3>
              <button
                type="button"
                onClick={() => handleRemoveProject(index)}
                className="inline-flex items-center p-1 border border-transparent rounded-full text-red-600 hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
              >
                <FaTrash />
              </button>
            </div>
            
            <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label htmlFor={`name-${index}`} className="block text-sm font-medium text-gray-700">
                  Project Name
                </label>
                <input
                  type="text"
                  id={`name-${index}`}
                  value={project.name}
                  onChange={(e) => handleChange(index, 'name', e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., E-commerce Website"
                  required
                />
              </div>

              <div className="sm:col-span-2">
                <label htmlFor={`technologies-${index}`} className="block text-sm font-medium text-gray-700">
                  Technologies Used
                </label>
                <input
                  type="text"
                  id={`technologies-${index}`}
                  value={project.technologies.join(', ')}
                  onChange={(e) => handleTechnologiesChange(index, e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., React.js, Node.js, MongoDB (comma separated)"
                  required
                />
                <p className="mt-1 text-xs text-gray-500">
                  Separate technologies with commas
                </p>
              </div>

              <div className="sm:col-span-2">
                <label htmlFor={`description-${index}`} className="block text-sm font-medium text-gray-700">
                  Project Description
                </label>
                <textarea
                  id={`description-${index}`}
                  value={project.description}
                  onChange={(e) => handleChange(index, 'description', e.target.value)}
                  rows={3}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="Briefly describe what the project does and your role in it"
                  required
                />
              </div>

              <div className="sm:col-span-2">
                <label htmlFor={`link-${index}`} className="block text-sm font-medium text-gray-700">
                  Project Link
                </label>
                <input
                  type="text"
                  id={`link-${index}`}
                  value={project.link}
                  onChange={(e) => handleChange(index, 'link', e.target.value)}
                  className="mt-1 focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md"
                  placeholder="e.g., https://github.com/username/project"
                />
              </div>
            </div>
          </div>
        ))}
        
        <div className="flex justify-between">
          <button
            type="button"
            onClick={handleAddProject}
            className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaPlus className="mr-2" />
            Add Project
          </button>
          
          <button
            type="submit"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaSave className="mr-2" />
            Save Projects
          </button>
        </div>
      </form>
    </div>
  );
};

export default ProjectsForm;
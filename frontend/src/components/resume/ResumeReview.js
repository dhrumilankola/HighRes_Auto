'use client';

import React, { useState } from 'react';
import { FaCheck, FaDownload, FaSave, FaEdit } from 'react-icons/fa';

const ResumeReview = ({ data, onSave }) => {
  const [isExpanded, setIsExpanded] = useState({
    personal: false,
    education: false,
    experience: false,
    projects: false,
    skills: false,
    honors: false,
    predefined: false
  });

  const toggleSection = (section) => {
    setIsExpanded(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const handleExportJSON = () => {
    // Create a blob with the JSON data
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    
    // Create a URL for the blob
    const url = URL.createObjectURL(blob);
    
    // Create a temporary anchor element and trigger the download
    const a = document.createElement('a');
    a.href = url;
    a.download = 'resume.json';
    document.body.appendChild(a);
    a.click();
    
    // Clean up
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center justify-center">
          <FaCheck className="mr-2" />
          Resume Review
        </h2>
        <p className="mt-1 text-gray-600">
          Review your resume information. Click each section to expand and check details.
        </p>
      </div>
      
      <div className="space-y-6">
        {/* Personal Information Section */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div 
            className="px-4 py-5 sm:px-6 cursor-pointer hover:bg-gray-50 flex justify-between items-center" 
            onClick={() => toggleSection('personal')}
          >
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">Personal Information</h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                Contact details and professional summary
              </p>
            </div>
            <span className="text-blue-500">
              {isExpanded.personal ? 'Collapse' : 'Expand'}
            </span>
          </div>
          
          {isExpanded.personal && (
            <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
              <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
                <div className="sm:col-span-1">
                  <dt className="text-sm font-medium text-gray-500">Full Name</dt>
                  <dd className="mt-1 text-sm text-gray-900">
                    {data.personal_info.first_name} {data.personal_info.last_name}
                  </dd>
                </div>
                <div className="sm:col-span-1">
                  <dt className="text-sm font-medium text-gray-500">Email</dt>
                  <dd className="mt-1 text-sm text-gray-900">{data.personal_info.email}</dd>
                </div>
                <div className="sm:col-span-1">
                  <dt className="text-sm font-medium text-gray-500">Phone</dt>
                  <dd className="mt-1 text-sm text-gray-900">{data.personal_info.phone}</dd>
                </div>
                <div className="sm:col-span-1">
                  <dt className="text-sm font-medium text-gray-500">LinkedIn</dt>
                  <dd className="mt-1 text-sm text-gray-900">{data.personal_info.linkedin || 'N/A'}</dd>
                </div>
                <div className="sm:col-span-1">
                  <dt className="text-sm font-medium text-gray-500">Portfolio</dt>
                  <dd className="mt-1 text-sm text-gray-900">{data.personal_info.portfolio || 'N/A'}</dd>
                </div>
                <div className="sm:col-span-2">
                  <dt className="text-sm font-medium text-gray-500">Professional Summary</dt>
                  <dd className="mt-1 text-sm text-gray-900">{data.summary}</dd>
                </div>
              </dl>
            </div>
          )}
        </div>

        {/* Education Section */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div 
            className="px-4 py-5 sm:px-6 cursor-pointer hover:bg-gray-50 flex justify-between items-center" 
            onClick={() => toggleSection('education')}
          >
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">Education</h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                {data.education.length} {data.education.length === 1 ? 'entry' : 'entries'}
              </p>
            </div>
            <span className="text-blue-500">
              {isExpanded.education ? 'Collapse' : 'Expand'}
            </span>
          </div>
          
          {isExpanded.education && (
            <div className="border-t border-gray-200">
              {data.education.map((edu, index) => (
                <div key={index} className="px-4 py-5 sm:px-6 border-b border-gray-200 last:border-b-0">
                  <h4 className="text-md font-medium text-gray-900 mb-2">{edu.degree}</h4>
                  <dl className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2">
                    <div className="sm:col-span-1">
                      <dt className="text-sm font-medium text-gray-500">University</dt>
                      <dd className="mt-1 text-sm text-gray-900">{edu.university}</dd>
                    </div>
                    <div className="sm:col-span-1">
                      <dt className="text-sm font-medium text-gray-500">Dates</dt>
                      <dd className="mt-1 text-sm text-gray-900">{edu.dates}</dd>
                    </div>
                    <div className="sm:col-span-1">
                      <dt className="text-sm font-medium text-gray-500">GPA</dt>
                      <dd className="mt-1 text-sm text-gray-900">{edu.gpa || 'N/A'}</dd>
                    </div>
                    <div className="sm:col-span-1">
                      <dt className="text-sm font-medium text-gray-500">Location</dt>
                      <dd className="mt-1 text-sm text-gray-900">{edu.location || 'N/A'}</dd>
                    </div>
                  </dl>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Experience Section */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div 
            className="px-4 py-5 sm:px-6 cursor-pointer hover:bg-gray-50 flex justify-between items-center" 
            onClick={() => toggleSection('experience')}
          >
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">Work Experience</h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                {data.experience.length} {data.experience.length === 1 ? 'position' : 'positions'}
              </p>
            </div>
            <span className="text-blue-500">
              {isExpanded.experience ? 'Collapse' : 'Expand'}
            </span>
          </div>
          
          {isExpanded.experience && (
            <div className="border-t border-gray-200">
              {data.experience.map((exp, index) => (
                <div key={index} className="px-4 py-5 sm:px-6 border-b border-gray-200 last:border-b-0">
                  <h4 className="text-md font-medium text-gray-900 mb-1">{exp.title}</h4>
                  <p className="text-sm text-gray-600 mb-2">{exp.company} • {exp.dates}</p>
                  
                  <ul className="mt-2 space-y-1">
                    {exp.bullets.map((bullet, bulletIndex) => (
                      <li key={bulletIndex} className="text-sm text-gray-900 flex">
                        <span className="text-gray-500 mr-2">•</span>
                        <span>{bullet}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Projects Section */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div 
            className="px-4 py-5 sm:px-6 cursor-pointer hover:bg-gray-50 flex justify-between items-center" 
            onClick={() => toggleSection('projects')}
          >
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">Projects</h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                {data.projects.length} {data.projects.length === 1 ? 'project' : 'projects'}
              </p>
            </div>
            <span className="text-blue-500">
              {isExpanded.projects ? 'Collapse' : 'Expand'}
            </span>
          </div>
          
          {isExpanded.projects && (
            <div className="border-t border-gray-200">
              {data.projects.map((project, index) => (
                <div key={index} className="px-4 py-5 sm:px-6 border-b border-gray-200 last:border-b-0">
                  <h4 className="text-md font-medium text-gray-900 mb-2">{project.name}</h4>
                  <dl className="grid grid-cols-1 gap-x-4 gap-y-2">
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Technologies</dt>
                      <dd className="mt-1 text-sm text-gray-900">
                        {project.technologies.join(', ')}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Description</dt>
                      <dd className="mt-1 text-sm text-gray-900">{project.description}</dd>
                    </div>
                    {project.link && (
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Link</dt>
                        <dd className="mt-1 text-sm text-gray-900">
                          <a href={project.link} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800">
                            {project.link}
                          </a>
                        </dd>
                      </div>
                    )}
                  </dl>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Skills Section */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div 
            className="px-4 py-5 sm:px-6 cursor-pointer hover:bg-gray-50 flex justify-between items-center" 
            onClick={() => toggleSection('skills')}
          >
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">Skills</h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                Technical skills and competencies
              </p>
            </div>
            <span className="text-blue-500">
              {isExpanded.skills ? 'Collapse' : 'Expand'}
            </span>
          </div>
          
          {isExpanded.skills && (
            <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
              <dl className="grid grid-cols-1 gap-x-4 gap-y-4">
                {Object.entries(data.skills).map(([category, skillList]) => (
                  <div key={category} className="sm:col-span-1">
                    <dt className="text-sm font-medium text-gray-500 capitalize">
                      {category.replace(/_/g, ' ')}
                    </dt>
                    <dd className="mt-1 text-sm text-gray-900">
                      {skillList.length > 0 ? skillList.join(', ') : 'None listed'}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>

        {/* Honors Section */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div 
            className="px-4 py-5 sm:px-6 cursor-pointer hover:bg-gray-50 flex justify-between items-center" 
            onClick={() => toggleSection('honors')}
          >
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">Honors & Awards</h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                {data.honors.length} {data.honors.length === 1 ? 'honor' : 'honors'} listed
              </p>
            </div>
            <span className="text-blue-500">
              {isExpanded.honors ? 'Collapse' : 'Expand'}
            </span>
          </div>
          
          {isExpanded.honors && (
            <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
              {data.honors.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {data.honors.map((honor, index) => (
                    <li key={index} className="text-sm text-gray-900 flex">
                      <span className="text-gray-500 mr-2">•</span>
                      <span>{honor}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-gray-500">No honors or awards added.</p>
              )}
            </div>
          )}
        </div>

        {/* Predefined Answers Section */}
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <div 
            className="px-4 py-5 sm:px-6 cursor-pointer hover:bg-gray-50 flex justify-between items-center" 
            onClick={() => toggleSection('predefined')}
          >
            <div>
              <h3 className="text-lg leading-6 font-medium text-gray-900">Predefined Answers</h3>
              <p className="mt-1 max-w-2xl text-sm text-gray-500">
                Default responses to common application questions
              </p>
            </div>
            <span className="text-blue-500">
              {isExpanded.predefined ? 'Collapse' : 'Expand'}
            </span>
          </div>
          
          {isExpanded.predefined && (
            <div className="border-t border-gray-200 px-4 py-5 sm:px-6">
              <dl className="grid grid-cols-1 gap-x-4 gap-y-4">
                {Object.entries(data.predefined_answers).map(([question, answer]) => (
                  <div key={question} className="sm:col-span-1">
                    <dt className="text-sm font-medium text-gray-500">{question}</dt>
                    <dd className="mt-1 text-sm text-gray-900">{answer || 'Not specified'}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>
        
        <div className="flex justify-between mt-8">
          <button
            type="button"
            onClick={handleExportJSON}
            className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaDownload className="mr-2" />
            Export as JSON
          </button>
          
          <button
            type="button"
            onClick={onSave}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaSave className="mr-2" />
            Save Resume
          </button>
        </div>
      </div>
    </div>
  );
};

export default ResumeReview;
'use client';

import React, { useState } from 'react';
import { FaFileUpload, FaUser, FaGraduationCap, FaBriefcase, FaCode, FaCogs, FaMedal, FaCheck } from 'react-icons/fa';

import Header from '../../components/Header';
import Footer from '../../components/Footer';
import FileUpload from '../../components/resume/FileUpload';
import PersonalInfoForm from '../../components/resume/PersonalInfoForm';
import EducationForm from '../../components/resume/EducationForm';
import ExperienceForm from '../../components/resume/ExperienceForm';
import ProjectsForm from '../../components/resume/ProjectsForm';
import SkillsForm from '../../components/resume/SkillsForm';
import HonorsForm from '../../components/resume/HonorsForm';
import PredefinedAnswersForm from '../../components/resume/PredefinedAnswersForm';
import ResumeReview from '../../components/resume/ResumeReview';

const steps = [
  { id: 'upload', title: 'Upload Resume', icon: <FaFileUpload /> },
  { id: 'personal', title: 'Personal Information', icon: <FaUser /> },
  { id: 'education', title: 'Education', icon: <FaGraduationCap /> },
  { id: 'experience', title: 'Experience', icon: <FaBriefcase /> },
  { id: 'projects', title: 'Projects', icon: <FaCode /> },
  { id: 'skills', title: 'Skills', icon: <FaCogs /> },
  { id: 'honors', title: 'Honors', icon: <FaMedal /> },
  { id: 'predefined', title: 'Predefined Answers', icon: <FaCheck /> },
  { id: 'review', title: 'Review', icon: <FaCheck /> }
];

export default function ResumePage() {
  const [currentStep, setCurrentStep] = useState(0);
  const [resumeData, setResumeData] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [parsedResume, setParsedResume] = useState(null);

  const handleResumeUpload = async (file) => {
    setIsUploading(true);
    
    try {
      // Create FormData for file upload
      const formData = new FormData();
      formData.append('resume', file);
      
      // In a real app, you would send this to your API endpoint
      // For now, we'll simulate a successful response
      
      // This would be the API call
      /*
      const response = await fetch('/api/parse-resume', {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        throw new Error('Failed to parse resume');
      }
      
      const data = await response.json();
      */
      
      // Simulate API response delay
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      // For demo purposes, use a template structure
      // In production, this would come from your backend parser
      const parsedData = {
        personal_info: {
          first_name: "",
          last_name: "",
          email: "",
          phone: "",
          linkedin: "",
          portfolio: ""
        },
        summary: "",
        education: [
          {
            degree: "",
            university: "",
            dates: "",
            gpa: "",
            location: ""
          }
        ],
        experience: [
          {
            title: "",
            company: "",
            dates: "",
            bullets: [""]
          }
        ],
        skills: {
          languages: [],
          frameworks: [],
          cloud: [],
          databases: [],
          tools: []
        },
        projects: [
          {
            name: "",
            technologies: [],
            description: "",
            link: ""
          }
        ],
        honors: [],
        predefined_answers: {
          "Will you require sponsorship now or in the future?": "No",
          "Are you able to work right now/do you have work authorization?": "Yes",
          "Do you agree to be part of the talent community?": "Yes",
          "Have you been referred?": "No",
          "Gender": "",
          "Pronouns": "",
          "Are you Hispanic/Latino?": "No",
          "Ethnicity": "",
          "Are you a veteran?": "No"
        }
      };
      
      setParsedResume(parsedData);
      setCurrentStep(1); // Move to the next step
    } catch (error) {
      console.error('Error parsing resume:', error);
      alert('Failed to parse resume. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const updateResumeData = (section, data) => {
    setParsedResume(prevData => ({
      ...prevData,
      [section]: data
    }));
  };

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
      // Scroll to top when changing steps
      window.scrollTo(0, 0);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
      // Scroll to top when changing steps
      window.scrollTo(0, 0);
    }
  };

  const handleSaveResume = async () => {
    try {
      // In a real app, you would send this to your API endpoint
      // For now, we'll simulate a successful save
      
      // This would be the API call
      /*
      const response = await fetch('/api/save-resume', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(parsedResume),
      });
      
      if (!response.ok) {
        throw new Error('Failed to save resume');
      }
      */
      
      // Save to localStorage for demo purposes
      localStorage.setItem('userResume', JSON.stringify(parsedResume));
      
      alert('Resume saved successfully!');
      // Redirect to the home page or another appropriate page
      window.location.href = '/';
    } catch (error) {
      console.error('Error saving resume:', error);
      alert('Failed to save resume. Please try again.');
    }
  };

  const renderStepContent = () => {
    switch (steps[currentStep].id) {
      case 'upload':
        return <FileUpload onUpload={handleResumeUpload} isLoading={isUploading} />;
      case 'personal':
        return <PersonalInfoForm data={parsedResume.personal_info} summary={parsedResume.summary} onSave={(data, summary) => {
          updateResumeData('personal_info', data);
          updateResumeData('summary', summary);
        }} />;
      case 'education':
        return <EducationForm data={parsedResume.education} onSave={(data) => updateResumeData('education', data)} />;
      case 'experience':
        return <ExperienceForm data={parsedResume.experience} onSave={(data) => updateResumeData('experience', data)} />;
      case 'projects':
        return <ProjectsForm data={parsedResume.projects} onSave={(data) => updateResumeData('projects', data)} />;
      case 'skills':
        return <SkillsForm data={parsedResume.skills} onSave={(data) => updateResumeData('skills', data)} />;
      case 'honors':
        return <HonorsForm data={parsedResume.honors} onSave={(data) => updateResumeData('honors', data)} />;
      case 'predefined':
        return <PredefinedAnswersForm data={parsedResume.predefined_answers} onSave={(data) => updateResumeData('predefined_answers', data)} />;
      case 'review':
        return <ResumeReview data={parsedResume} onSave={handleSaveResume} />;
      default:
        return <div>Step not found</div>;
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
                My Resume
              </h1>
              <p className="text-xl text-gray-600 max-w-3xl mx-auto">
                Upload your resume and review the parsed information to ensure your job applications have the correct details.
              </p>
            </div>

            {/* Progress Steps */}
            <div className="mb-8">
              <div className="hidden sm:block">
                <div className="border-b border-gray-200">
                  <nav className="-mb-px flex justify-between">
                    {steps.map((step, index) => (
                      <button
                        key={step.id}
                        className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm ${
                          index === currentStep
                            ? 'border-blue-500 text-blue-600'
                            : index < currentStep
                            ? 'border-green-500 text-green-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                        }`}
                        onClick={() => index <= Math.max(currentStep, 1) && setCurrentStep(index)}
                        disabled={index > Math.max(currentStep, 1)}
                      >
                        <span className="flex items-center">
                          <span className="mr-2">{step.icon}</span>
                          {step.title}
                        </span>
                      </button>
                    ))}
                  </nav>
                </div>
              </div>
              
              {/* Mobile Step Indicator */}
              <div className="sm:hidden">
                <p className="text-sm font-medium text-gray-500">
                  Step {currentStep + 1} of {steps.length}: {steps[currentStep].title}
                </p>
              </div>
            </div>
            
            {/* Step Content */}
            <div className="bg-white shadow sm:rounded-lg">
              <div className="px-4 py-5 sm:p-6">
                {renderStepContent()}
              </div>
            </div>
            
            {/* Navigation Buttons */}
            {currentStep > 0 && (
              <div className="mt-6 flex justify-between">
                <button
                  type="button"
                  onClick={handlePrevious}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  Previous
                </button>
                {currentStep < steps.length - 1 && (
                  <button
                    type="button"
                    onClick={handleNext}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                  >
                    Next
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
      
      <Footer />
    </div>
  );
}
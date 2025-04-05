// src/components/resume/FileUpload.js
'use client';

import React, { useState, useRef } from 'react';
import { FaFileUpload, FaSpinner } from 'react-icons/fa';
import LoadingIndicator from './LoadingIndicator';

const FileUpload = ({ onUpload, isLoading }) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const fileInputRef = useRef(null);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      handleFile(file);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      handleFile(file);
    }
  };

  const handleFile = (file) => {
    const validTypes = [
      'application/pdf',
      'text/plain',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ];
    if (!validTypes.includes(file.type)) {
      alert('Please upload a valid resume file (PDF, DOC, DOCX, or TXT)');
      return;
    }
    setSelectedFile(file);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!selectedFile) {
      alert('Please select a file to upload');
      return;
    }
    onUpload(selectedFile);
  };

  const openFileSelector = () => {
    fileInputRef.current.click();
  };

  if (isLoading) {
    return <LoadingIndicator message="Parsing your resume with AI..." />;
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900">Upload Your Resume</h2>
        <p className="mt-1 text-gray-600">
          Upload your resume to get started. We accept PDF, DOC, DOCX, and TXT files.
        </p>
      </div>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div
          className={`mt-2 flex justify-center px-6 pt-5 pb-6 border-2 border-dashed rounded-md ${
            dragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <div className="space-y-1 text-center">
            <FaFileUpload className="mx-auto h-12 w-12 text-gray-400" />
            <div className="flex text-sm text-gray-600">
              <label
                htmlFor="file-upload"
                className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none"
              >
                <span onClick={openFileSelector}>Upload a file</span>
                <input
                  id="file-upload"
                  name="file-upload"
                  type="file"
                  className="sr-only"
                  ref={fileInputRef}
                  onChange={handleChange}
                  accept=".pdf,.doc,.docx,.txt"
                />
              </label>
              <p className="pl-1">or drag and drop</p>
            </div>
            <p className="text-xs text-gray-500">PDF, DOC, DOCX, or TXT up to 10MB</p>
          </div>
        </div>
        {selectedFile && (
          <div className="bg-gray-50 p-4 rounded-md">
            <p className="text-sm font-medium text-gray-900">Selected file:</p>
            <p className="text-sm text-gray-600">{selectedFile.name}</p>
          </div>
        )}
        <div className="flex justify-center">
          <button
            type="submit"
            className="inline-flex items-center px-4 py-2 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            disabled={!selectedFile || isLoading}
          >
            {isLoading ? (
              <>
                <FaSpinner className="animate-spin mr-2" />
                Parsing Resume...
              </>
            ) : (
              'Parse Resume with AI'
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default FileUpload;

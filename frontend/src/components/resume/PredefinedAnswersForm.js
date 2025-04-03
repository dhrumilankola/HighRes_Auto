'use client';

import React, { useState } from 'react';
import { FaCheck, FaSave } from 'react-icons/fa';

const PredefinedAnswersForm = ({ data, onSave }) => {
  const [answers, setAnswers] = useState(data || {
    "Will you require sponsorship now or in the future?": "No",
    "Are you able to work right now/do you have work authorization?": "Yes",
    "Do you agree to be part of the talent community?": "Yes",
    "Have you been referred?": "No",
    "Gender": "",
    "Pronouns": "",
    "Are you Hispanic/Latino?": "No",
    "Ethnicity": "",
    "Are you a veteran?": "No"
  });

  const handleChange = (question, value) => {
    setAnswers(prev => ({
      ...prev,
      [question]: value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(answers);
  };

  // Define option sets for different question types
  const yesNoOptions = ["Yes", "No", "Prefer not to say"];
  const genderOptions = ["Male", "Female", "Non-binary", "Prefer not to say", "Other"];
  const pronounOptions = ["He/Him", "She/Her", "They/Them", "Prefer not to say", "Other"];
  const ethnicityOptions = [
    "Asian/South Asian",
    "Black/African American",
    "Hispanic/Latino",
    "Native American/Alaska Native",
    "Native Hawaiian/Pacific Islander",
    "White/Caucasian",
    "Two or more races",
    "Prefer not to say",
    "Other"
  ];

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center justify-center">
          <FaCheck className="mr-2" />
          Predefined Answers
        </h2>
        <p className="mt-1 text-gray-600">
          Set up default answers to common application questions to speed up the process.
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-gray-50 p-4 rounded-md">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">
                Will you require sponsorship now or in the future?
              </label>
              <div className="mt-2 space-x-4">
                {yesNoOptions.map(option => (
                  <label key={option} className="inline-flex items-center">
                    <input
                      type="radio"
                      name="sponsorship"
                      value={option}
                      checked={answers["Will you require sponsorship now or in the future?"] === option}
                      onChange={() => handleChange("Will you require sponsorship now or in the future?", option)}
                      className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300"
                    />
                    <span className="ml-2 text-sm text-gray-700">{option}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Are you able to work right now/do you have work authorization?
              </label>
              <div className="mt-2 space-x-4">
                {yesNoOptions.map(option => (
                  <label key={option} className="inline-flex items-center">
                    <input
                      type="radio"
                      name="authorization"
                      value={option}
                      checked={answers["Are you able to work right now/do you have work authorization?"] === option}
                      onChange={() => handleChange("Are you able to work right now/do you have work authorization?", option)}
                      className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300"
                    />
                    <span className="ml-2 text-sm text-gray-700">{option}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Do you agree to be part of the talent community?
              </label>
              <div className="mt-2 space-x-4">
                {yesNoOptions.map(option => (
                  <label key={option} className="inline-flex items-center">
                    <input
                      type="radio"
                      name="talent-community"
                      value={option}
                      checked={answers["Do you agree to be part of the talent community?"] === option}
                      onChange={() => handleChange("Do you agree to be part of the talent community?", option)}
                      className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300"
                    />
                    <span className="ml-2 text-sm text-gray-700">{option}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Have you been referred?
              </label>
              <div className="mt-2 space-x-4">
                {yesNoOptions.map(option => (
                  <label key={option} className="inline-flex items-center">
                    <input
                      type="radio"
                      name="referred"
                      value={option}
                      checked={answers["Have you been referred?"] === option}
                      onChange={() => handleChange("Have you been referred?", option)}
                      className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300"
                    />
                    <span className="ml-2 text-sm text-gray-700">{option}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Gender
              </label>
              <select
                value={answers["Gender"]}
                onChange={(e) => handleChange("Gender", e.target.value)}
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
              >
                <option value="">Select gender...</option>
                {genderOptions.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Pronouns
              </label>
              <select
                value={answers["Pronouns"]}
                onChange={(e) => handleChange("Pronouns", e.target.value)}
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
              >
                <option value="">Select pronouns...</option>
                {pronounOptions.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Are you Hispanic/Latino?
              </label>
              <div className="mt-2 space-x-4">
                {yesNoOptions.map(option => (
                  <label key={option} className="inline-flex items-center">
                    <input
                      type="radio"
                      name="hispanic"
                      value={option}
                      checked={answers["Are you Hispanic/Latino?"] === option}
                      onChange={() => handleChange("Are you Hispanic/Latino?", option)}
                      className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300"
                    />
                    <span className="ml-2 text-sm text-gray-700">{option}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Ethnicity
              </label>
              <select
                value={answers["Ethnicity"]}
                onChange={(e) => handleChange("Ethnicity", e.target.value)}
                className="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm rounded-md"
              >
                <option value="">Select ethnicity...</option>
                {ethnicityOptions.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700">
                Are you a veteran?
              </label>
              <div className="mt-2 space-x-4">
                {yesNoOptions.map(option => (
                  <label key={option} className="inline-flex items-center">
                    <input
                      type="radio"
                      name="veteran"
                      value={option}
                      checked={answers["Are you a veteran?"] === option}
                      onChange={() => handleChange("Are you a veteran?", option)}
                      className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300"
                    />
                    <span className="ml-2 text-sm text-gray-700">{option}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        </div>
        
        <div className="flex justify-end">
          <button
            type="submit"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaSave className="mr-2" />
            Save Predefined Answers
          </button>
        </div>
      </form>
    </div>
  );
};

export default PredefinedAnswersForm;
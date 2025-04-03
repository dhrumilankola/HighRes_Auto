'use client';

import React, { useState } from 'react';
import { FaMedal, FaSave, FaPlus, FaTrash } from 'react-icons/fa';

const HonorsForm = ({ data, onSave }) => {
  const [honors, setHonors] = useState(data || []);
  const [newHonor, setNewHonor] = useState('');

  const handleAddHonor = () => {
    if (!newHonor.trim()) {
      alert('Please enter an honor or award');
      return;
    }
    
    setHonors([...honors, newHonor.trim()]);
    setNewHonor('');
  };

  const handleRemoveHonor = (index) => {
    const updatedHonors = honors.filter((_, i) => i !== index);
    setHonors(updatedHonors);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(honors);
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center justify-center">
          <FaMedal className="mr-2" />
          Honors & Awards
        </h2>
        <p className="mt-1 text-gray-600">
          Add any honors, awards, or recognitions you've received.
        </p>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-gray-50 p-4 rounded-md">
          <div className="flex items-start mb-4">
            <div className="w-full">
              <label htmlFor="new-honor" className="block text-sm font-medium text-gray-700 mb-1">
                Add Honor/Award
              </label>
              <div className="flex">
                <input
                  type="text"
                  id="new-honor"
                  value={newHonor}
                  onChange={(e) => setNewHonor(e.target.value)}
                  className="focus:ring-blue-500 focus:border-blue-500 block w-full shadow-sm sm:text-sm border-gray-300 rounded-md rounded-r-none"
                  placeholder="e.g., Dean's List, Hackathon Winner"
                />
                <button
                  type="button"
                  onClick={handleAddHonor}
                  className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md rounded-l-none text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
                >
                  <FaPlus className="mr-2" />
                  Add
                </button>
              </div>
            </div>
          </div>
          
          {honors.length === 0 ? (
            <p className="text-gray-500 text-center py-4">No honors or awards added yet.</p>
          ) : (
            <ul className="divide-y divide-gray-200">
              {honors.map((honor, index) => (
                <li key={index} className="py-3 flex justify-between items-center">
                  <span className="text-gray-800">{honor}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveHonor(index)}
                    className="text-red-500 hover:text-red-700"
                  >
                    <FaTrash size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        
        <div className="flex justify-end">
          <button
            type="submit"
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <FaSave className="mr-2" />
            Save Honors & Awards
          </button>
        </div>
      </form>
    </div>
  );
};

export default HonorsForm;
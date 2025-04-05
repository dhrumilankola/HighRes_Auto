// src/utils/GeminiAPI.js
export const processResume = async (file) => {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/parse-resume', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to parse resume');
    }

    const data = await response.json();
    return data.resumeData;
  } catch (error) {
    console.error('Error processing resume:', error);
    throw error;
  }
};

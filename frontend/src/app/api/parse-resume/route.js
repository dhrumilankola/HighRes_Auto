// src/app/api/parse-resume/route.js
import { NextResponse } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import { join } from 'path';
import PDFParser from 'pdf2json';

/**
 * Parses resume text using the Gemini API.
 *
 * @param {string} resumeText - The extracted resume text.
 * @returns {Promise<Object>} - Parsed resume data.
 */
async function parseResumeWithGemini(resumeText) {
  try {
    const apiKey = process.env.NEXT_PUBLIC_GEMINI_API_KEY || '';
    if (!apiKey) {
      throw new Error('Gemini API key not found. Please check your environment variables.');
    }

    // Debug: log the resume text
    console.log("Extracted Resume Text:", resumeText);

    const prompt = `
You are a resume parsing assistant. Analyze the following resume text and extract all relevant information.
Return the result in a valid JSON format strictly following this structure:

{
  "personal_info": {
    "first_name": "",
    "last_name": "",
    "email": "",
    "phone": "",
    "linkedin": "",
    "portfolio": ""
  },
  "summary": "",
  "education": [
    {
      "degree": "",
      "university": "",
      "dates": "",
      "gpa": "",
      "location": ""
    }
  ],
  "experience": [
    {
      "title": "",
      "company": "",
      "dates": "",
      "bullets": [""]
    }
  ],
  "skills": {
    "languages": [],
    "frameworks": [],
    "cloud": [],
    "databases": [],
    "tools": []
  },
  "projects": [
    {
      "name": "",
      "technologies": [],
      "description": "",
      "link": ""
    }
  ],
  "honors": [],
  "predefined_answers": {
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
}

Categorize skills appropriately into languages, frameworks, cloud, databases, and tools.
For experience, extract bullet points that highlight responsibilities and achievements.
For education, include degree, university, dates, GPA, and location if available.
For projects, include name, technologies used, description, and any links if available.
For personal_info, extract first name, last name, email, phone, LinkedIn, and portfolio website if available.
IMPORTANT: Return ONLY the JSON object with no additional text, explanations or formatting.
HERE IS THE RESUME TEXT:
${resumeText}
    `;

    // Debug: log the full prompt
    console.log("Prompt Sent to Gemini:", prompt);

    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: {
            temperature: 0.2,
            topK: 40,
            topP: 0.95,
            maxOutputTokens: 8192,
          },
        })
      }
    );

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(`Gemini API error: ${errorData.error?.message || response.statusText}`);
    }

    const data = await response.json();
    const textResponse = data.candidates[0].content.parts[0].text;
    console.log("LLM Raw Response:", textResponse);

    // Extract the JSON object from the LLM response
    const startIndex = textResponse.indexOf('{');
    const endIndex = textResponse.lastIndexOf('}');
    if (startIndex === -1 || endIndex === -1) {
      throw new Error('Failed to extract JSON from Gemini response');
    }
    const jsonString = textResponse.substring(startIndex, endIndex + 1);
    const parsedJson = JSON.parse(jsonString);

    return parsedJson;
  } catch (error) {
    console.error('Error calling Gemini API:', error);
    throw error;
  }
}

/**
 * Extracts text from a PDF buffer using pdf2json.
 *
 * @param {Buffer} pdfBuffer - Buffer containing PDF data.
 * @returns {Promise<string>} - Extracted text from the PDF.
 */
async function extractTextFromPDF(pdfBuffer) {
  return new Promise((resolve, reject) => {
    const pdfParser = new PDFParser();

    pdfParser.on("pdfParser_dataError", errData => {
      console.error("Error in pdf2json:", errData.parserError);
      reject(errData.parserError);
    });

    pdfParser.on("pdfParser_dataReady", pdfData => {
      // Iterate over pages and extract text
      let extractedText = "";
      if (pdfData && pdfData.Pages) {
        pdfData.Pages.forEach(page => {
          if (page.Texts) {
            page.Texts.forEach(textItem => {
              if (textItem.R) {
                textItem.R.forEach(run => {
                  extractedText += decodeURIComponent(run.T) + " ";
                });
              }
            });
            extractedText += "\n";
          }
        });
      }
      resolve(extractedText);
    });

    // Start parsing the buffer
    pdfParser.parseBuffer(pdfBuffer);
  });
}

/**
 * Saves JSON data to a file.
 *
 * @param {Object} data - JSON data to save.
 * @param {string} filename - Name of the file.
 * @returns {Promise<string>} - Path to the saved file.
 */
async function saveJsonToFile(data, filename) {
  try {
    const dir = join(process.cwd(), 'resumes');
    await mkdir(dir, { recursive: true });
    const filePath = join(dir, filename);
    await writeFile(filePath, JSON.stringify(data, null, 2));
    return filePath;
  } catch (error) {
    console.error('Error saving JSON to file:', error);
    throw new Error('Failed to save resume data to file');
  }
}

/**
 * Handle POST requests for parsing a resume.
 */
export async function POST(request) {
  try {
    const formData = await request.formData();
    const file = formData.get('file');

    if (!file) {
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }

    if (file.type !== 'application/pdf' && file.type !== 'text/plain') {
      return NextResponse.json({ error: 'Unsupported file type. Please upload a PDF or TXT file.' }, { status: 400 });
    }

    let text = '';
    if (file.type === 'application/pdf') {
      try {
        const buffer = Buffer.from(await file.arrayBuffer());
        text = await extractTextFromPDF(buffer);
      } catch (pdfError) {
        console.error('Error processing PDF:', pdfError);
        return NextResponse.json({ error: 'Failed to extract text from PDF' }, { status: 500 });
      }
    } else if (file.type === 'text/plain') {
      text = await file.text();
    }

    let resumeData;
    try {
      resumeData = await parseResumeWithGemini(text);
    } catch (parsingError) {
      console.error('Error parsing with Gemini:', parsingError);
      return NextResponse.json({ error: 'Failed to parse resume with AI' }, { status: 500 });
    }

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const name = resumeData.personal_info.first_name && resumeData.personal_info.last_name
      ? `${resumeData.personal_info.first_name}-${resumeData.personal_info.last_name}`
      : 'resume';
    const filename = `${name}-${timestamp}.json`;

    let filePath;
    try {
      filePath = await saveJsonToFile(resumeData, filename);
    } catch (saveError) {
      console.error('Error saving file:', saveError);
      return NextResponse.json({
        success: true,
        resumeData,
        error: 'Failed to save file, but parsing succeeded'
      });
    }

    return NextResponse.json({
      success: true,
      resumeData,
      filePath: filePath.replace(process.cwd(), '')
    });
  } catch (error) {
    console.error('Error processing resume:', error);
    return NextResponse.json({ 
      success: false,
      error: error.message || 'Failed to process resume'
    }, { status: 500 });
  }
}

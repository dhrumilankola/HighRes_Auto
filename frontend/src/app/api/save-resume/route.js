// src/app/api/save-resume/route.js
import { NextResponse } from 'next/server';
import { writeFile, mkdir } from 'fs/promises';
import { join } from 'path';

export async function POST(request) {
  try {
    // Parse the JSON body sent by the client
    const resumeData = await request.json();

    // Generate a unique filename using a timestamp and user's name if available
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const name =
      resumeData.personal_info &&
      resumeData.personal_info.first_name &&
      resumeData.personal_info.last_name
        ? `${resumeData.personal_info.first_name}-${resumeData.personal_info.last_name}`
        : 'resume';
    const filename = `${name}-${timestamp}.json`;

    // Create a directory named 'resumes' in the project root (or adjust the path as needed)
    const dir = join(process.cwd(), 'resumes');
    await mkdir(dir, { recursive: true });

    // Write the JSON data to the file
    const filePath = join(dir, filename);
    await writeFile(filePath, JSON.stringify(resumeData, null, 2));

    // Return the file path and success status
    return NextResponse.json({
      success: true,
      filePath: filePath.replace(process.cwd(), '')
    });
  } catch (error) {
    console.error('Error saving resume:', error);
    return NextResponse.json(
      {
        success: false,
        error: error.message || 'Failed to save resume'
      },
      { status: 500 }
    );
  }
}

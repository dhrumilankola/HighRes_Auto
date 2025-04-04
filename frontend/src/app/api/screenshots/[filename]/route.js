import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(request, { params }) {
  const { filename } = params;
  
  // Security check to prevent directory traversal
  if (filename.includes('..') || !filename.endsWith('.png')) {
    return NextResponse.json({ error: 'Invalid filename' }, { status: 400 });
  }
  
  // Use the direct path to the mounted volume
  const screenshotPath = path.join('/app/screenshots', filename);
  
  try {
    const imageBuffer = fs.readFileSync(screenshotPath);
    return new NextResponse(imageBuffer, {
      headers: {
        'Content-Type': 'image/png',
        'Cache-Control': 'public, max-age=3600'
      }
    });
  } catch (error) {
    console.error(`Error reading screenshot: ${error}`);
    return NextResponse.json({ error: 'Screenshot not found' }, { status: 404 });
  }
}
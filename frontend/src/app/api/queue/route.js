import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function POST(request) {
  try {
    const { jobs } = await request.json();
    
    if (!jobs || !Array.isArray(jobs) || jobs.length === 0) {
      return NextResponse.json({ message: 'No jobs provided' }, { status: 400 });
    }

    // In a real implementation, you would:
    // 1. Validate the jobs
    // 2. Connect to your queue system (RQ in your case)
    // 3. Add the jobs to the queue

    // For now, we'll just log them and simulate adding to a queue
    console.log(`Adding ${jobs.length} jobs to the queue`);
    
    // Write to a queue file (simulation)
    const queueFilePath = path.join(process.cwd(), '../../queue_system/queue.json');
    const queueDir = path.dirname(queueFilePath);
    
    // Create directory if it doesn't exist
    if (!fs.existsSync(queueDir)) {
      fs.mkdirSync(queueDir, { recursive: true });
    }
    
    // Check if file exists and read it
    let queueData = [];
    if (fs.existsSync(queueFilePath)) {
      try {
        const fileData = fs.readFileSync(queueFilePath, 'utf8');
        queueData = JSON.parse(fileData);
      } catch (error) {
        console.error('Error reading existing queue file:', error);
      }
    }
    
    // Add new jobs to queue
    const updatedQueue = [
      ...queueData,
      ...jobs.map(job => ({
        ...job,
        queued_at: new Date().toISOString(),
        status: 'pending'
      }))
    ];
    
    // Write back to file
    fs.writeFileSync(queueFilePath, JSON.stringify(updatedQueue, null, 2));
    
    // Return success
    return NextResponse.json({ 
      message: `Successfully added ${jobs.length} jobs to the queue`,
      queue_size: updatedQueue.length
    });
    
  } catch (error) {
    console.error('Error adding jobs to queue:', error);
    return NextResponse.json({ message: 'Internal server error' }, { status: 500 });
  }
}
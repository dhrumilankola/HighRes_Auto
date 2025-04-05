// src/app/api/queue/route.js

import { NextResponse } from 'next/server';
const queueUtils = require('../../../../queue_system/queue_utils');

export async function POST(request) {
  try {
    const { jobs } = await request.json();
    
    if (!jobs || !Array.isArray(jobs) || jobs.length === 0) {
      return NextResponse.json({ message: 'No jobs provided' }, { status: 400 });
    }

    const results = [];
    let successCount = 0;

    // Add each job to the queue
    for (const job of jobs) {
      const result = queueUtils.addToQueue(job);
      if (result.success) {
        successCount++;
      }
      results.push(result);
    }

    // Return success response
    return NextResponse.json({ 
      message: `Successfully added ${successCount} of ${jobs.length} jobs to the queue`,
      results,
      queue_stats: queueUtils.getQueueStats()
    });
    
  } catch (error) {
    console.error('Error adding jobs to queue:', error);
    return NextResponse.json({ message: 'Internal server error' }, { status: 500 });
  }
}

// Get queue status
export async function GET() {
  try {
    const stats = queueUtils.getQueueStats();
    
    return NextResponse.json({
      queue_stats: stats,
      total: Object.values(stats).reduce((a, b) => a + b, 0)
    });
  } catch (error) {
    console.error('Error getting queue stats:', error);
    return NextResponse.json({ message: 'Internal server error' }, { status: 500 });
  }
}
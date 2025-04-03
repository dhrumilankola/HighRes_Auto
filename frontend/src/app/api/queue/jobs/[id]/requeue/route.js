// frontend/src/app/api/queue/jobs/[id]/requeue/route.js

import { NextResponse } from 'next/server';
const queueUtils = require('../../../../../../../queue_system/queue_utils');

export async function POST(request, { params }) {
  try {
    const { id } = params;
    
    if (!id) {
      return NextResponse.json(
        { message: 'Job ID is required' }, 
        { status: 400 }
      );
    }
    
    // Find the job in its current queue
    const allJobs = queueUtils.getJobsByStatus('all');
    let jobFound = false;
    let currentStatus = '';
    
    // Check all queue types to find the job
    for (const status of ['manual_review', 'failed', 'applied', 'in_progress', 'queued']) {
      if (allJobs[status] && allJobs[status].find(j => j.id === id)) {
        jobFound = true;
        currentStatus = status;
        break;
      }
    }
    
    if (!jobFound) {
      return NextResponse.json(
        { message: 'Job not found in any queue' }, 
        { status: 404 }
      );
    }
    
    // Update status to queued and reset attempts
    const result = queueUtils.updateJobStatus(id, 'queued', {
      attempts: 0,
      error: null,
      notes: `Requeued from ${currentStatus}`
    });
    
    if (result.success) {
      return NextResponse.json({
        message: `Job ${id} has been requeued`,
        job: result.job
      });
    } else {
      return NextResponse.json(
        { message: result.message }, 
        { status: 400 }
      );
    }
  } catch (error) {
    console.error('Error requeuing job:', error);
    return NextResponse.json({ message: 'Internal server error' }, { status: 500 });
  }
}
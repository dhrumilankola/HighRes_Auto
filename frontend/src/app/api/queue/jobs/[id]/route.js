// src/app/api/queue/jobs/[id]/route.js

import { NextResponse } from 'next/server';
const queueUtils = require('../../../../../../queue_system/queue_utils');

// Update job status
export async function PUT(request, { params }) {
  try {
    const { id } = params;
    const { status, details } = await request.json();
    
    if (!id || !status) {
      return NextResponse.json(
        { message: 'Job ID and status are required' }, 
        { status: 400 }
      );
    }
    
    const result = queueUtils.updateJobStatus(id, status, details);
    
    if (result.success) {
      return NextResponse.json({
        message: `Job ${id} status updated to ${status}`,
        job: result.job
      });
    } else {
      return NextResponse.json(
        { message: result.message }, 
        { status: 400 }
      );
    }
  } catch (error) {
    console.error('Error updating job status:', error);
    return NextResponse.json({ message: 'Internal server error' }, { status: 500 });
  }
}
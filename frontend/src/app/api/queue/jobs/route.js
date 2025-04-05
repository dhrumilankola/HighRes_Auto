// src/app/api/queue/jobs/route.js

import { NextResponse } from 'next/server';
const queueUtils = require('../../../../../queue_system/queue_utils');

// Get jobs by status
export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get('status') || 'all';
    
    const jobs = queueUtils.getJobsByStatus(status);
    
    return NextResponse.json({ jobs });
  } catch (error) {
    console.error('Error retrieving jobs:', error);
    return NextResponse.json({ message: 'Internal server error' }, { status: 500 });
  }
}
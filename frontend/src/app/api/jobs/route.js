import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
    try {
      // Use the specific path to the tech_jobs.json file in public/job_data
      const jobsPath = path.join(process.cwd(), 'public/job_data/tech_jobs.json');
      
      // Check if file exists
      if (!fs.existsSync(jobsPath)) {
        console.error('Jobs file not found at:', jobsPath);
        
        // For development purposes, return mock data if file doesn't exist
        return NextResponse.json(getMockJobs());
      }
      
      // Read and parse the JSON file
      const jobsData = fs.readFileSync(jobsPath, 'utf8');
      console.log('Successfully read file from:', jobsPath);
      
      try {
        const jobs = JSON.parse(jobsData);
        console.log(`Parsed ${jobs.length} jobs from tech_jobs.json`);
        
        // Return the jobs data
        return NextResponse.json(jobs);
      } catch (parseError) {
        console.error('Error parsing JSON:', parseError);
        return NextResponse.json(getMockJobs());
      }
    } catch (error) {
      console.error('Error reading jobs file:', error);
      
      // For development purposes, return mock data if there's an error
      return NextResponse.json(getMockJobs());
    }
  }

// // Mock data for development and testing
// function getMockJobs() {
//     const currentDate = new Date().toISOString();
//     const dayAgo = new Date(Date.now() - 86400000).toISOString();
//     const twoDaysAgo = new Date(Date.now() - 2 * 86400000).toISOString();
  
//     return [
//       {
//         id: '1',
//         title: 'Frontend Developer',
//         company: 'TechCorp',
//         company_token: 'techcorp',
//         location: 'San Francisco, CA',
//         department: 'Engineering',
//         posted_at: currentDate,
//         job_url: 'https://example.com/job/1',
//         apply_url: 'https://example.com/apply/1',
//         content_snippet: 'We are looking for a skilled Frontend Developer to join our team.',
//         is_remote: true,
//         is_us_based: true,
//         tech_stack: ['React', 'JavaScript', 'TypeScript', 'HTML', 'CSS', 'Redux'],
//         role_category: 'frontend',
//       },
//       {
//         id: '2',
//         title: 'Backend Engineer',
//         company: 'DataSystems',
//         company_token: 'datasystems',
//         location: 'Remote, US',
//         department: 'Engineering',
//         posted_at: dayAgo,
//         job_url: 'https://example.com/job/2',
//         apply_url: 'https://example.com/apply/2',
//         content_snippet: 'Join our backend team to build scalable APIs and microservices.',
//         is_remote: true,
//         is_us_based: true,
//         tech_stack: ['Python', 'Django', 'PostgreSQL', 'Redis', 'Docker', 'AWS'],
//         role_category: 'backend',
//       },
//       {
//         id: '3',
//         title: 'Full Stack Developer',
//         company: 'GrowthStartup',
//         company_token: 'growthstartup',
//         location: 'New York, NY',
//         department: 'Product',
//         posted_at: twoDaysAgo,
//         job_url: 'https://example.com/job/3',
//         apply_url: 'https://example.com/apply/3',
//         content_snippet: 'Looking for a versatile developer who can work across our entire stack.',
//         is_remote: false,
//         is_us_based: true,
//         tech_stack: ['React', 'Node.js', 'MongoDB', 'Express', 'GraphQL'],
//         role_category: 'fullstack',
//       },
//       {
//         id: '4',
//         title: 'Data Engineer',
//         company: 'AnalyticsPro',
//         company_token: 'analyticspro',
//         location: 'Remote, US',
//         department: 'Data',
//         posted_at: currentDate,
//         job_url: 'https://example.com/job/4',
//         apply_url: 'https://example.com/apply/4',
//         content_snippet: 'Join our data team to build data pipelines and infrastructure.',
//         is_remote: true,
//         is_us_based: true,
//         tech_stack: ['Python', 'Spark', 'Airflow', 'SQL', 'Snowflake', 'dbt'],
//         role_category: 'data',
//       },
//       {
//         id: '5',
//         title: 'DevOps Engineer',
//         company: 'CloudSolutions',
//         company_token: 'cloudsolutions',
//         location: 'Austin, TX',
//         department: 'Infrastructure',
//         posted_at: dayAgo,
//         job_url: 'https://example.com/job/5',
//         apply_url: 'https://example.com/apply/5',
//         content_snippet: 'We need a DevOps engineer to help automate our CI/CD pipelines.',
//         is_remote: true,
//         is_us_based: true,
//         tech_stack: ['Kubernetes', 'Docker', 'Terraform', 'AWS', 'Jenkins', 'GitHub Actions'],
//         role_category: 'devops',
//       },
//       {
//         id: '6',
//         title: 'Machine Learning Engineer',
//         company: 'AI Innovations',
//         company_token: 'aiinnovations',
//         location: 'Seattle, WA',
//         department: 'Research',
//         posted_at: twoDaysAgo,
//         job_url: 'https://example.com/job/6',
//         apply_url: 'https://example.com/apply/6',
//         content_snippet: 'Join our ML team to develop and deploy machine learning models.',
//         is_remote: false,
//         is_us_based: true,
//         tech_stack: ['Python', 'TensorFlow', 'PyTorch', 'Scikit-learn', 'Kubernetes'],
//         role_category: 'ml_ai',
//       },
//     ];
//   }
  
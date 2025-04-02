// This script copies the tech_jobs.json file from job_scraper directory to frontend/public/job_data
const fs = require('fs');
const path = require('path');

// Source path for tech_jobs.json
const sourcePath = path.join(__dirname, '../job_scraper/tech_jobs.json');

// Destination path in public/job_data directory
const destDir = path.join(__dirname, 'public/job_data');
const destPath = path.join(destDir, 'tech_jobs.json');

// Create public/job_data directory if it doesn't exist
if (!fs.existsSync(destDir)) {
  fs.mkdirSync(destDir, { recursive: true });
  console.log(`Created directory: ${destDir}`);
}

// Check if source file exists
if (fs.existsSync(sourcePath)) {
  console.log(`Found tech_jobs.json at: ${sourcePath}`);
  
  try {
    // Read file content and parse to validate JSON
    const content = fs.readFileSync(sourcePath, 'utf8');
    const data = JSON.parse(content); // This will throw if JSON is invalid
    
    console.log(`Parsed ${data.length} jobs from source file`);
    
    // Copy the file
    fs.copyFileSync(sourcePath, destPath);
    console.log(`Successfully copied to: ${destPath}`);
    
    // Output timestamp to indicate when the data was last updated
    fs.writeFileSync(
      path.join(destDir, 'last_updated.txt'), 
      new Date().toISOString()
    );
    console.log(`Updated timestamp file`);
    
  } catch (error) {
    console.error(`Error processing file: ${error.message}`);
    process.exit(1);
  }
} else {
  console.error(`Source file not found at: ${sourcePath}`);
  console.error('Please make sure the job_scraper has generated the tech_jobs.json file');
  process.exit(1);
}

console.log('Job data update completed successfully!');
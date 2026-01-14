/**
 * ReferralLink - Main Navigation
 * 
 * This file serves as a simple entry point to navigate to either 
 * the frontend or backend of the application.
 * 
 * - Frontend: React-based UI (/frontend)
 * - Backend: Python/Flask API with Supabase (/backend)
 * 
 * For more detailed instructions, see the README.md file.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html' });
  
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ReferralLink</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      max-width: 800px;
      margin: 0 auto;
      padding: 20px;
      line-height: 1.6;
    }
    h1 {
      color: #333;
      border-bottom: 1px solid #eee;
      padding-bottom: 10px;
    }
    .card {
      border: 1px solid #ddd;
      border-radius: 4px;
      padding: 20px;
      margin-bottom: 20px;
      background-color: #f9f9f9;
    }
    .button {
      display: inline-block;
      padding: 10px 20px;
      background-color: #4CAF50;
      color: white;
      text-decoration: none;
      border-radius: 4px;
      font-weight: bold;
    }
  </style>
</head>
<body>
  <h1>ReferralLink Project</h1>
  
  <div class="card">
    <h2>Frontend</h2>
    <p>React-based user interface for managing real estate leads and referrals.</p>
    <a href="/frontend" class="button">Go to Frontend</a>
  </div>
  
  <div class="card">
    <h2>Backend</h2>
    <p>Python/Flask API with Supabase for data persistence and webhook handling.</p>
    <a href="/backend" class="button">Go to Backend</a>
  </div>
  
  <p>For more information, please refer to the <a href="README.md">README.md</a> file.</p>
</body>
</html>`;
  
  res.end(html);
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}/`);
  console.log('Navigate to:');
  console.log(`- Frontend: http://localhost:${PORT}/frontend`);
  console.log(`- Backend: http://localhost:${PORT}/backend`);
}); 
 * ReferralLink - Main Navigation
 * 
 * This file serves as a simple entry point to navigate to either 
 * the frontend or backend of the application.
 * 
 * - Frontend: React-based UI (/frontend)
 * - Backend: Python/Flask API with Supabase (/backend)
 * 
 * For more detailed instructions, see the README.md file.
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const server = http.createServer((req, res) => {
  res.writeHead(200, { 'Content-Type': 'text/html' });
  
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ReferralLink</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      max-width: 800px;
      margin: 0 auto;
      padding: 20px;
      line-height: 1.6;
    }
    h1 {
      color: #333;
      border-bottom: 1px solid #eee;
      padding-bottom: 10px;
    }
    .card {
      border: 1px solid #ddd;
      border-radius: 4px;
      padding: 20px;
      margin-bottom: 20px;
      background-color: #f9f9f9;
    }
    .button {
      display: inline-block;
      padding: 10px 20px;
      background-color: #4CAF50;
      color: white;
      text-decoration: none;
      border-radius: 4px;
      font-weight: bold;
    }
  </style>
</head>
<body>
  <h1>ReferralLink Project</h1>
  
  <div class="card">
    <h2>Frontend</h2>
    <p>React-based user interface for managing real estate leads and referrals.</p>
    <a href="/frontend" class="button">Go to Frontend</a>
  </div>
  
  <div class="card">
    <h2>Backend</h2>
    <p>Python/Flask API with Supabase for data persistence and webhook handling.</p>
    <a href="/backend" class="button">Go to Backend</a>
  </div>
  
  <p>For more information, please refer to the <a href="README.md">README.md</a> file.</p>
</body>
</html>`;
  
  res.end(html);
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}/`);
  console.log('Navigate to:');
  console.log(`- Frontend: http://localhost:${PORT}/frontend`);
  console.log(`- Backend: http://localhost:${PORT}/backend`);
}); 
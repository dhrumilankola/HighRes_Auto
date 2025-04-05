# frontend/Dockerfile

FROM node:18-alpine

WORKDIR /app

# Copy the frontend package files and install dependencies
COPY frontend/package*.json ./
RUN npm install

# Copy the frontend source code
COPY frontend/ ./

# Copy the shared queue_system folder from the project root
COPY queue_system/ ./queue_system

# Build the Next.js application
RUN npm run build

# Expose port 3000
EXPOSE 3000

# Start the Next.js server in production mode
CMD ["npm", "start"]

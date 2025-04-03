# agent/Dockerfile

FROM mcr.microsoft.com/playwright:v1.35.0-jammy

WORKDIR /app

# Install Python and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the agent code into the container
COPY . .

# Create the screenshots directory
RUN mkdir -p screenshots

# Run the service in service mode by default
CMD ["python3", "main.py", "--mode", "service"]

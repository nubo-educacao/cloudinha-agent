FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed (e.g. git for some pip packages)
# RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set PYTHONPATH to include the current directory
ENV PYTHONPATH=/app

# Default command to run the agent
# Cloud Run will define the PORT env variable
CMD ["python", "server.py"]

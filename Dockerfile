FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library
RUN wget https://sourceforge.net/projects/ta-lib/files/ta-lib/0.4.0/ta-lib-0.4.0-src.tar.gz/download -O ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && \
    ./configure --prefix=/usr --build=aarch64-unknown-linux-gnu && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Update library cache
RUN ldconfig

# Set library path for TA-Lib
ENV LD_LIBRARY_PATH=/usr/lib:$LD_LIBRARY_PATH

# Copy requirements
COPY requirements.txt .

# Install Python packages with TA-Lib library paths
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir numpy && \
    TA_LIBRARY_PATH=/usr/lib TA_INCLUDE_PATH=/usr/include pip install --no-cache-dir TA-Lib && \
    pip install --no-cache-dir flask==3.0.0 flask-socketio==5.3.5 anthropic==0.39.0 requests==2.31.0 pandas==2.1.4 python-dotenv==1.0.0 pytz==2023.3 python-engineio==4.8.0 python-socketio==5.10.0

# Copy application
COPY . .

# Create necessary directories
RUN mkdir -p logs data data/claude_recommendations

# Expose Flask port
EXPOSE 8779

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8779/health')" || exit 1

# Run Flask web dashboard
CMD ["python", "web/app.py"]

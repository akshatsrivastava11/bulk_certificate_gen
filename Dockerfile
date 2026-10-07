FROM python:3.11-slim

# System dependencies for ReportLab and Pillow
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p generated_certificates static/fonts static/template_assets

# Copy and make entrypoint executable
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port
EXPOSE 5000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]

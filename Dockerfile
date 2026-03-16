FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates templates/
COPY static static/
COPY .env .

# Create directories with proper permissions
RUN mkdir -p reports static/logos && \
    chmod -R 755 static && \
    chmod -R 755 reports && \
    chmod -R 755 templates

# Ensure static files are readable and executable
RUN find static -type f -exec chmod 644 {} \; && \
    find static -type d -exec chmod 755 {} \; && \
    find templates -type f -exec chmod 644 {} \; && \
    find templates -type d -exec chmod 755 {} \;

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["python", "app.py"]

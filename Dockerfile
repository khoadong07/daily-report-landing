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
    chown -R www-data:www-data static reports 2>/dev/null || true

# Ensure static files are readable
RUN find static -type f -exec chmod 644 {} \; && \
    find static -type d -exec chmod 755 {} \;

EXPOSE 8000

CMD ["python", "app.py"]

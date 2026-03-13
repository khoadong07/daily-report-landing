FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates templates/
COPY static static/

# Create directories with proper permissions
RUN mkdir -p reports static/logos && \
    chmod -R 755 static && \
    chmod -R 755 reports

EXPOSE 8000

CMD ["python", "app.py"]

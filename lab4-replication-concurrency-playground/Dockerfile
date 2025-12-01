FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY leader.py .
COPY follower.py .

# Default to leader, can be overridden in docker-compose
CMD ["python", "leader.py"]

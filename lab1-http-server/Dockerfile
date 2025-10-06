FROM python:3.11-slim

WORKDIR /app

COPY src/ /app/src
COPY content/ /app/content

EXPOSE 8080

CMD ["python", "src/server.py", "content"]

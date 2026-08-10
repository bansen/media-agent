FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY content_agent ./content_agent
COPY .agents ./.agents
COPY .env.example ./.env.example

RUN mkdir -p output

EXPOSE 8000

CMD ["python3", "-m", "content_agent.web", "--host", "0.0.0.0", "--port", "8000"]

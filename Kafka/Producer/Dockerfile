FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src /app/src
ENV PYTHONPATH=/app/src

# Prometheus will scrape on this port
EXPOSE 8000

CMD ["python", "-m", "producer.main"]

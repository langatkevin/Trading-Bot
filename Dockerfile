FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot ./bot
COPY config ./config
# Keys come from the environment (GCP Secret Manager), never baked into the image.
ENV ALPACA_PAPER=true PYTHONUNBUFFERED=1
CMD ["python", "-m", "bot", "paper"]

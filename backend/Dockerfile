FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
# 1 worker + threads: model ek hi baar load hoga aur background jobs same process mein chalenge
CMD ["gunicorn", "-w", "1", "--threads", "8", "-t", "300", "-b", "0.0.0.0:5000", "run:app"]

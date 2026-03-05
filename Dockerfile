FROM python:3.11-slim   

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*  

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY classes.py .
COPY config.py .
COPY "GRI_2017_2020.xlsx" .

CMD ["python", "./app.py"]
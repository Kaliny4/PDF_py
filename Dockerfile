FROM python:3.11-slim   

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY "GRI_2017_2020 (1).xlsx" .

CMD ["python", "./app.py"]
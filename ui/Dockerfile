FROM python:3.11-slim

WORKDIR /app

COPY ui/requirements.txt /tmp/ui-requirements.txt
COPY backtester/requirements.txt /tmp/backtester-requirements.txt
RUN pip install --no-cache-dir -r /tmp/ui-requirements.txt -r /tmp/backtester-requirements.txt

COPY . /app

EXPOSE 5000
CMD ["python", "ui/flask_app.py"]

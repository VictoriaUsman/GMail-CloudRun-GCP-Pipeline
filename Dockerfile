FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
# Using gunicorn is better for production
RUN pip install gunicorn 
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
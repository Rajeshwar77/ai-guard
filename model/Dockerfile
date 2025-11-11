
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mock_model.py .
CMD ["uvicorn", "mock_model:app", "--host", "0.0.0.0", "--port", "5000"]

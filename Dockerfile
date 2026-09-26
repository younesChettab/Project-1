FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY amin ./amin
COPY web ./web
COPY samples ./samples
ENV PORT=8000 AMIN_DATA_DIR=/app/data
EXPOSE 8000
CMD ["sh", "-c", "uvicorn amin.api:app --host 0.0.0.0 --port ${PORT}"]

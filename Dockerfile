FROM python:3.12-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
WORKDIR /app

COPY main.py /app/main.py
COPY modules/BigQuerySchemaManager.py /app/modules/BigQuerySchemaManager.py
COPY modules/EnrichedSchemaManager.py /app/modules/EnrichedSchemaManager.py
COPY modules/file_utils.py /app/modules/file_utils.py
COPY modules/llm_utils.py /app/modules/llm_utils.py
COPY requirements.txt /app/requirements.txt
COPY logger_setup.py /app/logger_setup.py

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "main.py"]
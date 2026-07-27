FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY app.py ./
COPY knowledge_base ./knowledge_base
COPY data ./data
RUN pip install --no-cache-dir -e .

EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]


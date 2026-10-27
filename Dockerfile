FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY control ./control
COPY tests ./tests
RUN python -m unittest discover -s tests -v
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec uvicorn control.server:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]

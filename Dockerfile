FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY control ./control
COPY tests ./tests
COPY scripts ./scripts
RUN python -m unittest discover -s tests -v
ENV CONTROL_EMBED_CACHE=/opt/control-embeddings
RUN python -c "from fastembed import TextEmbedding; model=TextEmbedding(model_name='BAAI/bge-small-en-v1.5',cache_dir='/opt/control-embeddings',threads=2); vector=list(model.embed(['Preparing job applications is difficult']))[0]; assert len(vector)==384; print('Local semantic model ready: 384 dimensions')"
RUN python scripts/embedding_smoke.py
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec uvicorn control.server:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]

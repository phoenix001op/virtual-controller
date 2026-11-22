FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "aiohttp>=3.9,<4"
COPY relay.py server.py ./
COPY web ./web
ENV PORT=8080
EXPOSE 8080
CMD ["python","relay.py"]

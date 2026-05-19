FROM python:3.11-slim

ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8019

# Run via main() so the PORT env var and tuned uvicorn settings
# (proxy_headers, timeout_keep_alive) actually take effect.
CMD ["python", "main.py"]

FROM python:3.13-slim-bookworm

WORKDIR /app

COPY requirements.txt .

RUN pip install \
    --index-url https://mirrors.aliyun.com/pypi/simple/ \
    --no-cache-dir \
    -r requirements.txt

COPY . .

CMD ["python", "main.py"]

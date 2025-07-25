FROM python:3.9-slim AS base
LABEL maintainer="AWS Cost Monitor"
LABEL description="AWS成本监控系统"
LABEL version="1.0.0"

WORKDIR /app

ENV PYTHONUNBUFFERED=1

FROM base AS dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM dependencies AS app
COPY . .
RUN mkdir -p data

EXPOSE 80

CMD ["python", "-u", "start.py"]
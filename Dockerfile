FROM python:3.12-slim
RUN apt-get update && apt-get install -y graphviz && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONUNBUFFERED=1
CMD ["tail", "-f", "/dev/null"]

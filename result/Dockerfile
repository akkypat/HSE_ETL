FROM apache/airflow:2.6.3

USER root

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

USER airflow

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir -r /tmp/requirements.txt

ENV AIRFLOW__CORE__LOAD_EXAMPLES=False
ENV AIRFLOW__CORE__EXECUTOR=LocalExecutor
FROM python:3.12-slim
# iputils-ping -> sondeo ICMP | snmp -> snmpget/snmpwalk (net-snmp, código abierto)
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping snmp \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

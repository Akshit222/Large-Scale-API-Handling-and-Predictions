import socket
import time
import random
import json
from datetime import datetime
from kafka import KafkaProducer

# === CONFIG ===
MODE = 'direct'  # options: direct, fullstack
TCP_HOST = 'localhost'
TCP_PORT = 5044
KAFKA_TOPIC = 'full-pipeline'
KAFKA_SERVER = 'localhost:9092'

methods = ['GET', 'POST', 'PUT', 'DELETE']
endpoints = ['/api/login', '/api/user', '/api/data']
status_codes = [200, 201, 400, 401, 403, 404, 500]

if MODE == 'direct':
    s = socket.socket()
    s.connect((TCP_HOST, TCP_PORT))
elif MODE == 'fullstack':
    producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER)

while True:
    timestamp = datetime.utcnow().strftime('%d/%b/%Y:%H:%M:%S +0000')
    ip = f"192.168.1.{random.randint(1, 255)}"
    method = random.choice(methods)
    endpoint = random.choice(endpoints)
    status = random.choice(status_codes)
    log = f'{ip} - - [{timestamp}] "{method} {endpoint} HTTP/1.1" {status} {random.randint(100, 5000)}'

    if MODE == 'direct':
        s.send((log + "\n").encode())
    elif MODE == 'fullstack'
        producer.send(KAFKA_TOPIC, log.encode())

    time.sleep(0.1)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import json
import logging
import random
import time
from datetime import datetime
import os
import requests
from elasticsearch import Elasticsearch
import uuid
from pathlib import Path

app = FastAPI()

# Load environment variables
load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_DIR = os.getenv("LOG_DIR", "dock/logs")
ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")

# Create log directory if it doesn't exist
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
log_file = os.path.join(LOG_DIR, "api_logs.json")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Elasticsearch with error handling
try:
    es = Elasticsearch(ES_HOST)
    if es.ping():
        logger.info("Connected to Elasticsearch")
    else:
        logger.warning("Failed to connect to Elasticsearch - continuing without ES")
        es = None
except Exception as e:
    logger.warning(f"Elasticsearch connection error: {str(e)} - continuing without ES")
    es = None

# Variables for simulating API responses
status_codes = [200, 201, 400, 403, 404, 500, 503]
error_messages = {
    400: "Bad Request: Invalid input",
    403: "Forbidden: Access denied",
    404: "Not Found: Resource missing",
    500: "Internal Server Error",
    503: "Service Unavailable: Try later",
}

# Function to log requests and responses
async def log_request_response(request: Request, response_data, status_code, response_time):
    try:
        # Get request body if applicable
        body = await request.json() if request.method in ["POST", "PUT"] else None
    except:
        body = None
    
    # Create log entry
    log_entry = {
        "timestamp": str(datetime.utcnow()),
        "method": request.method,
        "endpoint": request.url.path,
        "url": str(request.url),
        "client_ip": request.client.host,
        "request_body": body,
        "response_body": response_data,
        "status_code": status_code,
        "environment": ENVIRONMENT,
        "response_time_ms": response_time,
        "request_id": str(uuid.uuid4())
    }
    
    # Log headers excluding sensitive information
    headers = dict(request.headers)
    if "authorization" in headers:
        headers["authorization"] = "[REDACTED]"
    log_entry["headers"] = headers
    
    # Write log as a single NDJSON line
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    # Also add log to Elasticsearch if available
    if es:
        try:
            es.index(index="api-logs", document=log_entry)
        except Exception as es_err:
            logger.error(f"Failed to log to Elasticsearch: {es_err}")
    
    # Call the Flask anomaly detection API
    try:
        flask_api_url = "http://localhost:5000/predict"
        
        # Format request for the ML API
        ml_request = {
            "source_type": "json_data",  # Send logs directly in JSON format
            "logs": [log_entry]  # Send the current log entry
        }
        
        # Send data to Flask API
        response = requests.post(flask_api_url, json=ml_request, timeout=5)
        
        # Process ML API response
        if response.status_code == 200:
            ml_response = response.json()
            
            # Check if anomalies were detected
            if "message" in ml_response and "Anomalies Detected" in ml_response["message"]:
                anomaly_count = int(ml_response["message"].split(":")[1].strip())
                
                if anomaly_count > 0 and "top_anomalies" in ml_response:
                    logger.warning(f"Anomalies detected: {anomaly_count}")
                    
                    # Save anomaly information to Elasticsearch
                    if es:
                        try:
                            # Create enhanced anomaly document
                            anomaly_doc = {
                                "detection_timestamp": str(datetime.utcnow()),
                                "api_endpoint": request.url.path,
                                "http_method": request.method,
                                "status_code": status_code,
                                "response_time": response_time,
                                "anomaly_count": anomaly_count,
                                "detection_model": ml_response.get("detection_method", "LSTM"),
                                "detection_threshold": ml_response.get("threshold", 0.1),
                                "original_log": log_entry,
                                "top_anomalies": ml_response.get("top_anomalies", []),
                                "problem_analysis": ml_response.get("problem_analysis", {}),
                                "environment": ENVIRONMENT
                            }
                            
                            # Index the anomaly in Elasticsearch
                            result = es.index(index="api-anomalies", document=anomaly_doc)
                            logger.info(f"Anomaly recorded in Elasticsearch: {result['_id']}")
                            
                        except Exception as es_error:
                            logger.error(f"Error recording anomaly in Elasticsearch: {es_error}")
            else:
                logger.debug("No anomalies detected in this request")
        else:
            logger.error(f"Anomaly detection request failed: {response.status_code} - {response.text}")
    
    except requests.exceptions.RequestException as req_error:
        logger.error(f"Error connecting to anomaly detection service: {req_error}")
    except Exception as e:
        logger.error(f"Unexpected error in anomaly detection flow: {e}")

# Dynamic behavior handler
async def handle_request(request: Request):
    start_time = datetime.utcnow()
    
    # Simulate random response delay
    delay = round(random.uniform(50, 2000), 2)
    time.sleep(delay / 1000)
    
    # Get request body if present
    try:
        body = await request.json()
    except:
        body = None
    
    # Status code selection based on randomness
    roll = random.uniform(0, 1)
    if roll < 0.85:
        # 85% chance of 2xx success
        status_code = random.choice([200, 201, 202])
    elif roll < 0.95:
        # 10% chance of 4xx client errors
        status_code = random.choice([400, 401, 403, 404])
    else:
        # 5% chance of 5xx server errors
        status_code = random.choice([500, 502, 503])
    
    # Create response data
    if status_code < 400:
        response_data = {"status": "success", "data": body}
    else:
        response_data = {"error": error_messages.get(status_code, "Unknown Error")}
    
    # Calculate response time
    end_time = datetime.utcnow()
    response_time = int((end_time - start_time).total_seconds() * 1000)
    
    # Log the request and response
    await log_request_response(request, response_data, status_code, response_time)
    
    return JSONResponse(content=response_data, status_code=status_code)

# Register API routes
endpoints = ["/submit", "/update", "/delete", "/fetch", "/authenticate"]
methods = ["GET", "POST", "PUT", "DELETE"]

for path in endpoints:
    for method in methods:
        app.add_api_route(
            path,
            handle_request,
            methods=[method],
            name=f"{method}_{path.strip('/')}"
        )

# Logs viewer endpoint
@app.get("/logs")
async def get_logs(limit: int = 100):
    try:
        # Read the log file
        logs = []
        with open(log_file, "r") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
                if len(logs) >= limit:
                    break
        
        # Return the most recent logs first
        logs.reverse()
        return JSONResponse(content=logs)
    except Exception as e:
        logger.error(f"Error retrieving logs: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

# Health check endpoint
@app.get("/health")
async def health_check():
    health = {
        "status": "healthy",
        "environment": ENVIRONMENT,
        "timestamp": str(datetime.utcnow()),
    }
    
    # Add Elasticsearch status
    if es:
        try:
            es_health = es.cluster.health()
            health["elasticsearch"] = {
                "status": es_health["status"],
                "nodes": es_health["number_of_nodes"]
            }
        except Exception as e:
            health["elasticsearch"] = {"status": "error", "message": str(e)}
    else:
        health["elasticsearch"] = {"status": "not_configured"}
    
    # Check anomaly detection service
    try:
        flask_response = requests.get("http://localhost:5000/", timeout=2)
        health["anomaly_detection"] = {
            "status": "available" if flask_response.status_code == 200 else "error",
            "code": flask_response.status_code
        }
    except:
        health["anomaly_detection"] = {"status": "unavailable"}
    
    return JSONResponse(content=health)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
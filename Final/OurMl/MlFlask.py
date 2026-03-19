from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
import joblib
from tensorflow.keras.models import load_model
from difflib import get_close_matches
from elasticsearch import Elasticsearch
import json
import datetime

app = Flask(__name__)

# Update with your Elasticsearch endpoint and credentials
es = Elasticsearch(
    ["http://localhost:9200"],
    http_auth=('elastic', 'YAqj2l7X')  # Replace with your actual username and password
)

# Load model and scaler
model = load_model('lstm_anomaly_model.h5')
scaler = joblib.load('scaler.save')

# Load additional models and scalers
model2 = load_model('h2.h5')
scaler2 = joblib.load('scaler2.save')
# model3 = load_model('h3.h5')
# scaler3 = joblib.load('scaler3.save')
# model4 = load_model('h4.h5')
# scaler4 = joblib.load('scaler4.save')

# Define remediation actions for different anomaly types
REMEDIATION_ACTIONS = {
    'Spike_1': {
        'description': 'Response time anomaly detected',
        'action': 'Check server load and database performance. Consider scaling up resources or optimizing slow queries.'
    },
    'Spike_2': {
        'description': 'API crash prediction',
        'action': 'Reduce incoming traffic, restart problematic services, and check memory usage. Consider implementing circuit breaker pattern.'
    },
    'Spike_3': {
        'description': 'Probable cause of failure detected',
        'action': 'Analyze recent logs for patterns in API parameters that correlate with failures. Consider revising API configurations or handling specific error cases.'
    }
    # Add more remediation actions for other anomaly types
}

# Functions
def create_sequences(data, time_steps=30):
    X = []
    for i in range(len(data) - time_steps):
        X.append(data[i:i+time_steps])
    return np.array(X)

def best_match(field_name, candidate_fields):
    match = get_close_matches(field_name, candidate_fields, n=1, cutoff=0.4)
    return match[0] if match else None

# Set a threshold manually or dynamically (fine-tune later)
THRESHOLD = 0.15  # Example: 15% error threshold

# Feature extraction for model 1
def extract_features_model1(df):
    # Extract features for model 1
    df_features = pd.DataFrame()
    df_features['response_time_ms'] = df['response_time_ms']
    # Add more features as needed
    return df_features

# Feature extraction for model 2
def extract_features_model2(df):
    # Extract features for model 2
    df_features = pd.DataFrame()
    
    # Create features in the EXACT same order and names as used during training
    df_features['hour'] = pd.to_datetime(df['timestamp']).dt.hour
    df_features['is_error'] = (df['status_code'] >= 400).astype(int)
    df_features['request_size'] = df.apply(
        lambda row: len(str(row['request_body'])) if isinstance(row['request_body'], dict) else 0, 
        axis=1
    )
    df_features['is_onprem'] = (df['environment'] == 'on-prem').astype(int)
    
    return df_features

# Feature extraction for model 3
# def extract_features_model3(df):
#     # Extract features for model 3
#     df_features = pd.DataFrame()
#     df_features['method'] = df['method']
#     df_features['endpoint'] = df['endpoint']
#     df_features['environment'] = df['environment']
#     df_features['client_ip'] = df['client_ip']
#     df_features['response_time_ms'] = df['response_time_ms']
#     # Add any missing features that were used during fitting
#     df_features['hour'] = pd.to_datetime(df['timestamp']).dt.hour
#     df_features['is_error'] = (df['status_code'] >= 400).astype(int)
#     df_features['is_onprem'] = (df['environment'] == 'on-prem').astype(int)
#     return df_features

# Send data to Elasticsearch
def send_to_elasticsearch(data, index_name):
    # Add timestamp for Elasticsearch if not present
    if '@timestamp' not in data:
        data['@timestamp'] = datetime.datetime.now().isoformat()
    
    # Include any remediation info for anomalies
    keys_to_modify = [key for key in data.keys() if key.startswith('Spike_') and data[key]]
    for key in keys_to_modify:
        data[f'{key}_remediation'] = REMEDIATION_ACTIONS.get(key, {})
        
    # Send to Elasticsearch
    try:
        res = es.index(index=index_name, document=data)
        return res
    except Exception as e:
        print(f"Error sending to Elasticsearch: {str(e)}")
        return None

# Process data with model
def process_with_model(model, scaler, output_file, anomaly_label, feature_extraction_func, df, send_to_es=True):
    # Extract features based on the appropriate function
    features = feature_extraction_func(df)
    
    # For model 1
    if anomaly_label == 'Spike_1':
        response_times_scaled = scaler.transform(features)
        
        # Create sequences
        time_steps = 30
        if len(response_times_scaled) < time_steps:
            return jsonify({'error': 'Not enough data points'}), 400

        X = create_sequences(response_times_scaled, time_steps)
        preds = model.predict(X)

        # Compare prediction and true value
        true = response_times_scaled[time_steps:]
        errors = np.abs(preds.flatten() - true.flatten())

        anomalies = errors > THRESHOLD

        # Add anomalies back to DataFrame
        df_copy = df.iloc[time_steps:].copy()
        df_copy[anomaly_label] = anomalies
    
    # For model 2 (h2.h5)
    elif anomaly_label == 'Spike_2':
        # Scale features
        features_scaled = scaler.transform(features)
        
        # Make predictions
        crash_probs = model.predict(features_scaled)
        
        # Add predictions to DataFrame
        df_copy = df.copy()
        df_copy[anomaly_label] = crash_probs > 0.5
        df_copy['crash_probability'] = crash_probs
    
    # For model 3 (h3.h5)
    # elif anomaly_label == 'Spike_3':
    #     # Scale features
    #     features_scaled = scaler.transform(features)
        
    #     # Make predictions
    #     failure_probs = model.predict(features_scaled)
        
    #     # Add predictions to DataFrame
    #     df_copy = df.copy()
    #     df_copy[anomaly_label] = failure_probs > 0.5
    #     df_copy['failure_probability'] = failure_probs

    # Replace NaN values with None (which translates to null in JSON)
    df_copy = df_copy.where(pd.notnull(df_copy), None)

    # Save to a new file
    df_copy.to_json(output_file, orient='records', lines=True)  # Save as JSON
    
    # Send to Elasticsearch if requested
    if send_to_es:
        # Process each row to send to Elasticsearch
        for _, row in df_copy.iterrows():
            # Convert row to dict
            row_dict = row.to_dict()
            
            # Check if any anomaly is True
            has_anomaly = False
            for key in row_dict:
                if key.startswith('Spike_') and row_dict[key]:
                    has_anomaly = True
                    break
            
            # If anomaly detected, add remediation information
            if has_anomaly:
                for spike_key in [k for k in row_dict.keys() if k.startswith('Spike_')]:
                    if row_dict[spike_key]:
                        row_dict[f'{spike_key}_remediation_description'] = REMEDIATION_ACTIONS.get(spike_key, {}).get('description', '')
                        row_dict[f'{spike_key}_remediation_action'] = REMEDIATION_ACTIONS.get(spike_key, {}).get('action', '')
            
            # Send to Elasticsearch
            index_name = 'api_logs_ml_results'  # You can customize this
            send_to_elasticsearch(row_dict, index_name)
    
    return df_copy

@app.route('/predict', methods=['POST'])
def predict_anomaly():
    try:
        # Fixed file path for input data
        file_path = '../dock/logs/api_logs.json'

        # Read the incoming JSON file
        df = pd.read_json(file_path, orient='records', lines=True)
        
        # Ensure Timestamp is a datetime type and sort values
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')

        # Debugging: Check the type of scaler3
        print(f"Type of scaler3: {type(scaler3)}")

        # Process logs for each model
        process_with_model(model, scaler, '../dock/logs/api_logs.json ', 'Spike_1', extract_features_model1, df)
        process_with_model(model2, scaler2, '../dock/logs/api_logs.json ', 'Spike_2', extract_features_model2, df)
        # process_with_model(model3, scaler3, '../dock/logs/api_logs.json ', 'Spike_3', extract_features_model3, df)
        # process_with_model(model4, scaler4, '../FinalMlLogs/Final_logs4.json', 'Spike_4', extract_features_model4, df)

        # Return the output file paths in the response
        return jsonify({'status': 'success', 'output_files': ['Final_logs.json', 'Final_logs2.json']})
    
    except Exception as e:
        # Add error handling and logging
        print(f"Error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    # Create the index pattern in Elasticsearch if it doesn't exist
    if not es.indices.exists(index="api_logs_ml_results"):
        # Define index mapping with fields for remediation actions
        mapping = {
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "timestamp": {"type": "date"},
                    "Spike_1": {"type": "boolean"},
                    "Spike_1_remediation_description": {"type": "text"},
                    "Spike_1_remediation_action": {"type": "text"},
                    "Spike_2": {"type": "boolean"},
                    "Spike_2_remediation_description": {"type": "text"},
                    "Spike_2_remediation_action": {"type": "text"},
                    "Spike_3": {"type": "boolean"},
                    "Spike_3_remediation_description": {"type": "text"},
                    "Spike_3_remediation_action": {"type": "text"},
                    "crash_probability": {"type": "float"},
                    "failure_probability": {"type": "float"}
                }
            }
        }
        es.indices.create(index="api_logs_ml_results", body=mapping)
    
    app.run(port=5000, debug=True)
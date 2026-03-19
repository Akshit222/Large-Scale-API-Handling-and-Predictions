import subprocess
import time
import os
import argparse

def run_full_process(log_count=5000):
    """Run the full process: start server, generate data, train model"""
    
    # Step 1: Start the Flask server
    print("Starting Flask server...")
    server_process = subprocess.Popen(
        ["python", "flask_log_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    print("Waiting for server to start...")
    time.sleep(5)
    
    try:
        # Step 2: Generate the dataset
        print("\n--- GENERATING DATASET ---")
        subprocess.run(["python", "generate_dataset.py", f"--count={log_count}"], check=True)
        
        # Step 3: Train the model
        print("\n--- TRAINING MODEL ---")
        subprocess.run(["python", "train_model.py"], check=True)
        
        print("\n--- PROCESS COMPLETED SUCCESSFULLY ---")
        print("The LSTM model has been trained and saved as 'models/lstm_anomaly_model.h5'")
        print("You can find evaluation metrics in 'models/evaluation_metrics.txt'")
        
    finally:
        # Always terminate the server process when done
        print("\nShutting down Flask server...")
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the full log anomaly detection process')
    parser.add_argument('--log-count', type=int, default=5000, help='Number of logs to generate')
    
    args = parser.parse_args()
    
    # Create necessary directories
    os.makedirs('data', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    
    # Run the full process
    run_full_process(args.log_count)
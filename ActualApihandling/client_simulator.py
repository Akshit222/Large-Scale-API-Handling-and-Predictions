import asyncio
import aiohttp
import random
import time

API_URL = "http://localhost:5000"

# Function to send the Sign-up request (201 Created)
async def client_signup(session):
    data = {
        "username": f"user{random.randint(1000, 9999)}",
        "password": "password123",
        "email": f"user{random.randint(1000, 9999)}@example.com"
    }
    async with session.post(f"{API_URL}/api/signup", json=data) as response:
        print(f"Signup Status: {response.status} - {await response.json()}")

# Function to send the Login request (200 OK)``
async def client_login(session):
    data = {
        "username": "user1",
        "password": "password123"
    }
    async with session.post(f"{API_URL}/api/login", json=data) as response:
        print(f"Login Status: {response.status} - {await response.json()}")

# Function to send request with missing password (400 Bad Request)
async def client_missing_password(session):
    data = {
        "username": "user1"
    }
    async with session.post(f"{API_URL}/api/login", json=data) as response:
        print(f"Missing Password Status: {response.status} - {await response.json()}")

# Function to send Unauthorized request (401)
async def client_unauthorized_user(session):
    data = {
        "username": "user1",
        "password": "wrongpassword"
    }
    async with session.post(f"{API_URL}/api/login", json=data) as response:
        print(f"Unauthorized User Status: {response.status} - {await response.json()}")

# Function to send Signup with missing email (400 Bad Request)
async def client_signup_missing_email(session):
    data = {
        "username": "newuser2",
        "password": "password123"
    }
    async with session.post(f"{API_URL}/api/signup", json=data) as response:
        print(f"Signup Missing Email Status: {response.status} - {await response.json()}")

# Function to simulate Admin Access request (200 OK)
async def client_admin_access(session):
    data = {
        "username": "admin",
        "password": "admin123"
    }
    async with session.post(f"{API_URL}/api/admin", json=data) as response:
        print(f"Admin Access Status: {response.status} - {await response.json()}")

# Function to simulate Forbidden Admin Access request (403)
async def client_forbidden_admin(session):
    data = {
        "username": "user1",
        "password": "password123"
    }
    async with session.post(f"{API_URL}/api/admin", json=data) as response:
        print(f"Forbidden Admin Access Status: {response.status} - {await response.json()}")

# Function to simulate high traffic load using asyncio and aiohttp
async def send_requests():
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(100):  # 100 concurrent clients
            tasks.append(client_signup(session))
            tasks.append(client_login(session))
            tasks.append(client_missing_password(session))
            tasks.append(client_unauthorized_user(session))
            tasks.append(client_signup_missing_email(session))
            tasks.append(client_admin_access(session))
            tasks.append(client_forbidden_admin(session))
        await asyncio.gather(*tasks)

async def infinite_load_test():
    while True:
        print("Starting a new batch of requests...")
        await send_requests()
        await asyncio.sleep(2)  # <-- small pause between batches (2 seconds)

def run_load_test():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(infinite_load_test())

if __name__ == "__main__":
    run_load_test()

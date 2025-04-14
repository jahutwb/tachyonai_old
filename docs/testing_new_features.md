# Testing the New Features

This document provides guidance on how to test the new features added to the TachyonAI application.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setting Up the Test Environment](#setting-up-the-test-environment)
- [Testing the Notifications System](#testing-the-notifications-system)
  - [Testing the Notifications API](#testing-the-notifications-api)
  - [Testing Notification Creation](#testing-notification-creation)
- [Testing the Standardized Error Handling](#testing-the-standardized-error-handling)
  - [Testing Error Responses](#testing-error-responses)
  - [Testing Error Handling Middleware](#testing-error-handling-middleware)
- [Testing the Configuration System](#testing-the-configuration-system)
  - [Testing Config Loading](#testing-config-loading)
  - [Testing Environment Variables](#testing-environment-variables)
- [Testing Database Migrations](#testing-database-migrations)
  - [Testing Migration Creation](#testing-migration-creation)
  - [Testing Migration Application](#testing-migration-application)
- [Running All Tests](#running-all-tests)

## Prerequisites

Before testing the new features, make sure you have the following:

- Python 3.8 or higher
- Virtual environment with all dependencies installed
- Access to the TachyonAI codebase
- Database with the latest migrations applied

## Setting Up the Test Environment

To set up the test environment, follow these steps:

1. Clone the repository:

```bash
git clone git@github.com:yourusername/tachyonai.git
cd tachyonai
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Apply migrations:

```bash
alembic upgrade head
```

5. Load test data:

```bash
python scripts/load_test_data.py
```

## Testing the Notifications System

### Testing the Notifications API

To test the notifications API, run the notification API tests:

```bash
python -m pytest tests/integration/test_api_notifications.py -v
```

This will run the following tests:

- `test_get_notifications`: Tests getting all notifications for the current user
- `test_get_unread_notifications`: Tests getting only unread notifications
- `test_mark_notification_read`: Tests marking a notification as read
- `test_mark_all_notifications_read`: Tests marking all notifications as read
- `test_delete_notification`: Tests deleting a notification
- `test_delete_all_notifications`: Tests deleting all notifications

### Testing Notification Creation

To test notification creation, you can use the following script:

```python
import asyncio
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import User, NotificationTypeEnum
from backend.routers.notifications import create_notification

async def test_notification_creation():
    # Get a database session
    db = next(get_db())
    
    try:
        # Get a user
        user = db.query(User).first()
        if not user:
            print("No users found in the database")
            return
        
        # Create notifications of different types
        create_notification(
            db=db,
            user_id=user.id,
            type=NotificationTypeEnum.INFO,
            message="This is an informational notification",
            title="Information",
            data={"additional_info": "Some additional information"}
        )
        
        create_notification(
            db=db,
            user_id=user.id,
            type=NotificationTypeEnum.WARNING,
            message="This is a warning notification",
            title="Warning",
            data={"additional_info": "Some additional information"}
        )
        
        create_notification(
            db=db,
            user_id=user.id,
            type=NotificationTypeEnum.ERROR,
            message="This is an error notification",
            title="Error",
            data={"additional_info": "Some additional information"}
        )
        
        create_notification(
            db=db,
            user_id=user.id,
            type=NotificationTypeEnum.SUCCESS,
            message="This is a success notification",
            title="Success",
            data={"additional_info": "Some additional information"}
        )
        
        print(f"Created 4 notifications for user {user.username}")
    finally:
        db.close()

# Run the test
asyncio.run(test_notification_creation())
```

Save this script as `test_notification_creation.py` and run it:

```bash
python test_notification_creation.py
```

## Testing the Standardized Error Handling

### Testing Error Responses

To test error responses, you can use the following script:

```python
import requests
import json

def test_error_responses():
    base_url = "http://localhost:8000"
    
    # Test authentication error
    response = requests.post(
        f"{base_url}/token",
        data={"username": "nonexistent", "password": "wrong_password"}
    )
    print_response("Authentication Error", response)
    
    # Test authorization error
    response = requests.get(
        f"{base_url}/api/users/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    print_response("Authorization Error", response)
    
    # Test not found error
    response = requests.get(f"{base_url}/api/nonexistent")
    print_response("Not Found Error", response)
    
    # Test validation error
    response = requests.post(
        f"{base_url}/token",
        data={"username": "test_user"}  # Missing password
    )
    print_response("Validation Error", response)

def print_response(title, response):
    print(f"\n=== {title} ===")
    print(f"Status Code: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        # Check for standardized error format
        if "code" in data and "message" in data:
            print(f"Error Code: {data['code']}")
            print(f"Error Message: {data['message']}")
            if "details" in data:
                print(f"Error Details: {json.dumps(data['details'], indent=2)}")
            if "timestamp" in data:
                print(f"Timestamp: {data['timestamp']}")
        else:
            print("Response is not in standardized error format")
    except ValueError:
        print(f"Response is not JSON: {response.text}")

# Run the test
test_error_responses()
```

Save this script as `test_error_responses.py` and run it:

```bash
python test_error_responses.py
```

### Testing Error Handling Middleware

To test the error handling middleware, you can use the following script:

```python
import requests
import json

def test_error_handling_middleware():
    base_url = "http://localhost:8000"
    
    # Test generic exception
    response = requests.get(f"{base_url}/api/test_error")
    print_response("Generic Exception", response)
    
    # Test validation error
    response = requests.post(
        f"{base_url}/api/rounds/choice",
        json={"invalid": "data"}
    )
    print_response("Validation Error", response)

def print_response(title, response):
    print(f"\n=== {title} ===")
    print(f"Status Code: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        
        # Check for standardized error format
        if "code" in data and "message" in data:
            print(f"Error Code: {data['code']}")
            print(f"Error Message: {data['message']}")
            if "details" in data:
                print(f"Error Details: {json.dumps(data['details'], indent=2)}")
            if "timestamp" in data:
                print(f"Timestamp: {data['timestamp']}")
        else:
            print("Response is not in standardized error format")
    except ValueError:
        print(f"Response is not JSON: {response.text}")

# Run the test
test_error_handling_middleware()
```

Save this script as `test_error_handling_middleware.py` and run it:

```bash
python test_error_handling_middleware.py
```

## Testing the Configuration System

### Testing Config Loading

To test config loading, you can use the following script:

```python
from backend.config import Config, ConfigSettingEnum, EnvironmentEnum, LogLevelEnum

def test_config_loading():
    # Load configuration
    Config.load()
    
    # Print all configuration settings
    print("=== Configuration Settings ===")
    for setting in ConfigSettingEnum:
        value = Config.get(setting)
        print(f"{setting.value}: {value}")
    
    # Test convenience methods
    print("\n=== Convenience Methods ===")
    print(f"Debug Mode: {Config.is_debug()}")
    print(f"Environment: {Config.get_environment()}")
    print(f"Production Mode: {Config.is_production()}")
    print(f"Log Level: {Config.get_log_level()}")
    print(f"Database URL: {Config.get_database_url()}")
    print(f"Secret Key: {Config.get_secret_key()}")
    print(f"Access Token Expire Minutes: {Config.get_access_token_expire_minutes()}")
    print(f"CORS Origins: {Config.get_cors_origins()}")
    print(f"Static Directory: {Config.get_static_dir()}")
    print(f"Templates Directory: {Config.get_templates_dir()}")
    print(f"Upload Directory: {Config.get_upload_dir()}")
    print(f"Max Upload Size: {Config.get_max_upload_size()}")
    print(f"Allowed Extensions: {Config.get_allowed_extensions()}")

# Run the test
test_config_loading()
```

Save this script as `test_config_loading.py` and run it:

```bash
python test_config_loading.py
```

### Testing Environment Variables

To test environment variables, you can use the following script:

```bash
#!/bin/bash

# Set environment variables
export TACHYONAI_DEBUG=false
export TACHYONAI_ENVIRONMENT=production
export TACHYONAI_LOG_LEVEL=INFO
export TACHYONAI_DATABASE_URL=sqlite:///test.db
export TACHYONAI_SECRET_KEY=test-secret-key
export TACHYONAI_ACCESS_TOKEN_EXPIRE_MINUTES=60
export TACHYONAI_CORS_ORIGINS=http://localhost:8000,http://localhost:3000
export TACHYONAI_STATIC_DIR=static
export TACHYONAI_TEMPLATES_DIR=templates
export TACHYONAI_UPLOAD_DIR=uploads
export TACHYONAI_MAX_UPLOAD_SIZE=5242880
export TACHYONAI_ALLOWED_EXTENSIONS=jpg,jpeg,png

# Run the config loading test
python test_config_loading.py

# Unset environment variables
unset TACHYONAI_DEBUG
unset TACHYONAI_ENVIRONMENT
unset TACHYONAI_LOG_LEVEL
unset TACHYONAI_DATABASE_URL
unset TACHYONAI_SECRET_KEY
unset TACHYONAI_ACCESS_TOKEN_EXPIRE_MINUTES
unset TACHYONAI_CORS_ORIGINS
unset TACHYONAI_STATIC_DIR
unset TACHYONAI_TEMPLATES_DIR
unset TACHYONAI_UPLOAD_DIR
unset TACHYONAI_MAX_UPLOAD_SIZE
unset TACHYONAI_ALLOWED_EXTENSIONS

# Run the config loading test again to see default values
python test_config_loading.py
```

Save this script as `test_environment_variables.sh` and run it:

```bash
bash test_environment_variables.sh
```

## Testing Database Migrations

### Testing Migration Creation

To test migration creation, you can use the following commands:

```bash
# Create a new migration
alembic revision --autogenerate -m "Test migration"

# Check that the migration file was created
ls -la migrations/versions/
```

### Testing Migration Application

To test migration application, you can use the following commands:

```bash
# Apply the migration
alembic upgrade head

# Check the current migration
alembic current

# Rollback the migration
alembic downgrade -1

# Check the current migration
alembic current

# Apply the migration again
alembic upgrade head

# Check the current migration
alembic current
```

## Running All Tests

To run all tests, use the following command:

```bash
python -m pytest
```

This will run all unit tests and integration tests, including the new tests for the notifications API and error handling.

# Using the New Features

This document provides guidance on how to use the new features added to the TachyonAI application.

## Table of Contents

- [Notifications System](#notifications-system)
  - [Getting Notifications](#getting-notifications)
  - [Marking Notifications as Read](#marking-notifications-as-read)
  - [Deleting Notifications](#deleting-notifications)
  - [Creating Notifications](#creating-notifications)
- [Standardized Error Handling](#standardized-error-handling)
  - [Error Response Format](#error-response-format)
  - [Error Codes](#error-codes)
  - [Handling Errors in Frontend Code](#handling-errors-in-frontend-code)
- [Configuration System](#configuration-system)
  - [Using the Config Class](#using-the-config-class)
  - [Environment Variables](#environment-variables)
- [Database Migrations](#database-migrations)
  - [Creating Migrations](#creating-migrations)
  - [Applying Migrations](#applying-migrations)

## Notifications System

The notifications system allows you to send and receive notifications for users. Notifications can be used to inform users about important events, such as successful operations, warnings, or errors.

### Getting Notifications

To get notifications for the current user, send a GET request to the `/api/notifications` endpoint:

```javascript
async function getNotifications(unreadOnly = false) {
  try {
    const url = unreadOnly ? '/api/notifications?unread_only=true' : '/api/notifications';
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to get notifications');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error getting notifications:', error);
    throw error;
  }
}
```

### Marking Notifications as Read

To mark a notification as read, send a POST request to the `/api/notifications/mark-read/{notification_id}` endpoint:

```javascript
async function markNotificationRead(notificationId) {
  try {
    const response = await fetch(`/api/notifications/mark-read/${notificationId}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to mark notification as read');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error marking notification as read:', error);
    throw error;
  }
}
```

To mark all notifications as read, send a POST request to the `/api/notifications/mark-all-read` endpoint:

```javascript
async function markAllNotificationsRead() {
  try {
    const response = await fetch('/api/notifications/mark-all-read', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to mark all notifications as read');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error marking all notifications as read:', error);
    throw error;
  }
}
```

### Deleting Notifications

To delete a notification, send a DELETE request to the `/api/notifications/{notification_id}` endpoint:

```javascript
async function deleteNotification(notificationId) {
  try {
    const response = await fetch(`/api/notifications/${notificationId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to delete notification');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error deleting notification:', error);
    throw error;
  }
}
```

To delete all notifications, send a DELETE request to the `/api/notifications` endpoint:

```javascript
async function deleteAllNotifications() {
  try {
    const response = await fetch('/api/notifications', {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to delete all notifications');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error deleting all notifications:', error);
    throw error;
  }
}
```

### Creating Notifications

To create a notification for a user, use the `create_notification` function in the `backend/routers/notifications.py` file:

```python
from backend.routers.notifications import create_notification
from backend.models import NotificationTypeEnum

# Create a notification
create_notification(
    db=db,
    user_id=user.id,
    type=NotificationTypeEnum.INFO,
    message="This is an informational notification",
    title="Information",
    data={"additional_info": "Some additional information"}
)
```

## Standardized Error Handling

The standardized error handling system provides a consistent way to handle errors across the application. All API errors are returned in a standardized format with a code, message, details, and timestamp.

### Error Response Format

All API errors are returned in the following format:

```json
{
  "code": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "additional_info": "Additional error details"
  },
  "timestamp": "2023-01-01T12:00:00Z"
}
```

### Error Codes

The API uses the following error codes:

| Code | HTTP Status | Description |
|------|-------------|-------------|
| AUTHENTICATION_ERROR | 401 | Authentication error (e.g., invalid credentials) |
| AUTHORIZATION_ERROR | 403 | Authorization error (e.g., insufficient permissions) |
| VALIDATION_ERROR | 422 | Validation error (e.g., invalid input) |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource conflict (e.g., duplicate username) |
| SERVER_ERROR | 500 | Server error |
| BAD_REQUEST | 400 | Bad request (e.g., invalid parameters) |
| RATE_LIMIT | 429 | Rate limit exceeded |
| SERVICE_UNAVAILABLE | 503 | Service unavailable |

### Handling Errors in Frontend Code

To handle errors in frontend code, check the error response for the `code` field:

```javascript
async function fetchData(url) {
  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${getToken()}`
      }
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      
      // Handle different error codes
      switch (errorData.code) {
        case 'AUTHENTICATION_ERROR':
          // Handle authentication error (e.g., redirect to login page)
          redirectToLogin();
          break;
        case 'AUTHORIZATION_ERROR':
          // Handle authorization error (e.g., show access denied message)
          showAccessDeniedMessage();
          break;
        case 'NOT_FOUND':
          // Handle not found error (e.g., show 404 page)
          showNotFoundPage();
          break;
        default:
          // Handle other errors
          showErrorMessage(errorData.message);
          break;
      }
      
      throw new Error(errorData.message);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching data:', error);
    throw error;
  }
}
```

## Configuration System

The configuration system provides a centralized way to manage application configuration. It supports loading configuration from environment variables and provides default values for all settings.

### Using the Config Class

To use the Config class, import it from the `backend/config.py` file:

```python
from backend.config import Config, ConfigSettingEnum

# Get a configuration setting
debug_mode = Config.get(ConfigSettingEnum.DEBUG)

# Set a configuration setting
Config.set(ConfigSettingEnum.DEBUG, True)

# Use convenience methods
if Config.is_debug():
    print("Debug mode is enabled")

if Config.is_production():
    print("Running in production mode")

# Get specific settings
database_url = Config.get_database_url()
secret_key = Config.get_secret_key()
access_token_expire_minutes = Config.get_access_token_expire_minutes()
```

### Environment Variables

The Config class loads configuration from environment variables with the prefix `TACHYONAI_`. For example, to set the `DEBUG` setting, set the `TACHYONAI_DEBUG` environment variable:

```bash
export TACHYONAI_DEBUG=true
export TACHYONAI_ENVIRONMENT=production
export TACHYONAI_LOG_LEVEL=INFO
export TACHYONAI_DATABASE_URL=postgresql://user:password@localhost/tachyonai
export TACHYONAI_SECRET_KEY=your-secret-key
export TACHYONAI_ACCESS_TOKEN_EXPIRE_MINUTES=30
export TACHYONAI_CORS_ORIGINS=http://localhost:8000,http://localhost:3000
```

## Database Migrations

The database migrations system uses Alembic to manage database schema changes. It allows you to create and apply migrations to update the database schema.

### Creating Migrations

To create a new migration, use the `alembic revision` command:

```bash
# Create a new migration with autogenerate
alembic revision --autogenerate -m "Add new table"

# Create a new migration without autogenerate
alembic revision -m "Add new table"
```

The migration file will be created in the `migrations/versions` directory. Edit the file to add the necessary changes.

### Applying Migrations

To apply migrations, use the `alembic upgrade` command:

```bash
# Apply all migrations
alembic upgrade head

# Apply specific migration
alembic upgrade <revision>

# Rollback to previous migration
alembic downgrade -1

# Rollback to specific migration
alembic downgrade <revision>
```

To check the current migration status, use the `alembic current` command:

```bash
alembic current
```

To see the migration history, use the `alembic history` command:

```bash
alembic history
```

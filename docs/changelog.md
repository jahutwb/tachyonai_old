# Changelog

## [1.0.0] - 2023-07-01

### Added

- **Notifications System**
  - Added NotificationTypeEnum for categorizing notifications (INFO, WARNING, ERROR, SUCCESS)
  - Created Notification model and schema for storing and retrieving user notifications
  - Implemented notifications router with endpoints for:
    - Getting user notifications
    - Marking notifications as read
    - Deleting notifications
  - Added database migration for the notifications table
  - Added comprehensive tests for the notification API

- **Standardized Error Handling**
  - Added ErrorCodeEnum for categorizing API errors
  - Created ErrorResponse schema for standardized error responses
  - Implemented error handling middleware for consistent error responses
  - Added utility functions for error handling
  - Updated all endpoints to use the standardized error handling

- **Configuration System**
  - Added ConfigSettingEnum, EnvironmentEnum, and LogLevelEnum for application configuration
  - Created Config class for managing application configuration
  - Updated the application to use the Config class for configuration settings

- **Database Migrations**
  - Set up Alembic for database migrations
  - Created initial migration for the notifications table

### Changed

- **Type Safety Improvements**
  - Converted User Action string literals to ActionEnum
  - Converted Side string literals to SideEnum
  - Converted Session Status string literals to SessionStatusEnum
  - Converted Image Type string literals to ImageTypeEnum
  - Created TokenTypeEnum for Authentication
  - Updated all relevant code to use the new enums

- **API Response Format**
  - Updated error responses to use a standardized format with code, message, details, and timestamp
  - Added custom JSON encoder for handling datetime objects in responses

- **Documentation**
  - Updated API documentation to reflect all changes
  - Added detailed documentation for the notifications API
  - Added documentation for the error handling system

### Fixed

- Fixed JSON serialization issues with datetime objects
- Fixed authentication error handling in the token endpoint
- Updated tests to work with the new error response format

## [0.9.0] - 2023-06-01

Initial release of the TachyonAI API.

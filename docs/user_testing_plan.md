# User Testing Plan: RoundResult Schema Updates

## Overview

This document outlines the testing plan for the recent updates to the RoundResult schema, particularly the transition from string literals to enum values for the `result` and `session_status` fields. The plan includes test scenarios, edge cases, and a testing checklist to ensure that the changes work correctly in all scenarios.

## Test Environments

- **Development Environment**: Initial testing in local development environment
- **Staging Environment**: Pre-production testing with realistic data
- **Production Environment**: Final verification after deployment

## Test Scenarios

### 1. Basic Functionality Tests

#### 1.1 Successful Round Completion

**Objective**: Verify that a successful round is correctly processed and displayed.

**Steps**:
1. Start a new session
2. Complete a round with a successful outcome (e.g., choose BUY when price increases)
3. Verify that the result is displayed as "SUCCESS" in the UI
4. Verify that the success counter is incremented
5. Verify that the session profit factor is updated correctly
6. Verify that the remaining pairs count remains unchanged

**Expected Result**: The round is marked as successful, the success counter increases, and the UI displays the success message with the correct profit percentage.

#### 1.2 Failed Round Completion

**Objective**: Verify that a failed round is correctly processed and displayed.

**Steps**:
1. Start a new session
2. Complete a round with a failed outcome (e.g., choose BUY when price decreases)
3. Verify that the result is displayed as "FAILURE" in the UI
4. Verify that the failure counter is incremented
5. Verify that the session profit factor is updated correctly
6. Verify that the remaining pairs count is decremented

**Expected Result**: The round is marked as failed, the failure counter increases, the remaining pairs count decreases, and the UI displays the failure message with the correct loss percentage.

### 2. Session Status Tests

#### 2.1 Active Session

**Objective**: Verify that an active session is correctly identified and processed.

**Steps**:
1. Start a new session
2. Complete a few rounds
3. Verify that the session status is displayed as "ACTIVE"
4. Verify that new rounds can be started

**Expected Result**: The session remains active, and new rounds can be started.

#### 2.2 Completed Session

**Objective**: Verify that a session is correctly marked as completed when all pairs are used.

**Steps**:
1. Start a new session
2. Complete rounds until the remaining pairs count reaches 0
3. Verify that the session status is displayed as "COMPLETED"
4. Verify that no new rounds can be started
5. Verify that the user is redirected to the summary page

**Expected Result**: The session is marked as completed, no new rounds can be started, and the user is redirected to the summary page.

### 3. Edge Cases

#### 3.1 Network Interruption

**Objective**: Verify that the application handles network interruptions gracefully.

**Steps**:
1. Start a new session
2. Disable network connection
3. Complete a round
4. Verify that an appropriate error message is displayed
5. Re-enable network connection
6. Verify that the application recovers and allows the user to continue

**Expected Result**: The application displays an error message when the network is disconnected and recovers when the connection is restored.

#### 3.2 Session Expiration

**Objective**: Verify that the application handles session expiration gracefully.

**Steps**:
1. Start a new session
2. Wait for the session token to expire (or manually expire it)
3. Complete a round
4. Verify that the user is prompted to log in again
5. Log in again
6. Verify that the user can continue the session

**Expected Result**: The application prompts the user to log in again when the session expires and allows the user to continue after logging in.

#### 3.3 Concurrent Sessions

**Objective**: Verify that the application handles concurrent sessions correctly.

**Steps**:
1. Start a session in one browser
2. Start another session in a different browser or incognito window
3. Complete rounds in both sessions
4. Verify that the results are correctly tracked for each session

**Expected Result**: Each session is tracked independently, and the results are correctly associated with the respective sessions.

### 4. Performance Tests

#### 4.1 Response Time

**Objective**: Verify that the application responds quickly to user actions.

**Steps**:
1. Start a new session
2. Complete multiple rounds in quick succession
3. Measure the response time for each round

**Expected Result**: The application responds within acceptable time limits (e.g., < 500ms).

#### 4.2 Load Testing

**Objective**: Verify that the application can handle multiple concurrent users.

**Steps**:
1. Simulate multiple users completing rounds simultaneously
2. Monitor server performance and response times

**Expected Result**: The application maintains acceptable performance under load.

## Testing Checklist

### Frontend Testing

- [ ] Verify that the UI correctly displays "SUCCESS" for successful rounds
- [ ] Verify that the UI correctly displays "FAILURE" for failed rounds
- [ ] Verify that the success counter increments correctly
- [ ] Verify that the failure counter increments correctly
- [ ] Verify that the session profit factor updates correctly
- [ ] Verify that the remaining pairs count updates correctly
- [ ] Verify that the stimulus image is displayed correctly
- [ ] Verify that the session status is displayed correctly
- [ ] Verify that the application redirects to the summary page when the session is completed
- [ ] Verify that error messages are displayed appropriately
- [ ] Verify that the application recovers gracefully from network interruptions
- [ ] Verify that the application handles session expiration correctly
- [ ] Verify that the application works correctly on different browsers (Chrome, Firefox, Safari)
- [ ] Verify that the application works correctly on different devices (desktop, tablet, mobile)

### Backend Testing

- [ ] Verify that the `/rounds/choice` endpoint correctly processes successful rounds
- [ ] Verify that the `/rounds/choice` endpoint correctly processes failed rounds
- [ ] Verify that the session status is updated correctly
- [ ] Verify that the remaining pairs count is updated correctly
- [ ] Verify that the session profit factor is calculated correctly
- [ ] Verify that the stimulus URL is generated correctly
- [ ] Verify that the endpoint returns the correct HTTP status codes for different scenarios
- [ ] Verify that the endpoint handles invalid input correctly
- [ ] Verify that the endpoint handles authentication errors correctly
- [ ] Verify that the endpoint handles database errors correctly
- [ ] Verify that the endpoint handles concurrent requests correctly
- [ ] Verify that the endpoint performs within acceptable time limits

### Database Testing

- [ ] Verify that round results are correctly stored in the database
- [ ] Verify that session statistics are correctly updated in the database
- [ ] Verify that the database can handle the expected load
- [ ] Verify that database queries are optimized for performance

## Test Data

### Sample Round Result (Success)

```json
{
  "round_id": 456,
  "session_id": 123,
  "start_price": 50000.0,
  "end_price": 50250.0,
  "profit_fraction": 0.005,
  "result": "SUCCESS",
  "remaining_pairs": 9,
  "session_profit_factor": 1.055,
  "stimulus_url": "http://example.com/api/images/789/full?token=xyz",
  "session_status": "ACTIVE"
}
```

### Sample Round Result (Failure)

```json
{
  "round_id": 457,
  "session_id": 123,
  "start_price": 50250.0,
  "end_price": 50000.0,
  "profit_fraction": -0.005,
  "result": "FAILURE",
  "remaining_pairs": 8,
  "session_profit_factor": 1.049,
  "stimulus_url": "http://example.com/api/images/790/full?token=xyz",
  "session_status": "ACTIVE"
}
```

## Test Reporting

For each test scenario, record the following information:

- Test ID
- Test description
- Steps performed
- Expected result
- Actual result
- Pass/Fail status
- Comments/Observations
- Screenshots (if applicable)

## Issue Tracking

For any issues found during testing, create a detailed bug report including:

- Issue description
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (browser, OS, device)
- Screenshots or videos
- Severity level (Critical, High, Medium, Low)
- Priority level (Immediate, High, Medium, Low)

## Test Schedule

1. **Development Testing**: Perform basic functionality tests in the development environment
2. **Code Review**: Review the code changes for potential issues
3. **Unit Testing**: Run automated unit tests to verify individual components
4. **Integration Testing**: Test the interaction between components
5. **System Testing**: Test the entire system end-to-end
6. **User Acceptance Testing**: Have end users test the application
7. **Performance Testing**: Test the application under load
8. **Security Testing**: Verify that the application is secure
9. **Regression Testing**: Verify that existing functionality still works correctly

## Conclusion

This testing plan provides a comprehensive approach to verifying the RoundResult schema updates. By following this plan, we can ensure that the changes work correctly in all scenarios and that the application provides a seamless user experience.

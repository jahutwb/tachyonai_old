# RoundResult Schema Test Script

This document provides a step-by-step test script for verifying the RoundResult schema changes, particularly the transition from string literals to enum values for the `result` and `session_status` fields.

## Prerequisites

- Access to the application in a test environment
- Test user account with appropriate permissions
- Chrome DevTools or similar browser developer tools for inspecting network requests
- Basic understanding of the application's functionality

## Test Script

### Test 1: Verify Successful Round Processing

1. **Login to the Application**
   - Open the application in a web browser
   - Log in with valid credentials
   - Verify that you are redirected to the main dashboard

2. **Start a New Session**
   - Click on the "New Session" button
   - Verify that a new session is created
   - Note the session ID for reference

3. **Complete a Successful Round**
   - When presented with a round, choose the option that is likely to result in success
     - If the left side shows "BUY", choose it when you expect the price to increase
     - If the right side shows "SELL", choose it when you expect the price to decrease
   - Wait for the round to complete

4. **Verify API Response**
   - Open Chrome DevTools (F12 or Ctrl+Shift+I)
   - Go to the Network tab
   - Find the POST request to `/api/rounds/choice`
   - Click on the request to view details
   - Go to the Response tab
   - Verify that the response includes:
     ```json
     {
       "result": "SUCCESS",
       "session_status": "ACTIVE"
     }
     ```
   - Note: The actual values may be part of a larger JSON object

5. **Verify UI Display**
   - Verify that the UI displays "Sukces" (or equivalent success message)
   - Verify that the success counter is incremented
   - Verify that the session profit factor is updated
   - Verify that the remaining pairs count remains unchanged
   - Verify that the appropriate stimulus image is displayed

6. **Verify Console Logs**
   - Check the browser console for any errors or warnings
   - Verify that there are no errors related to processing the result

### Test 2: Verify Failed Round Processing

1. **Continue the Session**
   - Start another round in the same session

2. **Complete a Failed Round**
   - When presented with a round, choose the option that is likely to result in failure
     - If the left side shows "BUY", choose it when you expect the price to decrease
     - If the right side shows "SELL", choose it when you expect the price to increase
   - Wait for the round to complete

3. **Verify API Response**
   - Open Chrome DevTools (F12 or Ctrl+Shift+I)
   - Go to the Network tab
   - Find the POST request to `/api/rounds/choice`
   - Click on the request to view details
   - Go to the Response tab
   - Verify that the response includes:
     ```json
     {
       "result": "FAILURE",
       "session_status": "ACTIVE"
     }
     ```
   - Note: The actual values may be part of a larger JSON object

4. **Verify UI Display**
   - Verify that the UI displays "Porażka" (or equivalent failure message)
   - Verify that the failure counter is incremented
   - Verify that the session profit factor is updated
   - Verify that the remaining pairs count is decremented
   - Verify that the appropriate stimulus image is displayed

5. **Verify Console Logs**
   - Check the browser console for any errors or warnings
   - Verify that there are no errors related to processing the result

### Test 3: Verify Session Completion

1. **Complete Remaining Rounds**
   - Continue completing rounds until the remaining pairs count reaches 0
   - Note: You may need to deliberately fail rounds to reduce the count faster

2. **Verify Session Completion**
   - Verify that the session status changes to "COMPLETED"
   - Verify that you are redirected to the summary page
   - Verify that the summary page displays the correct statistics
   - Verify that you cannot start new rounds in this session

3. **Verify API Response**
   - Open Chrome DevTools (F12 or Ctrl+Shift+I)
   - Go to the Network tab
   - Find the last POST request to `/api/rounds/choice`
   - Click on the request to view details
   - Go to the Response tab
   - Verify that the response includes:
     ```json
     {
       "session_status": "COMPLETED"
     }
     ```
   - Note: The actual values may be part of a larger JSON object

### Test 4: Verify Summary Page

1. **Navigate to the Summary Page**
   - If not automatically redirected, navigate to the summary page for the completed session

2. **Verify Round Results**
   - Verify that each round's result is correctly displayed as "SUKCES" or "PORAŻKA"
   - Verify that the success and failure counts match the expected values
   - Verify that the session profit factor is calculated correctly
   - Verify that the session status is displayed as "COMPLETED"

### Test 5: Verify Statistics Page

1. **Navigate to the Statistics Page**
   - Click on the "Statistics" or "History" link in the navigation menu

2. **Verify Session List**
   - Verify that the completed session is listed
   - Verify that the session status is displayed as "COMPLETED"
   - Verify that the session statistics are correct

3. **View Session Details**
   - Click on the session to view details
   - Verify that each round's result is correctly displayed as "SUKCES" or "PORAŻKA"
   - Verify that the success and failure counts match the expected values
   - Verify that the session profit factor is calculated correctly

### Test 6: Verify Error Handling

1. **Simulate Network Error**
   - Start a new session
   - Disable network connection (e.g., turn off Wi-Fi or use Chrome DevTools to simulate offline mode)
   - Complete a round
   - Verify that an appropriate error message is displayed
   - Re-enable network connection
   - Verify that the application recovers and allows the user to continue

2. **Simulate Invalid Input**
   - Use Chrome DevTools to modify the request payload before sending
   - Change the `side` value to an invalid value (e.g., "MIDDLE" instead of "LEFT" or "RIGHT")
   - Verify that the application handles the error gracefully
   - Verify that an appropriate error message is displayed

## Test Results

For each test, record the following information:

- Test ID
- Test date and time
- Tester name
- Environment details (browser, OS, device)
- Pass/Fail status
- Comments/Observations
- Screenshots (if applicable)

## Issue Reporting

If any issues are found during testing, report them with the following information:

- Issue description
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (browser, OS, device)
- Screenshots or videos
- Severity level (Critical, High, Medium, Low)
- Priority level (Immediate, High, Medium, Low)

## Conclusion

This test script provides a structured approach to verifying the RoundResult schema changes. By following this script, testers can ensure that the changes work correctly in all scenarios and that the application provides a seamless user experience.

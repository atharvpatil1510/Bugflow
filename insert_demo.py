from db import get_connection

bugs = [
    ("Authentication", "Login button not responding", "Clicking Login with valid credentials does nothing.", "High", "Open"),
    ("Authentication", "Incorrect password accepted", "Login validation accepts an incorrect password.", "Critical", "Open"),
    ("Authentication", "Password reset email missing", "Password reset email is not received.", "Medium", "In Progress"),
    ("Authentication", "Session expires too early", "User is logged out after a short period.", "Medium", "Open"),
    ("Authentication", "Logout button not working", "Clicking Logout does not end the session.", "High", "Resolved"),
    ("Authentication", "Login page crashes", "Login page fails to load for some users.", "Critical", "Open"),
    ("Authentication", "Email validation missing", "Invalid email formats are accepted during login.", "Low", "Open"),
    ("Authentication", "Remember me not working", "Login session is not remembered after reopening the browser.", "Low", "In Progress"),
    ("Authentication", "Account lockout not triggered", "Repeated failed login attempts do not lock the account.", "High", "Open"),
    ("Authentication", "Password field shows text", "Password characters are visible instead of masked.", "Medium", "Resolved"),

    ("Shopping", "Checkout button not working", "Clicking Place Order produces no response.", "Critical", "Open"),
    ("Shopping", "Cart total calculated incorrectly", "Cart total does not include all item prices.", "High", "In Progress"),
    ("Shopping", "Duplicate order created", "Submitting an order twice creates duplicate records.", "Critical", "Open"),
    ("Shopping", "Product image missing", "Some products display broken images.", "Low", "Open"),
    ("Shopping", "Quantity update fails", "Changing product quantity does not update the cart.", "Medium", "Open"),
    ("Shopping", "Coupon code rejected", "Valid discount codes are rejected at checkout.", "Medium", "Resolved"),
    ("Shopping", "Out-of-stock item purchasable", "Users can order products with zero stock.", "Critical", "Open"),
    ("Shopping", "Shipping fee incorrect", "Shipping charges are calculated incorrectly.", "High", "In Progress"),
    ("Shopping", "Order confirmation missing", "Successful orders do not show confirmation.", "Medium", "Open"),
    ("Shopping", "Cart becomes empty", "Cart items disappear after refreshing the page.", "High", "Open"),

    ("Performance", "Dashboard loads slowly", "Dashboard takes over 15 seconds to load many records.", "High", "Open"),
    ("Performance", "Search results delayed", "Search results take too long to appear.", "Medium", "In Progress"),
    ("Performance", "Memory usage increases", "Memory consumption grows during long sessions.", "High", "Open"),
    ("Performance", "Large report export hangs", "Exporting thousands of records freezes the page.", "High", "Open"),
    ("Performance", "API response is slow", "Bug listing API responds slowly under load.", "Medium", "Open"),
    ("Performance", "Repeated requests overload server", "Repeated requests cause server response delays.", "Critical", "In Progress"),
    ("Performance", "Pagination loads slowly", "Moving to the next page takes several seconds.", "Low", "Resolved"),
    ("Performance", "Dashboard chart freezes", "Charts become unresponsive with large datasets.", "Medium", "Open"),
    ("Performance", "Application startup delayed", "Application takes too long to become available.", "Medium", "Open"),
    ("Performance", "Database query timeout", "A report query times out for large result sets.", "Critical", "Open"),

    ("User Interface", "Navigation overlaps table", "Mobile navigation overlaps the issues table.", "Medium", "Open"),
    ("User Interface", "Submit button has wrong color", "Submit button displays an unexpected color.", "Low", "Resolved"),
    ("User Interface", "Text clipped on mobile", "Long issue titles are cut off on small screens.", "Low", "Open"),
    ("User Interface", "Modal cannot be closed", "Close icon does not dismiss the dialog.", "Medium", "Open"),
    ("User Interface", "Dropdown options invisible", "Dropdown menu text is not readable.", "Medium", "In Progress"),
    ("User Interface", "Dark mode contrast issue", "Text contrast is too low in dark mode.", "Low", "Open"),
    ("User Interface", "Form labels missing", "Some input fields do not show labels.", "Low", "Open"),
    ("User Interface", "Page layout breaks on tablet", "Dashboard layout is misaligned on tablet screens.", "Medium", "Open"),
    ("User Interface", "Error message not displayed", "Invalid form submission gives no visible feedback.", "Medium", "Resolved"),
    ("User Interface", "Loading indicator never disappears", "Spinner remains visible after data loads.", "Medium", "Open"),

    ("API", "Bug creation API returns 500", "Submitting valid bug data causes an internal server error.", "High", "Open"),
    ("API", "Missing required field accepted", "API creates a report without a title.", "High", "In Progress"),
    ("API", "Invalid status accepted", "API accepts a status that is not supported.", "Medium", "Open"),
    ("API", "Incorrect response format", "API response does not match the documented JSON format.", "Low", "Open"),
    ("API", "Unauthorized request succeeds", "Protected endpoint responds without authentication.", "Critical", "Open"),
    ("API", "Duplicate issue key allowed", "API permits duplicate issue identifiers.", "High", "Open"),
    ("API", "Empty description causes error", "Submitting an empty description causes an exception.", "Medium", "Resolved"),
    ("API", "Invalid ID crashes endpoint", "Requesting a nonnumeric ID causes an error.", "Medium", "Open"),
    ("API", "API pagination ignores limit", "API returns more records than the requested limit.", "Low", "In Progress"),
    ("API", "API error details missing", "Failed requests do not return a useful error message.", "Low", "Open"),

    ("Database", "Bug report not saved", "Submitted bug report is missing from the database.", "Critical", "Open"),
    ("Database", "Status update not persisted", "Updated status is not saved after refreshing.", "High", "Open"),
    ("Database", "Database connection failure", "Application cannot connect to PostgreSQL.", "Critical", "In Progress"),
    ("Database", "CSV export has duplicate rows", "Exported CSV contains repeated records.", "Medium", "Open"),
    ("Database", "Developer assignment missing", "Assigned developer is not stored correctly.", "High", "Open"),
    ("Database", "Null project causes error", "Reports without a project trigger an exception.", "Medium", "Resolved"),
    ("Database", "Timestamp displayed incorrectly", "Report creation time uses the wrong timezone.", "Low", "Open"),
    ("Database", "Transaction rollback fails", "Partial changes remain after a failed operation.", "Critical", "Open"),
    ("Database", "Report count is incorrect", "Dashboard count differs from the database count.", "Medium", "In Progress"),
    ("Database", "Long description truncated", "Long bug descriptions are not fully saved.", "Medium", "Open"),
]

conn = None
cur = None

try:
    conn = get_connection()
    cur = conn.cursor()

    cur.executemany(
        """
        INSERT INTO public.bug_reports
            (project, title, description, severity, status)
        VALUES (%s, %s, %s, %s, %s)
        """,
        bugs
    )

    conn.commit()
    print(f"Success! Inserted {len(bugs)} demo bug reports.")

except Exception as e:
    if conn:
        conn.rollback()
    print("Error inserting demo bugs:", e)

finally:
    if cur:
        cur.close()
    if conn:
        conn.close()

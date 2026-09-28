3. Parse a security log line
Given log lines like:
log = "event=4625 user=administrator src=10.0.0.8 status=failed"
Write:
def parse_login(log):
Return a string formatted like:
administrator@10.0.0.8
but only if:
- event is 4625
- status is failed
Otherwise return:
None
You should parse the fields from the string rather than relying on fixed character positions.
Test against:
"event=4625 user=administrator src=10.0.0.8 status=failed"

"event=4624 user=will src=10.0.0.5 status=success"
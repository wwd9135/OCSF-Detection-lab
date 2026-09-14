log = "event=4625 user=administrator src=10.0.0.8 status=failed"
log = log.strip().lower()
los = log.split(" ")
for i in los:
    key, value = i.split("=")
    print(key,value)
log = "event=4625 user=administrator src=10.0.0.8 status=failed"
def parse_login(log):
    log = log.strip().lower()

    key, valuew = log.split("=")
    print(valuew)
parse_login(log)


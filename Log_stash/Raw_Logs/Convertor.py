# Goal- Take sysmonRaw and clean up file.
# If text == Aug 25 19:09:56 siem01 logstash[37767]: remove completely and continue to next line
new = []
with open("Sysmonraw3.txt", "r") as file:
    lines = file.readlines()
for i in lines:
    i = i.replace("Aug 29 12:20:27 siem01 logstash[3213]:", "")
    new.append(i)

for i in new:
    print(i)

with open("sysmonCleaned3.txt", "w") as file:
    for i in new:
        file.write(i)
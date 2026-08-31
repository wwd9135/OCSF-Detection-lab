# Goal- Take sysmonRaw and clean up file.
# If text == Aug 25 19:09:56 siem01 logstash[37767]: remove completely and continue to next line
new = []
with open("RawData.txt", "r") as file:
    lines = file.readlines()
for i in lines:
    i = i.replace("Aug 30 13:00:48 siem01 logstash[6879]:", "")
    new.append(i)

for i in new:
    print(i)

with open("WinEventClean.txt", "w") as file:
    for i in new:
        file.write(i)
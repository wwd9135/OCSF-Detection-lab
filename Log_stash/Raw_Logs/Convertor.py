# Goal- Take sysmonRaw and clean up file.
# If text == Aug 25 19:09:56 siem01 logstash[37767]: remove completely and continue to next line
new = []
with open("SysmonRawOutput.txt", "r") as file:
    lines = file.readlines()
for i in lines:
    i = i.replace("Aug 28 09:21:19 siem01 logstash[4375]:", "")
    new.append(i)

for i in new:
    print(i)

with open("sysmonCleaned2.txt", "w") as file:
    for i in new:
        file.write(i)
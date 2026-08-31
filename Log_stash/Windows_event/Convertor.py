# Goal- Take sysmonRaw and clean up file.
# If text == Aug 25 19:09:56 siem01 logstash[37767]: remove completely and continue to next line
new = []
with open("4624.txt", "r") as file:
    lines = file.readlines()
for i in lines:
    i = i.replace("Aug 31 13:10:18 siem01 logstash[5568]:", "")
    new.append(i)

for i in new:
    print(i)

with open("4624clean.txt", "w") as file:
    for i in new:
        file.write(i)
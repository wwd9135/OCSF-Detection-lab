# Goal- Take sysmonRaw and clean up file.
# If text == Aug 25 19:09:56 siem01 logstash[37767]: remove completely and continue to next line
new = []
with open("4678_9raw.txt", "r") as file:
    lines = file.readlines()
for i in lines:
    i = i.replace("Sep 03 13:19:38 siem01 logstash[12021]:", "")
    new.append(i)

for i in new:
    print(i)

with open("468_9clean.txt", "w") as file:
    for i in new:
        file.write(i)
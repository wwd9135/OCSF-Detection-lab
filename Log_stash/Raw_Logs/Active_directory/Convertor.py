# Goal- Take sysmonRaw and clean up file.
# If text == Aug 25 19:09:56 siem01 logstash[37767]: remove completely and continue to next line
new = []
with open("1.txt", "r") as file:
    lines = file.readlines()
for i in lines:
    i = i.replace("Sep 09 12:39:39 siem01 logstash[3549]:", "")
    new.append(i)

for i in new:
    print(i)

with open("5136.txt", "w") as file:
    for i in new:
        file.write(i)
# Goal- Take sysmonRaw and clean up file.
# If text == Aug 25 19:09:56 siem01 logstash[37767]: remove completely and continue to next line
new = []
with open("4771(1).txt", "r") as file:
    lines = file.readlines()
for i in lines:
    i = i.replace("Sep 08 13:09:27 siem01 logstash[30528]:", "")
    new.append(i)

for i in new:
    print(i)

with open("4771(clean).txt", "w") as file:
    for i in new:
        file.write(i)
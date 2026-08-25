# Overview of OCSF lab
**REPO overview**

Infrastructure design/ VM layout is explained in Lab_build/Infrastructure-inventory.md


Standard telemetry before normalisation is explained in Lab_build/telemetry-inventory.md
**Architecture design**
```text
└── Hypervisor
    ├── DC01      Windows Server / AD DS / DNS
    ├── CA01      Windows Server / ADCS
    ├── WinUser   Windows 11 user/ Sysmon
    ├── UBU01     Linux target / auditd / SSSD
    └── SIEM01    Logstash / OpenSearch / Dashboards

Spare physical laptop with core OS changed to Kali linux or ubuntu
└── Kali Linux
    ├── Certipy
    ├── Impacket
    ├── BloodHound tools
    ├── Nmap
    └── other attack tooling

###################################################################################################################
####################   Forwarding / normalisation of logs   #######################################################
###################################################################################################################

                         ENDPOINTS
               ┌───────────┼────────────┐
               │           │            │
            Sysmon       auditd       SSSD/CA/etc
               │           │            │
               └───── collectors ───────┘
                           │
                           ▼
                        LOGSTASH
                           │
                  ┌────────┴────────┐
                  │                 │
                Parse           Preserve raw logs
                  │
                Enrich
                  │
                Normalize
                  │
              OCSF mapping
                  │
                  ▼
               OPENSEARCH
                  │
                indexes
                  │
                  ▼
               DASHBOARDS
                  │
                  ▼
               DETECTIONS
```

## Lab explanation
This lab was designed from scratch, I used Vmware workstation pro with a local NAT group. Then stood up 5 VMs total, windows server, linux server, windows / linux endpoints. I Stood up a DC, enabled AD-DS to create a functioning active directory & domain server, then I created a certificate authority server, to generate CA/ PKI related traffic down the line, and to grant certificates to the relevant devices within the network. 


I then stood up a OpenSearch / dashboards SIEM on my SIEM-01 linux server, used docker to configure it and docker compose to automate the setup of the SIEM allowing the SIEM to function as expected without ongoing maintanance, freezing the version number of OpenSearch deliberately so I wont need to reconfgiure if it auto updated itself.
From here the OpenSearch SIEM dashboard was reachable via HTTPS, the docker container hosting OpenSearch-Dashboards on SIEM01 was acting as a webserver now. I can reach the SIEM via my personal laptop or the windows user VM within the local NAT.

To actually work with the traffic created I am using LogStash, this was the main learning curve of this project, I collected telemetry from the 5 endpoints, used syslog CEF / syslog event forwarder to upload telemetry from each endpoint in real time. This telemetry was parsed by LogStash 

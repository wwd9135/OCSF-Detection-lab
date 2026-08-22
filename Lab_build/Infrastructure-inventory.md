# Overview of lab infrastructure
The lab will be split into two clean sections for attack & defence, I've deliberately used an old laptop with Kali and a windows 11 hypervisor laptop for defence so I can launch attacks and watch them unfold on the device and within the SIEM simuntaneously. 

## Architecture
Main Windows 11 laptop
└── Hypervisor
    ├── DC01      Windows Server / AD DS / DNS
    ├── CA01      Windows Server / ADCS
    ├── UBU01     Linux target / auditd / SSSD
    └── SIEM01    Logstash / OpenSearch / Dashboards

Spare physical laptop with core OS changed to Kali linux or ubuntu
└── Kali Linux
    ├── Certipy
    ├── Impacket
    ├── BloodHound tools
    ├── Nmap
    └── other attack tooling

The wider architecture linked together

                         DC01
                Active Directory + DNS
                Identity / Kerberos
                  /       |       \
                 /        |        \
                /         |         \
       WinUser01         UBU01       CA01
       Windows user      Linux       AD CS
          |               |           |
       processes       SSH/exec     certificates
       logons          SSSD/auth    enrollment
          \               |           /
           \              |          /
            \             |         /
             -----------------------
                       |
                       v
                     SIEM01
                 central telemetry
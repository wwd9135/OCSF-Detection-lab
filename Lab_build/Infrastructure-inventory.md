# Overview of lab infrastructure
The lab will be split into two clean sections for attack & defence, I've deliberately used an old laptop with Kali and a windows 11 hypervisor laptop for defence so I can launch attacks and watch them unfold on the device and within the SIEM simuntaneously. 

## Architecture
```text
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
```
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


## SIEM backround info
Logstash will be used to collect the data from the sources named in <GPT insert link to telemetry.md>
<will fill in more data about logstash when ive done the work on it>

Logstash will parse into OCSF and pass into OpenSearch <include more details when they arrive>

OpenSearch is being used at the ingestion layer, it will take data and efficiently transport it to OpenSearch-Dashboards the SIEM UI interface. I am deploying via docker compose to allow for a configuration to persist through VM reboots and require no manual effort.

OpenSearch data will be stored using a persistent Docker volume rather than solely within the OpenSearch container filesystem. This separates application lifecycle from telemetry storage, allowing containers to be recreated or upgraded without intentionally deleting indexed security data.
Open search-dashboards will then be utilized, SIEM01 will serve as a webserver allowing my Win user VM and my hypervisor itself to access the dashboards I create using standard TCP/HTTPS connections.




### OpenSearch SIEM
The SIEM stack is hosted on SIEM01 and containerised using Docker to simplify deployment, maintenance, upgrades, and recovery. OpenSearch and OpenSearch Dashboards are deployed from Docker images, with Docker Compose used to define and orchestrate the complete stack from a single YAML configuration file.


**The deployment consists of:**
| Component | Purpose |
|---|---|
| **OpenSearch** | Stores and indexes security telemetry and provides the backend search/analytics engine. |
| **OpenSearch Dashboards** | Web interface used to search, investigate, and visualise indexed telemetry. |
| **Docker Engine** | Runs the OpenSearch components as isolated containers on `SIEM01`. |
| **Docker Compose** | Defines container configuration, networking, ports, environment variables, volumes, and service dependencies. |
| **Docker network** | Provides internal communication between OpenSearch and OpenSearch Dashboards. |
| **Persistent volume** | Stores OpenSearch indexes outside the lifecycle of the container so telemetry is retained if the container is recreated. |

**The deployment lifecycle is:**

```text
docker compose up -d
        ↓
Create Docker network
        ↓
Create/start OpenSearch container
        ↓
Attach persistent OpenSearch data volume
        ↓
Create/start OpenSearch Dashboards container
        ↓
Connect Dashboards to OpenSearch
        ↓
Publish required ports on SIEM01
        ↓
Dashboards accessible remotely through browser
```
### Interface / port data
```text
SIEM01: 10.0.0.30

OpenSearch API:
TCP 9200

OpenSearch Dashboards:
TCP 5601

Administrative access:
SSH TCP 22
```

**Docker compose file**
```yaml
services:
  opensearch:
    image: opensearchproject/opensearch:latest
    container_name: opensearch
    environment:
      - discovery.type=single-node
      - bootstrap.memory_lock=true
      - OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
    ulimits:
      memlock:
        soft: -1
        hard: -1
    volumes:
      - opensearch-data:/usr/share/opensearch/data
    ports:
      - "9200:9200"
    networks:
      - opensearch-net

  dashboards:
    image: opensearchproject/opensearch-dashboards:latest
    container_name: opensearch-dashboards
    ports:
      - "5601:5601"
    environment:
      - OPENSEARCH_HOSTS=["https://opensearch:9200"]
    depends_on:
      - opensearch
    networks:
      - opensearch-net

volumes:
  opensearch-data:

networks:
  opensearch-net:
```
### LogStash
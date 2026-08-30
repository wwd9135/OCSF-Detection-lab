# Overview of lab infrastructure
The lab will be split into two clean sections for attack & defence, I've deliberately used an old laptop with Kali and a windows 11 hypervisor laptop for defence so I can launch attacks and watch them unfold on the device and within the SIEM simuntaneously. 

## Architecture
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

### OpenSearch Dashboard configuration
It's important to change the default username from admin upon first logon

And to create SIEM RBAC roles, such as- SIEM-ADMIN, read only viewer etc. So you're not running everything on a global admin account that can accidently delete the entire pipeline.

OpenSearch dashboards will automatically ingest data from OpenSearch when its received, if the configuration is correct. To achieve this, OpenSearch must be configure correctly with the following plugin installed:
```code
# First check:
sudo -u logstash /usr/share/logstash/bin/logstash-plugin list | grep opensearch

# If not installed, use:
sudo /usr/share/logstash/bin/logstash-plugin install logstash-output-opensearch
```
Move on to LogStash configuration from here as OpenSearch is ready to receive.

## LogStash configuration
LogStash is a core part of the traditional ELK stack, handling forwarding & efficient parsing/ filtering on raw data before it hits a custom SIEM, this is useful when your SIEM doesnt have built in indexing / parsing for raw traffic.

**Configuration guide- Linux server**
```code
# Install Logstash, then make sure it runs as the logstash service user rather than root.
wget -qO - https://artifacts.elastic.co/GPG-KEY-elasticsearch \
  | sudo gpg --dearmor -o /usr/share/keyrings/elastic-keyring.gpg
sudo apt-get install apt-transport-https
echo "deb [signed-by=/usr/share/keyrings/elastic-keyring.gpg] https://artifacts.elastic.co/packages/9.x/apt stable main" \
  | sudo tee /etc/apt/sources.list.d/elastic-9.x.list
sudo apt-get update
sudo apt-get install logstash
# Then start it:
sudo systemctl start logstash
# Enable at boot:
sudo systemctl enable logstash
# Check:
sudo systemctl status logstash
```

**Useful linux paths:**
```code
/usr/share/logstash/bin/logstash
/etc/logstash/logstash.yml
/etc/logstash/conf.d/
# Install the OpenSearch output plugin:
sudo /usr/share/logstash/bin/logstash-plugin install logstash-output-opensearch
Check it installed:
sudo -u logstash /usr/share/logstash/bin/logstash-plugin list | grep opensearch
Your input plugin for Winlogbeat is the Beats input, typically listening on:
TCP 5044
Minimal pipeline shape:
input {
  beats {
    port => 5044
  }
}

output {
  opensearch {
    hosts => ["https://localhost:9200"]
    user => "logstash"
    password => "PASSWORD"
    index => "ocsf-process-%{+YYYY.MM.dd}"
    ssl_certificate_verification => false
  }
}
Validate the config before restarting:
sudo -u logstash /usr/share/logstash/bin/logstash \
  --path.settings /etc/logstash \
  --config.test_and_exit \
  -f /etc/logstash/conf.d/your-config.conf
Restart Logstash:
sudo systemctl restart logstash
Check status:
sudo systemctl status logstash
Follow logs:
sudo journalctl -u logstash -f
```

### LogStash filtering config
To put it simply log stash config has three sections:

1. Input  - Name input sources and ports to listen on for traffic uploading.
2. Filter - Using ruby & basic filtering to add, remove, rename fields in the raw traffic.
3. Output - 

**Input example:**
```json
input {
  beats {
    port => 5044
  }
}
```
This example shows using winbeats forwarder via port 5044 to receive the raw traffic.

**Filter example**
This is where it gets more complicated, the goal when manually mapping to a set schema, OCSF in my instance, is to do multiple rounds of careful tuning, start by keeping raw telemetry logs to refer back to, then working through the raw data and creating a mapping table from raw- OCSF. And removing uneccessary fields, I'd recommend keeping a raw_data field, so analysts can use the full raw data if its needed. 

The following path shows a complete example.
Log_stash\Sysmon_mapping\conf.yml


**Output example:**
```json
output {
  stdout {
    codec => rubydebug
  }

  opensearch {
    hosts => ["https://localhost:9200"]

    user => "logstash"
    password => "YOUR_PASSWORD"

    index => "ocsf-process-%{+YYYY.MM.dd}"

    ssl_certificate_verification => false
  }
}
```
When debugging/ testing parsing it's recommended to just use the stdout rubydebug section.
Once you're filtering logic is perfectted adding the openSearch clause is needed to ingest the data into the SIEM and do further testing.
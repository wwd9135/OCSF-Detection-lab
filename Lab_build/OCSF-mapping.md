# Overview
Throughout this project I will be manually mapping all required telemetry sources and normalising them to OCSF schema.


All against **OCSF 4.5.0**.

I mapped carefully, removing uncessary fields, testing each iteration & ensuring no data or value was lost throughout this process. After each source was successfully mapped I tested the new output contents against the original raw contents to ensure there wasn't any lost information.

**Process Activity (1007)** ← Sysmon EID 1 / Linux execve

| OCSF field | Source |
| --- | --- |
| `class_uid` | `1007` (constant) |
| `activity_id` | `1` (Launch) |
| `process.pid` / `process.name` / `process.cmd_line` | Sysmon ProcessId/Image/CommandLine · execve args |
| `actor.process.file.path` | Sysmon ParentImage · auditd exe |
| `actor.user.name` | Sysmon User · auditd `auid`/`uid` |
| `device.hostname` | Beat host field |

**File System Activity (1001)** ← Sysmon EID 11 / auditd PATH

| OCSF field | Source |
| --- | --- |
| `class_uid` | `1001` |
| `activity_id` | `1` Create / `3` Update / `4` Delete (map from the auditd op) |
| `file.path` | Sysmon TargetFilename · auditd `name` |
| `actor.process` / `actor.user` | as above |

**Authentication (3002)** ← 4624 / 4768 / sshd

| OCSF field | Source |
| --- | --- |
| `class_uid` | `3002` |
| `activity_id` | `1` (Logon) |
| `user.name` | 4624 TargetUserName · 4768 Account Name · sshd user |
| `auth_protocol_id` | Kerberos / NTLM / other |
| `cert` (serial/issuer/thumbprint) | **4768 PKINIT Certificate Information — carry these; A1 needs them** |
| `status_id` | Success/Failure |

**Entity Management (3004)** ← 5136 directory-object change

| OCSF field | Source |
| --- | --- |
| `class_uid` | `3004` |
| `activity_id` | Create / Update / Delete per the 5136 operation |
| `entity.name` / `entity.type` | the modified object (`pKICertificateTemplate`) |
| `actor.user.name` | 5136 Subject Account |
| the changed attribute + old/new value | 5136 LDAP Display Name / Value |

**Certificate issuance (4886/4887)** — **no stock class.** I had to create my own mapping for this. 

## Sysmon EID 1
Evidence is stored in Raw_Logs and Sysmon_mapping folders. (GPT to add exact links)
I recorded several versions of the raw data and my config files to show progression.

Sysmon was the first source to be mapped, and would serve as the foundational point to map auditd & Windows events, since I was collecting process execution telemetry from those two sources too, I could use my sysmon normalisation work to compare to auditd (linux) and winevents and see how they differ and where they align. 
This also meant I could combine WinEvent with sysmon to potentially merge information and increase the overall hollistcness of a single log, IE. sysmon and winevents are raised simuntaneously for each process execution, so I can merge alerts to increase the strength and quality.

I completed my sysmon mapping and removed a bulk of the original telemetry fields using the remove command/filter:
mutate {
      remove_field => [
        "winlog",
        "host",
        "event",
        "agent",
        "ecs",
        "log",
        "tags",
        "message",
        "@version",
      ]
    }
Now the telemetry was normalized with all of the original sysmon fields removed, leaving OCSF offical fields remaining only.

From here I engineered a output path now which still allowed for proper testing while I proved OpenSeach / dashboards we working and not losing any telemetry, 
This is an example of the structure to be used. Keeping rubydebug allows for full logging to troubleshoot any hiccups in the indexing/ ingestion process.
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

## Windows event mappings
Event ID:


## Linux Auditd mappings.
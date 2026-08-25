# Overview of OCSF lab
Infrastructure design/ VM layout is explained in Lab_build/Infrastructure-inventory.md
Standard telemetry before normalisation is explained in Lab_build/telemetry-inventory.md
**Architecture design**
```text
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
                Parse           Preserve raw
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

## Layout explained
**Data collection**
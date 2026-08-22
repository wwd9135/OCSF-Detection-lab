
sudo nano /etc/audit/rules.d/lab.rules
## 64-bit process execution
-a always,exit -F arch=b64 -S execve -k process_exec

## 32-bit process execution
-a always,exit -F arch=b32 -S execve -k process_exec

## Identity/authentication-related files
-w /etc/passwd -p wa -k identity
-w /etc/group -p wa -k identity
-w /etc/shadow -p wa -k identity
-w /etc/sudoers -p wa -k privilege_config

## SSH configuration
-w /etc/ssh/sshd_config -p wa -k ssh_config

# OCSF Detection Lab — Build Guide


## Table of contents

1. [The one-paragraph version](#the-one-paragraph-version)
2. [Environment assumptions and naming](#environment-assumptions-and-naming)
3. [Concept primers (read once)](#concept-primers-read-once)
   - [PKI, CAs and certificate templates](#-concept-pki-cas-and-certificate-templates)
   - [What ESC1 and ESC4 actually are](#-concept-what-esc1-and-esc4-actually-are)
   - [OCSF in plain English](#-concept-ocsf-in-plain-english)
   - [Logstash and OpenSearch](#-concept-logstash-and-opensearch)
   - [auditd](#-concept-auditd)
4. [Week 1 — Lab + telemetry (front-load the risk)](#week-1--lab--telemetry-front-load-the-risk)
5. [Week 2 — Pipeline + schema validation](#week-2--pipeline--schema-validation)
6. [Week 3 — Attacks + fixtures](#week-3--attacks--fixtures)
7. [Week 4 — Detection engine + CI](#week-4--detection-engine--ci)
8. [Week 5 — Writeups + buffer](#week-5--writeups--buffer)
9. [Appendix A — The A1 (ESC1) correlation, at the event level](#appendix-a--the-a1-esc1-correlation-at-the-event-level)
10. [Appendix B — OCSF mapping cheat-sheet](#appendix-b--ocsf-mapping-cheat-sheet)
11. [Appendix C — Event ID / record-type cheat-sheet](#appendix-c--event-id--record-type-cheat-sheet)
12. [Appendix D — The ESC1 vulnerable-template recipe](#appendix-d--the-esc1-vulnerable-template-recipe)
13. [Deliverables checklist](#deliverables-checklist)

---

## The one-paragraph version

You are building a detection pipeline you own end to end: raw telemetry from Windows/ADCS/Linux →
normalised to **OCSF** by **Logstash** → schema-validated in **CI** → stored in **OpenSearch** →
evaluated by a **detection engine you wrote**. Four detections (two Linux persistence, two ADCS
certificate attacks) each demonstrate a *different shape* of detection. The portfolio value is not
the four rules — it's (a) the schema-validation CI gate, (b) the honest writeup of where OCSF
**doesn't** fit certificate telemetry, and (c) the stateful ESC1 correlation. Spend your surplus
hours there, not on adding a fifth rule.

**Sequencing principle for the whole project:** do the *unfamiliar, risky* thing first each week,
while you still have slack to recover. Your safe, known-good work (Linux atomics, the CI port) is
the thing you finish *with*, not the thing you start with.

---

## Environment assumptions and naming

Main Windows 11 laptop
└── Hypervisor
    ├── DC01      Windows Server / AD DS / DNS
    ├── CA01      Windows Server / ADCS
    ├── UBU01     Linux target / auditd / SSSD
    └── SIEM01    Logstash / OpenSearch / Dashboards

Spare physical laptop
└── Kali Linux
    ├── Certipy
    ├── Impacket
    ├── BloodHound tools
    ├── Nmap
    └── other attack tooling

**Snapshot every VM before each attack run.** You will re-run these many times; a clean baseline
is the difference between a two-hour fixture capture and a two-day one.

---

## Concept primers (read once)

### 🧠 CONCEPT: PKI, CAs and certificate templates

You already understand authentication in AD (Kerberos, NTLM, passwords). **PKI (Public Key
Infrastructure)** is a second, parallel way to prove identity — using **certificates** instead of
passwords. A certificate is a signed file that says "the holder of this private key is
*such-and-such principal*," signed by an authority everyone trusts.

- **CA (Certificate Authority):** the trusted signer. An **Enterprise CA** is domain-joined and
  publishes its templates into AD, so any domain machine can request certs. (There's also a
  *Standalone* CA — ignore it, it doesn't use AD templates and the entire attack surface here
  depends on AD-integrated templates.)
- **Certificate template:** a reusable blueprint that says *what kind* of cert this is, *who* is
  allowed to request one, and *how the subject/identity is decided*. Templates live as objects in
  AD's Configuration partition. This is the crucial bit: **a template is just an AD object with an
  ACL**, which is why certificate misconfigurations are really AD misconfigurations — familiar
  ground for you.
- **EKU (Extended Key Usage):** what the cert is *allowed to be used for*. "Client Authentication"
  EKU means the cert can be used to log in as its subject. That's the EKU that makes a template
  dangerous.
- **SAN (Subject Alternative Name):** an optional field in a cert request that says "this cert also
  represents *this other identity*." Normally the CA decides your subject from your AD account. But
  if a template is configured to let *you* supply the subject/SAN, you can ask for a cert that
  claims to be someone else. Hold that thought — it's the whole of ESC1.

The mental model: **a certificate template is a policy object; abusing certificates is abusing a
policy object's configuration and ACL.** You are not learning cryptography here, you're learning a
new class of AD misconfiguration.

### 🧠 CONCEPT: What ESC1 and ESC4 actually are

"ESC" = **E**scalation via **S**ervices **C**ertificate, from the SpecterOps "Certified Pre-Owned"
research. There are ~15 numbered ESCs; you're doing two, chosen because they're *different shapes*
of detection.

**ESC1 — the enrolment-time abuse.** A template is vulnerable when *all* of these are true at once:

1. A low-privileged group (e.g. Domain Users) has **Enroll** rights, **and**
2. the template lets the **enrollee supply the subject** (`CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT`), **and**
3. the template has an authentication EKU (Client Authentication / Smart Card Logon / Any Purpose), **and**
4. manager approval and authorised signatures are **not** required.

Attack: low-priv user `bob` requests a cert from this template but supplies a SAN of
`administrator@lab.local`. The CA happily issues a cert that says "the holder is administrator."
`bob` then uses that cert to authenticate — and is now administrator. This is *execution-time*
abuse: nothing about the template changed, the attacker just used it as designed-but-misconfigured.

**ESC4 — the config-change abuse.** Here the template *isn't* vulnerable yet, but its **ACL** is weak
— a low-priv user has write access to the template object. The attacker **rewrites the template** to
make it ESC1-vulnerable (grants themselves enrol rights, flips on enrollee-supplies-subject),
exploits it, then optionally reverts. This is *config-change* abuse: the signal is the **modification
of an AD object**, not an authentication.

Why these two: ESC1 teaches **stateful correlation** (you must join issuance to authentication —
see Appendix A). ESC4 teaches **directory-change auditing** (event 5136 on a template object). One
schema, two genuinely different detection logics. That contrast is your blog post #2 and #1.

### 🧠 CONCEPT: OCSF in plain English

**OCSF (Open Cybersecurity Schema Framework)** is a vendor-neutral way to describe security events.
Instead of "Sysmon event 1" and "auditd execve" and "Linux sshd" all having different field names
for the same idea (a process started, a user logged in), OCSF gives you **one shape** per *kind of
activity*, with the same field names regardless of source.
.
The pieces you'll touch:

- **Category** — a broad domain. You'll use *System Activity* (id 1) and *IAM* (id 3).
- **Event Class** — a specific activity within a category, each with a stable numeric id. Your four:

  | Class | ID | You feed it from |
  | --- | --- | --- |
  | File System Activity | 1001 | Sysmon 11, auditd PATH |
  | Process Activity | 1007 | Sysmon 1, Linux execve |
  | Authentication | 3002 | 4624 / 4768, sshd |
  | Entity Management | 3004 | 5136 directory changes |

- **Attributes** — the fields on a class. Some are shared "Base Event" fields (`time`, `severity`,
  `metadata`, `class_uid`), some are class-specific (`process`, `actor`, `file`, `user`).
- **`activity_id` / `type_uid`** — enums that say *which* variant of the activity happened
  (e.g. Process Activity `activity_id: 1` = "Launch"). Getting these right is most of "mapping."

> **The current version is OCSF 4.5.0** (schema.ocsf.io). The original plan was written against an
> older release; the four class IDs above are still valid in 4.5.0, but **pull the live JSON schema
> for 4.5.0** when you build validation — don't trust a cached copy.

**The ADCS problem you'll hit in Week 2 (and it's the good part):** OCSF has **no clean class for
"a certificate was issued."** Authentication (3002) is about *using* a credential, not *minting*
one. As of late 2025 the OCSF maintainers themselves have an **open issue** debating how certificate
validation/issuance should fit — search the `ocsf/ocsf-schema` repo for issue **#1513** ("Need for a
certificate validation activity_id … or a separate class"). That means your headline finding —
"the standard schema doesn't cleanly model certificate issuance, here's how I reasoned about it" —
is not you being confused, it's you landing on a live, unresolved gap in the standard. Cite the
issue in your writeup. That single move is what makes the post read as senior rather than
tutorial-follower.

### 🧠 CONCEPT: Logstash and OpenSearch

You've lived in Sentinel/KQL. This is the open-source analogue, and the concepts map 1:1:

- **Logstash** = the ingestion/normalisation engine. A **pipeline** has three stages: **input**
  (read from Beats/files), **filter** (parse and reshape — this is where you *become* OCSF), and
  **output** (send to OpenSearch). The filter stage is where you'll spend your Week 2 hours.
  - **grok** = regex-with-names for pulling fields out of unstructured log lines. Familiar pain.
  - **`logstash-filter-ruby`** = an escape hatch: when grok gets ugly, write a few lines of Ruby to
    reshape the event instead. Readability beats cleverness — reach for ruby when a grok pattern
    starts looking like line noise.
- **Beats** = lightweight shippers on the endpoints. **Winlogbeat** ships Windows event logs;
  **Filebeat** ships files/auditd. They're the equivalent of the Sentinel/Defender agents.
- **OpenSearch** = the store + query engine (a fork of Elasticsearch). It's your "Sentinel
  workspace." You query it with its own DSL (JSON) rather than KQL, but the ideas — indices,
  documents, fields, time filters — are the same. **OpenSearch Dashboards** is the Kibana-style UI.

Data flow, concretely: `Winlogbeat/Filebeat → Logstash (input → OCSF filter → output) → OpenSearch
index`. Your detection engine later queries OpenSearch and writes hits to an `alerts` index.

### 🧠 CONCEPT: auditd

`auditd` is the Linux kernel audit daemon — the closest thing Linux has to Sysmon for
syscalls/file-access. You care about two rule shapes:

- **File watches** (`-w /path -p wa -k key`): "tell me on write/attribute-change to this path,
  tagged with key `key`." This is how you catch cron and shell-config tampering (L1/L2).
- **Syscall rules** (`-a always,exit -F arch=b64 -S execve -k exec`): "log every execve," giving you
  process-execution context to map into OCSF Process Activity.

Events land in `/var/log/audit/audit.log` as multiple lines per event (a `SYSCALL` line plus `PATH`,
`CWD`, `EXECVE` lines). Filebeat's auditd module (or reading the file) ships them; Logstash
reassembles and maps them. **Blind spot to write down now:** `-w` watches on per-user dotfiles
(`~/.bashrc`) are awkward — you either enumerate every home directory or accept you're only watching
`/etc` and `root`. That limitation is exactly the kind of thing your `telemetry-inventory.md` should
call out.

---

## Week 1 — Lab + telemetry (front-load the risk)

**Goal of the week:** every VM built and audited, and — the non-negotiable — **prove ESC1 fires
end-to-end in raw telemetry before any pipeline exists.** If CA auditing is going to fight you, you
want to find out on day 2 with 190 hours left, not day 24 with 6.

**Order matters. Do the unfamiliar CA/auditing work first, the familiar AD/Linux work second.**

### Day 1–2: CA stand-up and *win the auditing battle in isolation*

Do this **before** you build any vulnerable template. Prove you can see a *normal* enrolment in the
logs first, so that later you're only ever debugging one variable at a time.

⚡ **DO — install an Enterprise CA on CA01** (domain-joined member server):

```powershell
Install-WindowsFeature ADCS-Cert-Authority -IncludeManagementTools
Install-AdcsCertificationAuthority -CAType EnterpriseRootCA -CACommonName "lab-CA01-CA" -Force
```

> ⚠️ **GOTCHA — Enterprise, not Standalone.** If the wizard/PowerShell gives you a Standalone CA,
> stop and redo it. Standalone CAs don't use AD-published templates and the entire ESC1/ESC4 surface
> won't exist. `-CAType EnterpriseRootCA` is correct for a single-tier lab.

⚡ **DO — turn on CA auditing. This is a two-part switch and both parts are required:**

```powershell
# Part 1: tell the CA which event categories to audit (127 = all 7 categories)
certutil -setreg CA\AuditFilter 127
net stop certsvc && net start certsvc

# Part 2: turn on the OS audit subcategory that actually emits the events
auditpol /set /subcategory:"Certification Services" /success:enable /failure:enable
```

> ⚠️ **GOTCHA — the telemetry does not exist until you turn it on, and it takes *both* steps.**
> `AuditFilter` alone gets you nothing; the `auditpol` subcategory alone gets you nothing. This is
> the single most common "I wasted a day" moment in ADCS detection work. Do both, then **verify
> before moving on** (next step). Write this up — "the telemetry doesn't exist until you enable it,
> and enabling it is two independent switches" is a genuinely good blog paragraph.

⚡ **DO — generate one normal enrolment and confirm the events land.** From any domain machine,
request a plain user cert (`certlm.msc` / `certreq`, or just `gpupdate` with autoenrolment). Then on
CA01:

```powershell
Get-WinEvent -LogName Security -FilterXPath "*[System[(EventID=4886 or EventID=4887)]]" -MaxEvents 10 |
  Format-List TimeCreated, Id, Message
```

You want **4886** (request received) and **4887** (request approved / cert issued). If you see them,
the auditing battle is won and you can trust every later capture. If you don't, you're debugging
*only* auditing right now — not auditing *and* an attack. That isolation is the whole point of doing
this first.

⚡ **DO — enable directory-change auditing for ESC4 (event 5136) now, while you're in the audit
mindset.** 5136 has its own two-part gotcha:

```powershell
auditpol /set /subcategory:"Directory Service Changes" /success:enable /failure:enable
```

> ⚠️ **GOTCHA — 5136 also needs a SACL on the object, or it stays silent.** The audit subcategory
> is necessary but not sufficient: the AD object being changed must have a **System ACL (auditing
> entry)** telling AD to log modifications. Add a SACL to the certificate-templates container via
> ADSI Edit → Configuration partition →
> `CN=Certificate Templates,CN=Public Key Services,CN=Services,CN=Configuration,DC=lab,DC=local`
> → Properties → Security → Advanced → **Auditing** → add principal `Everyone`, Type `Success`,
> Applies to "This object and all descendant objects," permission "Write all properties." Without
> this SACL, ESC4 will happen and **no 5136 will appear** — another day-loser if you skip it.

### Day 3: the deliberately vulnerable ESC1 template

Only now — auditing proven — introduce the vulnerability. See [Appendix D](#appendix-d--the-esc1-vulnerable-template-recipe)
for the exact click-path. **Record every setting you change as you change it**; that record is your
writeup evidence and your `telemetry-inventory.md` entry.

### Day 3–5: the familiar work (fast, because you own it)

- Promote `DC01`, build the domain, add users incl. low-priv `bob`.
- Join `ubu01` / to `local NAT` via **SSSD**. It's fiddly but you get realistic auth
  telemetry (4768/4769 on the DC, `sssd`/`sshd` on the box). Keep the `sssd.conf` you land on — it's
  a `telemetry-inventory.md` artefact.
- Windows auditing: Advanced Audit Policy for **process creation with command line**
  (`auditpol /set /subcategory:"Process Creation" /success:enable` **plus** the "Include command
  line in process creation events" policy), **directory service changes**, **certification
  services** (done above). Install **Sysmon** with the SwiftOnSecurity config as a base.
- Linux auditing: drop the L1/L2 rules and an execve rule into `/etc/audit/rules.d/lab.rules`
  (see [Appendix C](#appendix-c--event-id--record-type-cheat-sheet)) and `augenrules --load`.

⚡ **DO — the actual Week-1 deliverable: `telemetry-inventory.md`.** For every source: what event
IDs / record types it emits, what was **on by default vs what you enabled**, and known **blind
spots** (the `~/.bashrc` watch gap; whether 4887 carries the cert serial on your build — see
Appendix A; the SACL requirement for 5136). This document is worth more in an interview than any
single rule, because it proves you understand that *detection starts at telemetry availability, not
at rule-writing.*

---

## Week 2 — Pipeline + schema validation

**This is the week that separates you from rule-writers. Do not rush it.** It's also your hardest
*genuinely new* week (Logstash + OCSF depth + the ADCS mapping problem).

### Order of attack

1. **Stand up OpenSearch + Dashboards on `siem01`**, then Logstash. Get one boring source
   (say Sysmon 1 → Process Activity 1007) flowing all the way to an index *before* you touch OCSF
   subtlety. Prove the plumbing, then improve the mapping.
2. **Build one Logstash pipeline per source.** Structure each filter as: parse → rename to OCSF
   fields → set the class/activity enums → attach metadata. Use `logstash-filter-ruby` the moment a
   grok pattern stops being readable.
3. **Map to the four classes** using [Appendix B](#appendix-b--ocsf-mapping-cheat-sheet) as a
   starting point. Expect to iterate — the first mapping is always wrong in small ways the validator
   will catch.

### The schema-validation CI gate (the most transferable thing you'll build)

This mirrors your existing frozen-fixture CI pattern, but the gate is **schema conformance** instead
of (well, in addition to) rule behaviour.

⚡ **DO:**

- Pull the **OCSF 4.5.0 JSON schema** (from `schema.ocsf.io` / the `ocsf-schema` repo export).
- In `pytest`, load every normalised event your pipeline produces (freeze a sample set as fixtures)
  and validate each against its class schema with the `jsonschema` library.
- **Fail the build** on any non-conformant event. Wire it into GitHub Actions exactly like your
  existing six-stage gate — a merge that produces a non-OCSF-conformant event does not land.

```python
# tests/test_ocsf_conformance.py  (shape, not gospel)
import json, glob, pytest
from jsonschema import Draft202012Validator

# class_uid -> compiled validator, built from the 4.5.0 schema export
VALIDATORS = load_ocsf_validators("schema/ocsf-4.5.0/")

@pytest.mark.parametrize("path", glob.glob("fixtures/normalised/*.json"))
def test_event_is_ocsf_conformant(path):
    event = json.load(open(path))
    validator = VALIDATORS[event["class_uid"]]
    errors = sorted(validator.iter_errors(event), key=lambda e: e.path)
    assert not errors, f"{path}: " + "; ".join(e.message for e in errors)
```

### The ADCS mapping decision (your headline deliverable)

When you get to the certificate-issuance events (4886/4887), **OCSF will not have a clean home for
them.** You must make and *document* a choice. The two defensible options:

- **Option A — force it into an existing class** (Entity Management 3004, treating the cert as an
  entity being created; or stretch Authentication 3002). Cheap, but semantically lossy — write down
  exactly what you lose (issuance ≠ authentication; there's no natural field for "template used" or
  "SAN supplied").
- **Option B — define a documented OCSF *extension***: an `x_` custom object/attributes (or a small
  custom class) that models certificate issuance honestly. More work, but this is the senior move —
  and you can anchor it to the live gap in **OCSF issue #1513**.

Whichever you pick, the **writeup is the point**: state the requirement, show why the stock schema
doesn't meet it, show your extension/compromise, and reference the maintainers' own open discussion.
"Finding where a standard schema doesn't fit reality and reasoning about it in public" is a
senior-level output — far more interesting than four working rules.

> With your time surplus, actually do Option B properly. It's the highest-ceiling thing in the whole
> project and it rewards the extra hours more than anything else you could add.

---

## Week 3 — Attacks + fixtures

Generate each technique for real, then **freeze** the telemetry. For each: **snapshot → run attack →
export raw + normalised events → restore snapshot.** Frozen fixtures are what make your CI
deterministic.

### L1 / L2 — Linux persistence (fast; you know this)

Atomic Red Team has Linux atomics for both:

- **L1 — T1053.003 cron persistence:** run the cron atomics; confirm auditd fires your `cron_persist`
  key on `/etc/cron*` and `/var/spool/cron`.
- **L2 — T1546.004 shell config:** run the `.bashrc`/`.profile`/`/etc/profile.d` atomics; confirm
  your `shell_config` key fires.

### A1 — ESC1 (from `atk01` with Certipy)

> **Install Certipy:** `pipx install certipy-ad` (the maintained package name is `certipy-ad`; the
> command is `certipy`).

```bash
# 1. Enumerate — confirm the template shows as vulnerable to ESC1
certipy find -u bob@lab.local -p 'Passw0rd!' -dc-ip 10.0.0.10 -vulnerable -stdout

# 2. Request a cert as bob but supply administrator's identity in the SAN
certipy req -u bob@lab.local -p 'Passw0rd!' -ca 'lab-CA01-CA' \
  -template 'ESC1-Vuln' -upn administrator@lab.local -dc-ip 10.0.0.10

# 3. Authenticate with the issued cert — this is what produces the 4768 you'll correlate on
certipy auth -pfx administrator.pfx -dc-ip 10.0.0.10
```

Step 2 generates the **4886/4887** issuance events (requester = `bob`). Step 3 generates a **4768**
PKINIT logon (authenticated principal = `administrator`, carrying the cert serial). The join between
those two is your detection — see [Appendix A](#appendix-a--the-a1-esc1-correlation-at-the-event-level).

### A2 — ESC4 (config-change)

```bash
# Rewrite a template bob can write to, making it ESC1-vulnerable.
# certipy saves the original config and overwrites it — this modification is the 5136 signal.
certipy template -u bob@lab.local -p 'Passw0rd!' -template 'VulnACL-Template' -dc-ip 10.0.0.10
```

Confirm **5136** events appear on the `pKICertificateTemplate` object (only if you set the SACL in
Week 1). Then restore the template from the saved config.

### Capture benign near-misses too (this is the discipline people notice)

Your pipeline's strength has always been that it tunes against *near-misses*, not unrelated noise.
Keep that here. For each detection, capture a **legitimate** analogue and freeze it as a "must stay
silent" fixture:

- **L1:** a real cron edit by config management (Ansible/cron.d drop-in).
- **L2:** a genuine user editing their own `.bashrc`.
- **A1:** a **normal** certificate enrolment through a *properly-configured* template (same 4886/4887
  shape, but requester == subject, no SAN mismatch).
- **A2:** a legitimate template change by a CA admin (same 5136, but by an authorised principal).

The A1 benign case is the important one: it proves your correlation keys on *requester ≠
authenticated principal*, not merely on "a cert was issued."

---

## Week 4 — Detection engine + CI

Fast for you — this is re-implementing your existing pattern against a new store.

⚡ **DO — write `detection-engine.py`:**

- **Rule format:** YAML, Sigma-shaped but **OCSF-native** (conditions reference OCSF field paths and
  `class_uid`, not raw Windows fields). One file per detection (L1, L2, A1, A2).
- **Query:** the engine loads a rule, builds the OpenSearch query (DSL) from its conditions, runs it.
- **Stateful correlation for A1:** the engine must support a *join across two event sets* keyed on
  certificate serial, with the condition `requester != authenticated_principal`. This is the one rule
  that isn't a flat field-match — design the rule schema so a detection can declare a correlation
  (two sub-queries + a join key + a comparison predicate), not just a filter. Getting this
  abstraction right is the interesting engineering.
- **Output:** write hits to an `alerts` index (OCSF **Detection Finding**, class 2004, is the natural
  shape for the alert documents — bonus OCSF consistency).

⚡ **DO — mirror your existing CI:** pytest harness, frozen fixtures from Week 3, and a merge gate
that blocks unless each rule **fires on the malicious fixture and stays silent on the benign one**.
You already have this pattern — port it. Combined with the Week 2 schema-conformance gate, your CI
now enforces *both* "events are valid OCSF" and "rules behave correctly."

Rough rule-schema sketch (so A1's correlation has somewhere to live):

```yaml
id: A1-esc1-san-abuse
title: ESC1 certificate SAN abuse (issuance/authentication mismatch)
class_uid: 3002            # evaluated against Authentication events...
correlation:
  join_key: cert.serial_number
  left:                    # issuance side
    class_uid: 3004        # (or your documented cert-issuance extension)
    select: [requester, cert.serial_number]
  right:                   # authentication side
    class_uid: 3002        # PKINIT logon
    select: [user.name, cert.serial_number]
  condition: left.requester != right.user.name
```

---

## Week 5 — Writeups + buffer

Ring-fence this. Three posts is the entire CV payoff, and it's the first thing that gets sacrificed
if you'd rather keep building. You have the surplus; use it here.

1. **Normalising ADCS telemetry to OCSF, and where the schema breaks.** Lead with the issue-#1513
   gap, your Option A-vs-B reasoning, and your extension. This is the senior-signal post.
2. **Cross-platform persistence detection with one schema.** L1/L2 vs your existing T1053.005 /
   T1547.001 — "same technique, different platform, one schema" is the story.
3. **Detecting ESC1 through certificate request correlation.** The issuance→authentication serial
   join, and why the SAN isn't readable from a single event (Appendix A).

**Buffer:** whatever slipped — a stubborn SSSD join, a Logstash mapping that won't validate, a 5136
SACL you forgot. Something always slips; that's *why* you planned five weeks instead of four.

> **The real risk with your time surplus is the opposite of running out.** The failure mode is
> gold-plating the easy Linux/CI parts because they're comfortable, and leaving the ADCS
> schema-reasoning and the writeups shallow because they're uncomfortable. Those two uncomfortable
> things are the entire reason this project moves your CV from "Sentinel analyst" toward "detection
> engineer." Spend the surplus there.

---

## Appendix A — The A1 (ESC1) correlation, at the event level

This is the part where the detection is *real correlation*, not a field match — so here's exactly
what you're joining and, importantly, an honest note on where the telemetry is thin.

**The naive idea** ("just read the supplied SAN out of the request event and compare it to the
requester") **does not work reliably.** The Windows CA events **4886** (request received) and
**4887** (request issued) do **not** cleanly expose the attacker-supplied SAN/UPN in a parseable
field on most builds. If you go hunting for the SAN in 4886, you'll lose a day — write that blind
spot into `telemetry-inventory.md`.

**What actually works — join issuance to authentication on the certificate serial number:**

| Signal | Event | Key fields you extract |
| --- | --- | --- |
| Certificate **issued** | 4887 (or the CA database via `certutil -view`) | `Requester` (= `bob`, the account that authenticated *to the CA*), `Request ID`, **certificate serial number** |
| Certificate **used to log in** | 4768 (Kerberos TGT via PKINIT) | authenticated `Account Name` (= `administrator`, the impersonated identity), **Certificate Serial Number**, Issuer, Thumbprint |

**Join key:** certificate **serial number** (present in the 4768 "Certificate Information" fields on
a PKINIT logon, and attached to the issuance record).

**Detection condition:** for a given serial `S`,
`issuance.Requester != authentication.AccountName`.
`bob` requested it; `administrator` authenticated with it → the requester minted a cert that
authenticates as someone else → **ESC1 SAN abuse.**

⚠️ **The "where's the serial actually live?" investigation is itself blog-worthy.** On your specific
build, confirm whether 4887 carries the serial in a parseable field. If it doesn't, pull the
serial↔requester mapping from the **CA database** (`certutil -view -restrict "RequestID=..."`) and
feed *that* into the pipeline as your issuance source. Documenting "the clean join key isn't in the
security event, so here's the authoritative source I used instead" is exactly the kind of honest,
specific detail that makes post #3 credible.

**Weaker fallback (mention, don't rely on):** you can heuristically flag *any* successful PKINIT
logon (4768 with certificate info) whose authenticated principal is privileged and whose issuing
template is your enrollee-supplies-subject template. Higher false-positive rate, no requester join —
useful as a backstop, not as the primary rule. The serial-join is the one you build.

---

## Appendix B — OCSF mapping cheat-sheet

Starting points, not gospel — the validator will correct your details. All against **OCSF 4.5.0**.

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

**Certificate issuance (4886/4887)** — **no stock class.** This is your Week 2 decision: Option A
(bend into 3004 Entity Management, documenting the loss) or Option B (documented `x_certificate_*`
extension / small custom class). See Week 2 and OCSF issue #1513.

**Alerts your engine emits** → **Detection Finding (2004)** for OCSF consistency end-to-end.

---

## Appendix C — Event ID / record-type cheat-sheet

**Windows / ADCS**

| Event | Meaning | Needs enabling? |
| --- | --- | --- |
| 4886 | CA received a certificate request | Yes — `AuditFilter` + `auditpol "Certification Services"` |
| 4887 | CA approved request & issued cert | Same |
| 4768 | Kerberos TGT requested (PKINIT carries cert info) | Kerberos auditing (on by default on DC, verify) |
| 4624 | Successful logon | Logon auditing |
| 5136 | Directory service object modified | Yes — `auditpol "Directory Service Changes"` **+ SACL on the object** |
| Sysmon 1 | Process create (w/ command line) | Sysmon install + config |
| Sysmon 11 | File create | Sysmon config |

**Linux auditd** — drop into `/etc/audit/rules.d/lab.rules`, then `augenrules --load`:

```
## L1 — T1053.003 cron persistence
-w /etc/crontab       -p wa -k cron_persist
-w /etc/cron.d/       -p wa -k cron_persist
-w /etc/cron.daily/   -p wa -k cron_persist
-w /etc/cron.hourly/  -p wa -k cron_persist
-w /etc/cron.weekly/  -p wa -k cron_persist
-w /etc/cron.monthly/ -p wa -k cron_persist
-w /var/spool/cron/   -p wa -k cron_persist

## L2 — T1546.004 shell config
-w /etc/profile       -p wa -k shell_config
-w /etc/profile.d/    -p wa -k shell_config
-w /etc/bash.bashrc   -p wa -k shell_config
-w /root/.bashrc      -p wa -k shell_config
-w /root/.profile     -p wa -k shell_config
# NOTE blind spot: per-user ~/.bashrc not covered by these watches — document in telemetry-inventory.md

## execve context (feeds OCSF Process Activity)
-a always,exit -F arch=b64 -S execve -k exec
-a always,exit -F arch=b32 -S execve -k exec
```

---

## Appendix D — The ESC1 vulnerable-template recipe

Build this **only after** Week-1 auditing is proven. Record each setting as you set it.

1. `certtmpl.msc` on CA01 → right-click a base template (e.g. **User**) → **Duplicate Template**.
   (Duplicating gives you a modern schema-version template — never edit a base template directly.)
2. **General** tab → name it `ESC1-Vuln`. Note the *Template display name* and the resulting
   *Template name* (no spaces) — Certipy needs the latter.
3. **Subject Name** tab → select **"Supply in the request."** *(This is
   `CT_FLAG_ENROLLEE_SUPPLIES_SUBJECT` — the heart of ESC1.)* Acknowledge the security warning; that
   warning is literally describing the vuln you're building.
4. **Extensions** tab → **Application Policies** must include **Client Authentication** (an auth EKU).
5. **Issuance Requirements** tab → **CA certificate manager approval = unchecked**, authorised
   signatures = 0. (Approval would break the attack — leave it off.)
6. **Security** tab → add **Domain Users** → tick **Enroll** (and Autoenroll if you like).
7. Publish it: `certsrv.msc` → *Certificate Templates* node → right-click → **New → Certificate
   Template to Issue** → select `ESC1-Vuln`.

> ⚠️ **GOTCHA — duplicating a template does not publish it.** Step 7 is the one people forget.
> Without it, enrolment fails with a confusing error and you'll be convinced the template config is
> wrong. Duplicate = "define the blueprint"; *Template to Issue* = "tell the CA to actually hand
> these out." Both required.

Your ESC1 misconfiguration = *enrollee-supplies-subject* **+** *client-auth EKU* **+** *Domain Users
enroll* **+** *no approval*. Those four facts, written down, are your writeup evidence.

---

## Deliverables checklist

- [ ] 5+ VMs built, DC promoted, Enterprise CA installed, Linux boxes SSSD-joined
- [ ] CA auditing proven (4886/4887 visible on a normal enrolment) **before** any attack
- [ ] 5136 auditing proven (subcategory **+** SACL) on a template change
- [ ] `telemetry-inventory.md` — every source, on-by-default vs enabled, blind spots
- [ ] ESC1 template deliberately misconfigured, every setting recorded
- [ ] Logstash pipeline per source → OCSF 4.5.0
- [ ] `jsonschema` conformance gate in CI, merge-blocking
- [ ] Documented ADCS→OCSF mapping decision (Option A or B), referencing issue #1513
- [ ] Frozen fixtures: malicious **and** benign near-miss, for L1/L2/A1/A2
- [ ] `detection-engine.py` — YAML OCSF-native rules, OpenSearch queries, **stateful A1 correlation**,
      alerts → `alerts` index (Detection Finding 2004)
- [ ] CI gate: each rule fires on malicious, silent on benign
- [ ] Three writeups drafted

---

*Built against OCSF 4.5.0. Pull the live schema when you start Week 2 — the class IDs here (1001,
1007, 3002, 3004, 2004) are current, but attribute details evolve between releases.*
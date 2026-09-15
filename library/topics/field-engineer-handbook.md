---
title: Field engineer handbook for customer sites
date: 2026-09-06
tags: [topic, field, deployment, customer, food, hygiene, safety, communication, handover, assignment]
status: draft
source: synthesis (primary links inline and in Sources)
---

# Field engineer handbook for customer sites

## What it is

What a forward-deployed robot learning engineer needs to know to work inside a customer's plant:
what the customer is paying for, what to ask before travelling, how a food plant runs its day
and its people, how to test without stopping production, how to talk about a policy that fails
sometimes, what to hand over, and how to keep yourself functional in a 4 C room for two weeks.
Written for a meat-processing plant first because that is the current assignment
([[library/topics/meat-cutting-automation]]); most of it transfers to any factory.

The two forms that go with this note: [[templates/site-survey]] (fill in on a phone during the
first walk) and [[templates/customer-daily-update]] (the five-line update and the incident
message).

## Why it matters

- The customer measures the cell on shifts, not demos. DMRI reports uptime under 80 percent "is
  not uncommon and sometimes even as low as 50%" in meat automation, and Scott's first robotic
  lamb boning was out-yielded by the boning room within weeks
  ([DMRI 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9056032/),
  [Scott 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9056031/)). Everything in this note is
  in service of a stop log and a placement-error distribution that hold up over weeks.
- One incident ends the deployment ([[library/topics/safety-for-learned-policies]]). The rules
  about lockout, interlocks and what not to touch are the ones with no second chance.
- A food plant has a regulator in the building. A new machine on the line is a change that can
  trigger a HACCP reassessment: "Every establishment shall reassess the adequacy of the HACCP
  plan at least annually and whenever any changes occur that could affect the hazard analysis",
  with "slaughter or processing methods or systems" among the listed triggers
  ([9 CFR 417.4(a)(3)](https://www.law.cornell.edu/cfr/text/9/417.4)). Your cell is that change.
- The camera that watches the piece also watches the people. Recording workers is regulated
  (GDPR Art. 88 and the EDPB video guidelines in the EU, biometric statutes in some US states)
  and the customer's HR and legal will ask before QA does.

## The role

The forward-deployed engineer role comes from Palantir, which built it in the early 2010s
(internally "Delta") and until about 2016 employed more FDEs than product engineers. The FDE
alternates between embedding with a customer and feeding what was learned back to the product
team; Palantir's framing is "one customer, many capabilities" and "technical outcomes for our
customers" ([Pragmatic Engineer, Aug 2025](https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers)).
The robotics version adds hardware, a safety chain and a production schedule. Chef Robotics
describes its field model as software that self-diagnoses, a 24/7 remote support portal with
PagerDuty escalation, certified third-party technicians for maintenance, engineers travelling
"for complex integrations", and a target that "fewer than 5% of support cases escalate to
engineering"; the customers that trusted it went from 2 to 36 and 2 to 22 robots
([Chef Robotics, Aug 2026](https://www.chefrobotics.ai/post/how-chef-supports-robots-at-scale-across-two-continents)).
Read that as the customer's scoreboard: the pilot is judged on whether the second and tenth
robot get ordered.

How the customer measures you, in the order they will bring it up:

| Measure | Who asks | Number to have ready |
|---|---|---|
| Did the line run | Plant manager | Stops caused by the cell, by cause and minutes, per shift |
| Yield and placement | Production and QA | Lane offset and yaw, median and 95th percentile, pieces per condition ([[library/topics/meat-cutting-automation]]) |
| Throughput | Production | Pieces per minute sustained over 30 min against the manual station |
| Interventions | Operators, maintenance | Per shift, with the cause list |
| Hygiene | QA, the inspector | Pre-op inspection pass, ATP swab results, declarations on file |
| Safety | Safety officer, maintenance | Zero contacts; shield log; LOTO compliance |
| Did you show up and answer | Everyone | Daily update sent, phone answered, cell left clean |

The soft measures decide renewals as often as the hard ones (unverified, no published data on
robotics pilots found; the Chef expansion figures above are the closest public evidence).

## Before the visit

### Site survey

Send the questionnaire two weeks ahead; expect half of it back; fill the rest on the first walk
with [[templates/site-survey]]. What each block is for:

- **Power.** Voltage and phase at the cell, circuit rating, whether the robot controller and the
  GPU box get their own breaker, where the nearest outlet a laptop can use without a permit is.
  Wet-area outlets are GFCI or RCD protected and the GPU box's PSU may trip them (unverified,
  test in the lab with a portable RCD).
- **Network.** Plant Ethernet at the cell or not, who owns the switch, whether the OT network is
  segmented from IT (see the IT requests below), 4G or 5G signal inside the cold room for a
  fallback modem.
- **Floor.** Drains, slope, wet or dry, floor-mounted or ceiling-mounted robot base, forklift
  and pallet-jack traffic through the aisle, the hose-down path.
- **Lighting.** Overhead type, whether it changes between shifts and during washdown, windows,
  the position of the cutter's own lights. Lock the camera exposure regardless
  ([[library/topics/meat-cutting-automation]]).
- **Temperature and humidity.** EU cutting rooms run at "an ambient temperature of not more than
  12 °C" with meat at "not more than 3 °C for offal and 7 °C for other meat"
  ([Reg. 853/2004 Annex III Sec. I Ch. V](https://www.legislation.gov.uk/eur/2004/853/annex/III));
  US plants set their own in the HACCP plan. Boning rooms at 2 to 4 C and near-saturated humidity
  are what to plan for. Consequences for kit: condensation on any electronics brought in from a
  warm room, laptop batteries losing capacity, touchscreens that do not work with gloves.
- **Washdown schedule.** When the sanitation shift starts, what chemicals (alkaline foam, chlorine,
  peracetic acid, quaternary ammonium: get the SSOP list), water pressure and temperature, and
  whether the cell is inside the washdown zone. IP69K is 80 to 100 bar at 80 C from 10 to 15 cm
  ([[library/topics/meat-cutting-automation]]). Anything without that rating leaves the room or
  gets a cover before sanitation starts.
- **Shift patterns.** Production shifts, break times, changeovers, the sanitation shift, and the
  pre-operational inspection window before first product, which is a written daily procedure under
  [9 CFR 416.12](https://www.law.cornell.edu/cfr/text/9/416.12). Your test windows are the gaps.
- **Who owns what.** Names for: plant manager, production supervisor per shift, maintenance
  lead, controls engineer, QA manager, safety officer, plant IT, the integrator, the cutter
  vendor's service contact, and the FSIS inspector-in-charge or equivalent. One person per row.

### Requests to plant IT

Plants that follow OT security guidance segment control networks from the business network and
gate remote access ([NIST SP 800-82 Rev. 3](https://csrc.nist.gov/pubs/sp/800/82/r3/final);
[ISA/IEC 62443](https://www.isa.org/standards-and-publications/isa-standards/isa-iec-62443-series-of-standards)
defines requirements for asset owners, integrators and product suppliers). Ask in writing, four
weeks ahead, using their change form if they have one:

- [ ] A VLAN or physically separate switch for the cell: robot controller, safety PLC link, cameras,
  policy PC, GPU box. No Wi-Fi carries DDS ([[sops/robot-bring-up]]).
- [ ] Static IPs and a reserved `ROS_DOMAIN_ID`; the address plan written down and given back to them.
- [ ] Firewall rules: which ports from the cell to the plant historian or MES, which outbound ports
  for model and log sync, and a stated "none" for everything else.
- [ ] Remote access: their VPN or jump host, named accounts, session logging, and a written rule that
  remote restart of a container is allowed and remote release of a safety stop is not
  ([[library/topics/fleet-operations]]).
- [ ] NTP source inside the plant, or permission to run `chrony` against a cell-local clock.
- [ ] Their policy on USB drives and laptops on the OT network. Assume both are banned until told
  otherwise.

### PPE, hygiene and food safety basics

The rules are the plant's, taught in their induction; the regulations behind them are short
enough to read on the plane.

- Employee hygiene in a USDA plant: hygienic practices for anyone "working in contact with product,
  food-contact surfaces, and product-packaging materials", clean outer garments at the start of
  each day, and exclusion of anyone with an infectious disease or open lesion
  ([9 CFR 416.5](https://www.law.cornell.edu/cfr/text/9/416.5)). FDA-regulated plants have the
  same list plus jewelry, gloves, hair and beard restraints, and no eating, gum or tobacco where
  food is exposed ([21 CFR 117.10](https://www.law.cornell.edu/cfr/text/21/117.10)).
- HACCP: the plant's hazard analysis and critical control points, written per
  [9 CFR 417](https://www.law.cornell.edu/cfr/text/9/part-417). You will not be asked to write
  any of it; you will be asked whether the cell introduces a hazard (foreign material from a
  gripper, lubricant, a surface that cannot be cleaned) and the answer must be documented, with
  the reassessment trigger quoted above in mind.
- Allergens: nine major allergens in US law (milk, eggs, fish, crustacean shellfish, tree nuts,
  peanuts, wheat, soybeans, sesame; sesame from 1 January 2023)
  ([FDA](https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/food-allergies)).
  A meat plant's concern is cross-contact between lines and species; do not carry tools or
  cloths between rooms, and do not bring food into the plant.
- Contamination rules that bite engineers: no loose small parts (cable ties, screws, pens,
  phone) above open product; metal-detectable materials where a fragment could shed; nothing
  wooden; a declared list of every material that touches product
  ([[library/topics/meat-cutting-automation]]).
- Ammonia. Most cold-chain plants run anhydrous ammonia refrigeration; at 10,000 lb or more it is
  covered by OSHA process safety management, which is where the plant's management-of-change
  procedure and its ammonia alarm training come from
  ([29 CFR 1910.119 App. A and (l)](https://www.law.cornell.edu/cfr/text/29/1910.119)). Know the
  alarm sound and the muster point before the first day.

Before travel: induction booked, boot and coat sizes sent, medical questionnaire done, no open
cuts, hair and beard cover packed if the plant does not supply them.

## On site

### The people and their vocabulary

| Term | What it is | Why you care |
|---|---|---|
| PLC | The programmable logic controller running the line; the cell PLC owns the cutter start and the production gate | Your "pose OK" is an input to it, never a safety signal ([[library/topics/meat-cutting-automation]]) |
| HMI | The touchscreen operators use | Any state your cell has must be visible on it or operators will not trust the cell |
| SCADA, historian, MES | Plant-wide supervision, time-series store, production execution | Where the customer's uptime and count numbers come from; get your stop reasons into it |
| Tags | Named PLC variables (`CutterReady`, `ArmInZone`) | The interface contract; ask for the tag list and the data types |
| LOTO | Lockout/tagout under [29 CFR 1910.147](https://www.law.cornell.edu/cfr/text/29/1910.147): an "authorized employee" locks out to service a machine; an "affected employee" operates it | You are outside personnel; (f)(2) requires the plant and your employer to inform each other of their procedures. Never remove a lock that is not yours |
| Permit to work | A written authorisation for a hazardous job, signed by the area owner ([HSE HSG250](https://www.hse.gov.uk/pubns/books/hsg250.htm)) | Hot work, working at height, confined space, and often any work inside a guarded cell |
| MOC | Management of change: written procedure covering technical basis, safety impact, procedure updates, time period and authorisation before a change ([1910.119(l)](https://www.law.cornell.edu/cfr/text/29/1910.119)) | A new checkpoint, a new camera position or a new shield limit is a change. Ask which form the plant uses |
| Pre-op | Pre-operational sanitation inspection before first product ([9 CFR 416.12](https://www.law.cornell.edu/cfr/text/9/416.12)) | Your cell must pass it every morning or the line starts without you |
| SSOP | Written sanitation SOP | Names your cell's surfaces and how they are cleaned |

Controls and maintenance engineers own the PLC, the safety configuration and the interlocks.
They have seen automation vendors arrive with laptops and leave with the line down. Ask for their
time in advance, show them the shield log, and route every change through them.

### The daily rhythm

- [ ] Arrive before pre-op. Walk the cell with the sanitation lead; anything left wet or streaked
  is your problem to fix before the inspector sees it.
- [ ] Production start: watch the first 30 minutes at the cell, not from the office.
- [ ] Test windows: breaks, changeovers, the gap between last product and sanitation, and any
  agreed off-line time. Confirm the window with the supervisor the day before, in writing.
- [ ] Data backup every 2 hours ([[sops/field-deployment-checklist]]).
- [ ] Before sanitation: electronics out or covered, cameras' housings closed, cables lifted off
  the floor, the cell in the state the SSOP describes.
- [ ] Daily update sent before you leave the plant ([[templates/customer-daily-update]]).

### Running a test without stopping the line

Options in rising order of disruption; choose the lowest that answers the question:

1. **Shadow mode.** The policy sees live observations and logs actions; the manual station or the
   existing automation keeps working. Costs nothing on the line; yields placement-error estimates
   only if the verification camera can score the manual placement too.
2. **Diverted product.** A bin of pieces from the line, run at a presented-piece station off the
   belt, at the belt's product temperature. Answers grasp and pose questions, not tracking.
3. **Bypass lane or parallel infeed.** The cell feeds the cutter on one lane while the manual
   station feeds the other. Needs the cutter vendor's agreement and a PLC change (MOC).
4. **Agreed line time.** A booked window, the supervisor present, a stated stop condition and a
   stated maximum duration.

For every option: the PLC production gate stays with the plant, the pendant slider and the
deadman stay with you, and the stop condition is written before the trial starts
([[sops/robot-bring-up]]).

### Escalation paths

| Event | First call | Then | Within |
|---|---|---|---|
| Contact, injury, unexpected motion | Stop the cell; the supervisor and safety officer | Your manager; incident log ([[sops/incident-log-template]]) | 15 minutes |
| Cell down, line affected | Supervisor and maintenance lead | Your manager; the integrator if the safety chain is involved | Immediately |
| Hygiene finding by QA or the inspector | QA manager | Your manager; fix before next pre-op | Same shift |
| Network or IT change needed | Plant IT contact | Their change process | Their SLA |
| Cutter fault | Cutter vendor service line via the plant | Log the fault code | Same day |

### What to never touch

- The safety configuration, the safety PLC, or any interlock wiring. Read-only, photographed,
  changed by the integrator ([[library/topics/safety-for-learned-policies]]).
- A lock or tag that is not yours. Ever.
- The PLC program. You supply tags and a spec; the controls engineer writes the rungs.
- The cutter, beyond its infeed. Its guards and its service are the vendor's.
- Product on the line, unless gloved, gowned and told to by QA. Dropped product is waste, not
  a test piece.
- Ammonia lines, valves and alarms.
- The plant network beyond your VLAN. No scanning, no DHCP server, no bridging Wi-Fi.

## Talking about learned policies

**What a success rate means.** A policy success rate is k successes in n trials under a written
protocol, with an interval. Report it as "184/200 pieces placed inside the window, Wilson 95
percent interval 87.4 to 95.0 percent, product X, belt 250 mm/s, 4 September" and never as
"92 percent" ([[library/topics/policy-evaluation]]).

**Why 95 is not 100.** The customer's manual station is also not 100 percent; get its number on
the same lot before the pilot. Then: 95 percent at 60 pieces per minute is 3 rejects per minute,
which is a reject lane, a person, or a stop, and which of those it is decides whether the cell is
worth having. For a safety claim, zero failures in n trials bounds the failure rate near 3/n at 95
percent confidence: 100 clean trials bound it near 3 percent per trial, 1000 near 0.3 percent
([Hanley and Lippman-Hand 1983](https://doi.org/10.1001/jama.1983.03330370053031)). Say the
number before anyone asks.

**How to present evidence.** One page per claim: the claim, the protocol, the number with its
interval and trial count, the conditions covered and the conditions not covered, the log file
name ([[library/topics/safety-for-learned-policies]]). Video of successes is decoration; video of
the failure modes with the stop log next to it is evidence.

**What to promise.** Availability of the system, the response time by severity, and a process by
which the success rate improves with data. Not a success rate ([[library/topics/fleet-operations]]).
An improvement curve promised on a date is a training run that has not happened yet; say so.

**Data rights and worker privacy.** The camera records people. Settle these in writing before the
first frame is stored:

- Who owns the recordings and the derived datasets, who may train on them, whether they leave the
  site, and for how long they are kept. A contract clause, not an email.
- EU: consent from employees is generally not freely given, so the employer needs another legal
  basis and should not rely on consent (EDPB Guidelines 3/2019 para. 47); a warning sign at the
  cell must state the purposes, the controller and the data-subject rights and point to the full
  notice (para. 114); storage beyond 72 hours needs more justification (Section 8)
  ([EDPB 3/2019](https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-32019-processing-personal-data-through-video_en)).
  Member States and works agreements add rules under
  [GDPR Art. 88](https://gdpr-info.eu/art-88-gdpr/); a works council may need to agree.
- US: Illinois BIPA requires written notice of purpose and term and a "written release" before
  collecting biometric identifiers, plus a written retention policy with destruction within 3 years
  of last interaction ([740 ILCS 14/15](https://www.ilga.gov/Documents/legislation/ilcs/documents/074000140K15.htm)).
  Whether workspace video that never extracts a face template is a biometric collection is a
  question for the customer's counsel; do not answer it yourself. Texas and Washington have
  biometric statutes too (unverified this session).
- Engineering controls that make the conversation easier: crop or mask the field of view to the
  belt and the arm, store no audio, keep faces out of the training set, delete raw footage on a
  schedule and log the deletion, and put the retention period in the DATASET.md
  ([[sops/data-collection-protocol]]).

## Documentation and handover

What the customer holds when you leave, each a file in their system and in ours:

- **As-built.** Network diagram with IPs and VLAN, tag list with data types and direction, safety
  configuration photographs, camera mounts with heights and angles, the parts list with material
  declarations and IP ratings, and the configuration record (checkpoint hash, git SHAs, image
  tags, shield limits, watchdog timeout, calibration hash) from [[library/topics/safety-for-learned-policies]].
- **Runbooks.** Start of shift, end of shift, pre-sanitation, post-sanitation recalibration, jam
  clearing (written with maintenance, because it is a lockout question under the minor-servicing
  exception of [1910.147](https://www.law.cornell.edu/cfr/text/29/1910.147)), product changeover,
  what each HMI message means and what to do, who to call. One page each, laminated, at the cell.
- **Operator training.** Each operator runs the cell through a shift start, a jam, a product
  change and a shift end with you watching, and signs a record. Maintenance gets the same plus
  camera cleaning and the recalibration check.
- **Acceptance test protocol.** Written before the pilot, agreed with the customer, run at the
  end: the evaluation protocol from [[library/topics/meat-cutting-automation]] (placement error
  distribution at 200 pieces per condition, throughput over 30 min, miss/drop/double by cause,
  uptime by cause over a full shift, pre-op and ATP pass, yield against the manual baseline) with
  pass thresholds the customer wrote down.
- **Sign-off.** The bring-up sign-off record ([[sops/robot-bring-up]]) plus the acceptance test
  results, signed by the engineer and the customer's named owner. No blank lines.

## Communication

**Daily update.** Five lines, sent before leaving the plant, same recipients every day:
done, evidence with numbers and trial counts, blocked, tomorrow, decisions needed. The template
is [[templates/customer-daily-update]]. Numbers with counts; no adjectives.

**Incident communication.** Facts within 15 minutes to the supervisor and your manager, the
incident log filled ([[sops/incident-log-template]]), a written follow-up within 24 hours with
cause marked as hypothesis, and the cell down until a named person signs it back. Injury
recordkeeping is the plant's duty under OSHA 29 CFR 1904, within 7 calendar days
([OSHA](https://www.osha.gov/recordkeeping)); give them what they need for it. The message
template is in [[templates/customer-daily-update]].

**Weekly customer report.** One page: the objective for the week, the numbers table (placement
error, throughput, uptime by cause, interventions, all with counts), what changed in the cell and
its MOC reference, open risks with owners, next week's plan and the decisions you need. Same
structure every week so the customer can diff it.

## Kit

- [ ] Laptop with the offline stack ([[sops/field-deployment-checklist]]), a second laptop or a
  mini PC as a spare, chargers for both, a power strip with a long cord.
- [ ] Network: managed switch, 30 m and 5 m Ethernet cables, USB-Ethernet adapters, a 4G/5G
  modem with a data SIM, labels and a marker.
- [ ] Console: USB-serial adapter, the robot vendor's pendant cable, HDMI cable and a small monitor.
- [ ] Hand tools: metric hex keys, torque driver, multimeter, cable ties (metal-detectable for
  inside the cell), tape measure, spirit level, headlamp.
- [ ] Sensor spares: one camera, one lens, calibration target sealed in a cleanable bag, lens
  cloths, desiccant packs.
- [ ] Hygiene: your own steel-toe washdown boots if the plant allows them, thermal base layers, a
  fleece under the plant coat, thin liner gloves that work under nitrile, a stylus.
- [ ] Documents printed: the safety configuration photos, the tag list, the acceptance protocol,
  the address plan, the escalation table with phone numbers.
- [ ] Storage: external SSD, tested; a second one.

## Practical gotchas

- **Manual out-yields the robot at first**, and the customer will notice within days
  ([Scott 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9056031/)). Baseline the manual
  station on the same lot before the pilot.
- **Uptime kills pilots, not demo success** ([DMRI 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC9056032/)).
  Stops by cause from the first shift, in the plant's historian if they will take the tags.
- **"Hygienic robot" is a claim, not a certificate.** No robot, gripper or camera housing is on
  the EHEDG certified list ([EHEDG](https://www.ehedg.org/certification-testing/certified-equipment/list-of-certified-equipment));
  the plant QA decides.
- **Jam clearing is a lockout question.** The minor-servicing exception needs alternative measures
  that give effective protection ([1910.147](https://www.law.cornell.edu/cfr/text/29/1910.147));
  write the procedure with maintenance before the first jam.
- **Camera recalibration after washdown** is a daily job until the mounts prove otherwise
  (unverified, [[library/topics/meat-cutting-automation]]).
- **A new checkpoint is a change** to the cell under the integrator's risk assessment
  ([[library/topics/safety-for-learned-policies]]) and under the plant's MOC. Budget the paperwork.
- **Condensation.** Electronics moved from a warm office into a 4 C room at high humidity fog
  and drip. Let kit acclimatise in its case, or keep it in the cold room (unverified as a
  procedure; physics is not).
- **Cold.** Layers of loose clothing and warm breaks are NIOSH's controls for cold work
  ([NIOSH cold stress](https://www.cdc.gov/niosh/cold-stress/about/index.html)); fine motor
  work on a laptop degrades before you feel cold. Set a timer for a warm-up every hour.
- **Sleep and long days.** Sanitation runs at night and production starts at 05:00; you cannot
  attend both for two weeks. Pick the window that answers this week's question and sleep for the
  other. Keep the field note as you go; nothing written from memory after 14 hours is reliable
  ([[sops/field-deployment-checklist]]).
- **Note-taking discipline.** One `field-notes/` file per day, timestamped entries, photographs
  named by time and location, every number with its unit and trial count at the moment it is
  read, the customer summary drafted before leaving the plant.

## What a forward-deployed engineer must be able to do

- Walk a plant once and come back with the site survey filled, the owner list complete, and the
  three questions that decide the design.
- Write the IT request, the MOC form and the permit-to-work application in the plant's own
  vocabulary, and get them through before the kit ships.
- Pass the plant induction and a pre-op inspection with the cell in the state the SSOP describes.
- Run a shadow-mode or diverted-product test in a break window without a line stop, with the stop
  condition written first.
- Explain to a plant manager what 184/200 with an interval means, what the manual baseline is,
  and what the pilot will promise (availability and a process) and not (a success rate).
- Explain to HR and counsel what the camera records, where it goes, how long it is kept, and
  which faces are masked.
- Hand over as-builts, runbooks, trained operators and a signed acceptance test that a stranger
  could use to restart the cell.
- Send the five-line update every day and the incident message within 15 minutes, both with
  numbers and without adjectives.

## Open questions

- The plant's actual ambient and product temperatures and washdown chemistry; everything in the
  kit list depends on them.
- Whether plant IT will allow a cell VLAN with a cellular fallback, or insist on their VPN only.
- The customer's position on video: on-site only, or allowed to leave for training, and under
  which contract clause.
- Which change-control form the plant uses for non-PSM equipment, and how long it takes.
- What the manual station's placement error and throughput are on the pilot lot.
- Whether the cutter vendor will allow a bypass lane for parallel testing.
- A verified account of the FDE role from a robotics company other than Chef; none was reachable
  this session.

## Related entries

- [[library/topics/meat-cutting-automation]] (the cell, hygiene and regulatory map, evaluation protocol)
- [[library/topics/safety-for-learned-policies]] (standards map, evidence folder, what a safety function is)
- [[library/topics/policy-evaluation]] (intervals, trial counts)
- [[library/topics/fleet-operations]] (SLAs, incident severity, remote access rules)
- [[library/topics/deployment-engineering]] (shadow and canary rollout)
- [[sops/field-deployment-checklist]], [[sops/robot-bring-up]], [[sops/incident-log-template]], [[sops/data-collection-protocol]]
- [[templates/site-survey]], [[templates/customer-daily-update]]

## Sources

- FDE role: Orosz, "What are Forward Deployed Engineers, and why are they so in demand?", Pragmatic Engineer, 12 Aug 2025. https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers (Palantir's own blog post on the role returned HTTP 403 this session and is not cited)
- Robotics field model: Chef Robotics, "How Chef Supports Robots At Scale Across Two Continents", 24 Aug 2026. https://www.chefrobotics.ai/post/how-chef-supports-robots-at-scale-across-two-continents
- Meat automation uptime and yield: DMRI, Animal Frontiers 2022 https://pmc.ncbi.nlm.nih.gov/articles/PMC9056032/ ; Scott R&D, Animal Frontiers 2022 https://pmc.ncbi.nlm.nih.gov/articles/PMC9056031/
- Food regulation: 9 CFR 416.5 https://www.law.cornell.edu/cfr/text/9/416.5 ; 9 CFR 416.12 https://www.law.cornell.edu/cfr/text/9/416.12 ; 9 CFR 417 https://www.law.cornell.edu/cfr/text/9/part-417 ; 9 CFR 417.4 https://www.law.cornell.edu/cfr/text/9/417.4 ; 21 CFR 117.10 https://www.law.cornell.edu/cfr/text/21/117.10 ; FDA major allergens https://www.fda.gov/food/nutrition-food-labeling-and-critical-foods/food-allergies ; Regulation (EC) 853/2004 Annex III https://www.legislation.gov.uk/eur/2004/853/annex/III ; EHEDG certified list https://www.ehedg.org/certification-testing/certified-equipment/list-of-certified-equipment
- Occupational safety: 29 CFR 1910.147 https://www.law.cornell.edu/cfr/text/29/1910.147 ; 29 CFR 1910.119 https://www.law.cornell.edu/cfr/text/29/1910.119 ; HSE HSG250 permit-to-work https://www.hse.gov.uk/pubns/books/hsg250.htm ; OSHA recordkeeping https://www.osha.gov/recordkeeping ; NIOSH cold stress https://www.cdc.gov/niosh/cold-stress/about/index.html
- OT networks: NIST SP 800-82 Rev. 3 (Sep 2023) https://csrc.nist.gov/pubs/sp/800/82/r3/final ; ISA/IEC 62443 https://www.isa.org/standards-and-publications/isa-standards/isa-iec-62443-series-of-standards
- Privacy: EDPB Guidelines 3/2019 on video devices (v2.0, 29 Jan 2020) https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-32019-processing-personal-data-through-video_en ; GDPR Art. 88 https://gdpr-info.eu/art-88-gdpr/ ; 740 ILCS 14/15 (BIPA) https://www.ilga.gov/Documents/legislation/ilcs/documents/074000140K15.htm
- Statistics: Hanley and Lippman-Hand, JAMA 1983 https://doi.org/10.1001/jama.1983.03330370053031

Changes: 2026-09-06 created for the meat-plant assignment.

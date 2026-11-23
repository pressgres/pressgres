# R-008 — User discovery kit

This kit is for the solo maintainer to run 5–10 interviews, recommend a first persona and hand two plugin targets to R-014 when the evidence warrants it. [R-007 approved a solo preview pilot](R-007-m0-go-no-go.md#stop-and-re-evaluate-triggers). The proposed first target is one managed WordPress 7.1 series on PHP 8.4 and PostgreSQL 18 with native UUIDv7 IDs throughout. Exact release pins and compatibility depend on testing. [Version policy](../adr/0006-version-policy.md)

## Decisions the interviews feed

| Decision | Evidence to collect |
|---|---|
| First persona | Which of agency, host, enterprise platform or individual developer has recurring PostgreSQL-related friction, a real WordPress project and a path to running the preview? Where do native UUIDs help or break existing workflows? |
| Fresh sites at 1.0 | Is there a new site the persona could start? Would content recreated through a tested path suffice, or must an existing MySQL site retain its data, links or integrations? A confirmed import dependency can reopen [ADR-0009](../adr/0009-legacy-migration.md). |
| Two plugin targets | Which specific plugins and workflows would block the first persona, and what substitutes have they tried? Send the evidence to [R-014](../08-roadmap.md#m0--feasibility-and-adr-sign-off-research). |
| Production environment | Where does the organisation deploy today, and who controls DB TLS trust, certificates, secret storage and credential rotation? |
| Preview and maintenance | Who can approve an isolated pilot of a managed core patchset? What legal, operational or security requirements apply? Who can allocate budget, review time or ongoing maintenance capacity? |

These decisions inform the [M1 open questions](../14-open-decisions.md#questions-to-resolve-before-m1).

## Recruiting

Recruit organisations that standardise on PostgreSQL and already run WordPress or have evaluated it for a concrete project. Include teams that kept a MySQL exception or rejected WordPress. Recruit people involved in a recent CMS, hosting or database decision. Count one decision-making unit per organisation. An independent developer qualifies when they can describe a real project and make the stack decision themselves.

| Persona | Who to look for |
|---|---|
| Agency | Delivery or technical leads who build WordPress client sites and operate PostgreSQL elsewhere. |
| Host | Managed hosting operators with PostgreSQL infrastructure and experience approving or running WordPress workloads. |
| Enterprise platform | Internal platform teams whose approved database is PostgreSQL and whose content teams run or have requested WordPress. |
| Individual developer | Independent developers who standardise their own projects on PostgreSQL and run or have evaluated WordPress for a specific project. |

Start with five interviews, aiming to cover all four personas where possible. Use the remaining slots, up to ten total, to verify an emerging pattern, fill gaps and hear from teams that declined a similar project. Recruit from both ecosystems so the sample includes people already operating PostgreSQL and people responsible for WordPress delivery.

- **Communities.** Local PostgreSQL user groups and organisers of WordPress meetups. Ask organisers where opt-in research invitations belong. [PostgreSQL community](https://www.postgresql.org/community/), [WordCamp Central](https://central.wordcamp.org/)
- **Conferences.** PostgreSQL conferences and PGDays, WordCamps, and platform engineering or open-source events with public community channels. [PostgreSQL events](https://www.postgresql.org/about/events/), [WordCamp Central](https://central.wordcamp.org/)
- **Forums.** WordPress development and hosting discussions and PostgreSQL mailing lists can surface relevant workflows. Follow venue rules and use an approved opt-in channel for invitations. Keep recruitment threads free of screener answers. [WordPress.org forums](https://wordpress.org/support/forums/), [PostgreSQL community](https://www.postgresql.org/community/)

### Outreach message

> I maintain Pressgres, an early project exploring WordPress on PostgreSQL. I'm looking for people whose teams standardise on PostgreSQL and have run or evaluated WordPress for a real project. Could I ask about your last CMS or hosting decision in a 30–45 minute call? Participation is voluntary. I take private notes and publish only anonymised findings combined across interviews. If you're interested, please reply privately.

### Screener

1. What kind of work do you do, and which CMS or infrastructure decisions do you take part in?
2. What database engines does your team approve or operate today? How are exceptions handled?
3. When did you last deploy WordPress or evaluate it for a specific project? What did you choose?
4. Was that project a fresh site or a move from an existing site? What is the next comparable project you expect?
5. Who operates the CMS and database today? Who signs off on an isolated, non-production evaluation?
6. Can you spend 30–45 minutes discussing the decision and workflow without sharing customer data or credentials?

## Interview guide (30–45 minutes)

Use the low end of each time range for 30 minutes. Start from a recent example, then ask what happened, who was involved, what it cost and what they did next. Keep the product description until the discovery questions are covered. Ask neutral follow-ups when they name a workaround or exception.

| Time | Stage | Prompts |
|---|---|---|
| 3–4 min | Warm-up and consent | Ask for consent using the wording below. What do you own in the publishing or hosting stack? Walk me through the last CMS decision you took part in. |
| 4–6 min | Current stack | Where did that site run, and which database and CMS did you choose? What else did you consider? Who decided, and what constraints drove the choice? |
| 4–6 min | Pain and PostgreSQL/UUID value | What happened the last time a CMS needed a database outside your standard? What did you do and what did it cost? Where do entity IDs cross system boundaries today? Walk me through the last time an ID format affected an import, API or integration. Which systems expect numbers or strings? |
| 4–6 min | Plugins and fresh sites | Walk me through what the site needed on launch day. Which exact plugins provided those workflows, and which versions or editions mattered? What did you try in their place? For your next site, what has to come across from an existing one? What happened the last time you recreated content or moved a site? |
| 5–7 min | Operations and security | Walk me through your last deployment or database rotation. Who owns the runtime and DB service? Who configures TLS trust, renews certificates, manages secrets and rotates credentials? What happened during your last urgent patch or restore? What evidence and approvals are required to run a patched upstream distribution? |
| 6–8 min | Preview disclosure and fit | Read the disclosure below. What recent or planned project, if any, could use this setup? What changes if WordPress uses PostgreSQL but all entity IDs are UUID strings? What breaks? What would the first approval or setup step look like? Who could take it, and when? What would stop the trial? |
| 4–8 min | Wrap-up and sustainability | How did you fund or staff the last dependency you relied on? What could your team realistically offer here, if anything? Who can approve funding or recurring review or maintenance time? What evidence would they need? Is there a next step you want to take, and may I follow up? |

### Preview disclosure

> Pressgres is a preview pilot for isolated, non-production evaluation with disposable or synthetic data. It uses a managed WordPress core patchset, one WordPress release series, PostgreSQL 18 and native UUIDv7 IDs. One maintainer handles releases. Security updates are best effort, with no guaranteed response time or SLA. The first release plan starts with fresh sites. Legacy MySQL import is a separate, restricted proposal. Plugin compatibility is version-specific and depends on testing. Given those limits, what would your organisation do next, if anything?

Avoid a feature pitch, named plugin suggestions before unaided recall, and promises about timing, support, speed or security. Questions such as “Wouldn't one database simplify everything?” and “Would you pay for this?” invite agreement. Ask for a recent decision, its consequences and a next step the participant is able to take. Skip speculative plugin lists and requests for confidential examples.

## Private interview notes

Copy this template into a private workspace before the call. Spend five minutes filling gaps immediately afterwards. Mark missing answers as **unknown** and distinguish observed past behaviour, participant statements and your own inferences.

| Field | Notes |
|---|---|
| Interview code, date, primary persona | ___ |
| Consent to notes and anonymised aggregate reporting, plus follow-up permission | ___ |
| Recent project, respondent's role, decision and owner | ___ |
| DB standard, actual friction, workaround and cost | ___ |
| ID workflow, benefit of native UUID strings, integration constraints | ___ |
| Next site, fresh-site fit at 1.0, data and dependencies that must move | ___ |
| Likely production environment, DB TLS/trust owner, secrets/rotation owner, operator and incident owner | ___ |
| Patchset approval, recovery and security update requirements | ___ |
| Funding/co-maintenance precedent, offered action and approver | ___ |
| Preview outcome (**ready**, **conditional**, **no**, **unknown**), reason and evidence | ___ |
| Pilot workload, environment, next action, accountable role and timeframe | ___ |
| Strong persona signal (**yes** or **no**), reasons and contrary evidence | ___ |

Record one line per plugin, using the participant's evidence about the workflow.

| Plugin slug or product, version/edition | Workflow | Required or optional | Substitute tried and outcome | Impact without it |
|---|---|---|---|---|
| ___ | ___ | ___ | ___ | ___ |

## Synthesis

Use a private copy of the [aggregate CSV template](data/R-008-synthesis-template.csv). Remove the fictional row before tallying. Count an organisation once per persona and once per plugin. Use the role in the pilot decision to select a primary persona when several fit. Merge aliases by plugin slug or product identity and retain version and edition differences in the private worksheet.

| Persona | Interviewed | Ready / conditional / no / unknown | Strong signals | Fresh-site fit / import blockers | Deployment pattern with DB TLS and secrets owners | Funding or maintenance actions | Preview blockers |
|---|---:|---|---:|---|---|---|---|
| Agency | ___ | ___ | ___ | ___ | ___ | ___ | ___ |
| Host | ___ | ___ | ___ | ___ | ___ | ___ | ___ |
| Enterprise platform | ___ | ___ | ___ | ___ | ___ | ___ | ___ |
| Individual developer | ___ | ___ | ___ | ___ | ___ | ___ | ___ |

| Persona | Plugin | Orgs mentioning | Orgs blocked without it | Ready orgs blocked without it | Workflow and substitute tried | R-014 target or open question |
|---|---|---:|---:|---:|---|---|
| ___ | ___ | ___ | ___ | ___ | ___ | ___ |

The plugin counts refer to dependencies for a real site or pilot workflow. A **required** mention has a concrete consequence and no acceptable substitute the organisation has identified. Keep total mentions visible alongside required mentions. Flag if both proposed plugins would still leave the same pilot blocked by other required dependencies.

Classify pilot willingness only after the disclosure.

| Outcome | Evidence |
|---|---|
| Ready | Would run an isolated preview on the disclosed terms for a specific workload, with a plausible approval path, an accountable role and a concrete next step and timeframe. A named compatibility target may be the subject of the evaluation. A requirement for proven compatibility before evaluation is conditional. |
| Conditional | Can name a condition that must change or a decision that must be made before they would run it. Record the condition and who could resolve it. |
| No | Declines or states a decisive blocker, such as production-only adoption, a mandatory SLA, prohibited patched core, unavailable isolation, required legacy import or an essential plugin that rules out evaluation. Record the reason in their terms. |
| Unknown | Approval or intent is unclear, or the respondent lacks the information to answer. A compliment, “keep me posted” or interest in a demo is insufficient evidence of readiness. |

For each repeated blocker, tally the organisations affected and whether the blocker rules out the preview or only production use. Sum the four outcome counts across personas for the R-007 decision. In the CSV, use a `persona` row for each persona and a `plugin` row for each plugin within that persona. Fill the columns that apply to the row type. Leave inapplicable cells blank and use zero for measured zero counts.

## Decision rule

1. **Check after five completed, qualified interviews with independent organisations.** Use up to ten total if a persona or plugin still lacks evidence, if leading signals are tied, or if preview outcomes need clarification. Follow up once on unresolved approval paths with permission. Record the final sample and its gaps.
2. **Choose a first persona with at least two strong signals from independent organisations in that persona.** A strong signal is a **ready** outcome plus a concrete WordPress workload and a recent example of PostgreSQL standardisation causing meaningful effort, delay or a decision constraint. Record actual UUID benefits or integration costs separately. If multiple personas qualify, favour the one with more strong signals, then the one with more concrete pilot steps already taken. If evidence still ties or no persona clears the threshold by interview ten, leave the choice open.
3. **Test fresh-site-only against the selected persona.** Treat fresh-site fit as supported if at least two strong-signal organisations can start representative fresh sites. If at least two organisations in that persona have concrete projects blocked without legacy MySQL import, bring those cases to ADR-0009 review, including which data and integrations must carry over. If both thresholds are met, report mixed evidence and bring both groups to the review. If neither is met, leave the evidence inconclusive. A review can reconsider the timing of the restricted import pilot.
4. **Recommend up to two R-014 targets.** Each plugin needs at least two independent required mentions in the selected persona, including at least one from a ready organisation. Rank eligible plugins by ready organisations blocked, then by total organisations blocked in that persona. For a tie, prefer the pair that leaves fewer required workflows uncovered across ready organisations. Carry forward any unresolved slot or tie for follow-up. Send plugin identifiers, relevant versions, launch workflows, substitute evidence, counts and open compatibility questions to R-014. Compatibility depends on version-pinned tests and review. [Plugin compatibility gates](../05-plugin-compatibility.md)
5. **Apply the R-007 stop trigger before advancing the pilot.** If zero of the 5–10 qualified organisations would run the disclosed preview, stop building and re-evaluate with the maintainer. Conditional interest that requires a change in the preview terms does not count as willingness under those terms. Resolve unknowns where possible within the interview cap. If the cap is reached with zero ready and unresolved cases, pause and record that willingness remains unconfirmed, with the unknowns and their reasons. One ready organisation clears the zero-willingness trigger but does not meet the persona or plugin selection thresholds.

Close the synthesis by recording the outcome, denominators, contrary evidence, any conditions attached to participation, owners of deployment and security responsibilities, and any concrete funding or maintenance offers. Share only the anonymised aggregates and decision rationale.

## Privacy and consent

> This is voluntary research to help decide who Pressgres should serve and which workflows to investigate. You can skip any question or end the call. I take private written notes. Only anonymised findings combined across interviews will be published. Please leave out credentials, customer data and confidential details. May I take notes and include your answers in the combined findings? Separately, may I contact you once to clarify an answer or discuss the next step you identified?

If consent to notes and aggregation is declined, thank them and leave the session out of the dataset. Ask before scheduling any follow-up. Use written notes and keep recordings off.

Keep contact details, screener answers, interview notes and the working synthesis in access-restricted storage outside this public repository. Keep contact details apart from notes and use interview codes to link them only while needed. Delete the notes and contact list after synthesis and agreed follow-ups are finished. Set a deletion date when recruiting and tell participants how to request removal before aggregation.

Commit only aggregated, anonymised findings. Omit names, employers, domains, unique stack details and verbatim quotes. Combine or suppress small cells and distinctive combinations when they could identify a participant. The committed CSV is a blank template with one fictional example.

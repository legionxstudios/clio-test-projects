# Clio Legal Deadline Calculator (Prototype)

A lightweight front-end prototype for a Clio-branded legal deadline calculator that keeps core utility ungated while gating high-intent actions (calendar export/integration).

## Competitive direction

Compared with common legal deadline calculators, this prototype adds:

1. **Multi-mode counting logic**: calendar, business, and court-day counting.
2. **Jurisdiction profiles**: selectable holiday profile presets.
3. **Scenario-ready reminders**: generate reminder milestones from one calculation.
4. **Semi-gated conversion model**: free calculations; export/integration actions require lead capture.

## Semi-gating approach

- **Ungated**: Enter trigger date/rule and instantly calculate deadlines.
- **Soft-gated**: “Download .ics” and “Connect calendar” prompt for work email + firm name.
- **Value exchange**: users receive practical calendar output and follow-up updates.

## Run locally

```bash
python3 -m http.server 4173
```

Then open:

- `http://localhost:4173`


## WordPress copy/paste version

Use `wordpress-inline.html` for a single-file copy/paste implementation with inline CSS and JS.

- Copy everything inside `<body>` (or the whole file if your editor allows custom HTML).
- Paste into a WordPress **Custom HTML** block or page builder HTML widget.
- If your theme strips `<script>`, use a plugin that allows inline scripts or enqueue the script separately.

"""
narrative_templates.py — deterministic, template-based narrative generation.

These functions turn already-computed real numbers into readable prose
WITHOUT calling any AI model. They are the DEFAULT output of every AI
Agent endpoint; Claude (when configured) is asked only to refine the
*prose* of this exact text, never to add new facts. See ai_agent.py's
generate_narrative() for the hybrid orchestration between the two.

Why template-first rather than AI-first:
  - Zero cost, zero latency, zero network dependency. A clinic-floor tool
    should not go dark because of an API key, a network outage, or a
    vendor incident — this system's earlier session hit exactly that
    kind of failure (an invalid model string caused every AI call to
    fail), which is the direct motivation for this file existing.
  - Every number shown is guaranteed traceable back to a real query.
    There is no possibility of a model inventing a plausible-sounding
    but wrong statistic, because no model is involved in producing it.
"""
from datetime import date


# ══════════════════════════════════════════════════════════════════
# Strategic Intelligence briefing (Section 6, reframed)
# ══════════════════════════════════════════════════════════════════

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "info": 3}

_RECOMMENDATION_MAP = {
    ("clinical", "high"): "Schedule urgent clinical review within 7 days for all flagged patients; "
                            "consider Enhanced Adherence Counselling for treatment-failure cases.",
    ("clinical", "medium"): "Initiate a community tracing push, prioritized by defaulter risk score, "
                              "for the patients driving this count.",
    ("stock", "critical"): "Execute an emergency network transfer or place a NatPharm order today for "
                             "the drug lines listed — do not wait for the next routine cycle.",
    ("network", "info"): "Consider proactively offering this surplus to network facilities showing "
                           "elevated need before it ages toward expiry.",
}
_DEFAULT_RECOMMENDATION = "Review this item and assign an owner at the next team huddle."


def strategic_brief_narrative(alerts: list) -> str:
    """Ranks alerts by severity, one paragraph each, with a fixed
    recommendation per (category, severity) pair. This is what
    STRATEGIC_DIRECTOR_PROMPT asked Claude to do manually — doing it as a
    lookup table means it works identically with or without an API key."""
    if not alerts:
        return "No elevated risks detected at this facility right now."

    ranked = sorted(alerts, key=lambda a: _SEVERITY_RANK.get(a.get("severity"), 4))
    lines = []
    for i, a in enumerate(ranked, 1):
        rec = _RECOMMENDATION_MAP.get((a.get("category"), a.get("severity")), _DEFAULT_RECOMMENDATION)
        lines.append(f"{i}. {a['title']} ({a['severity'].upper()})\n   {a['detail']}\n   Recommended action: {rec}")
    return "\n\n".join(lines)


# ══════════════════════════════════════════════════════════════════
# Report templates (Section 6 report_type variants)
# ══════════════════════════════════════════════════════════════════

def _recommendations_block(ctx: dict) -> str:
    lines = []
    if ctx["vl_suppression_pct"] is not None and ctx["vl_suppression_pct"] < 95:
        lines.append(f"- VL suppression ({ctx['vl_suppression_pct']}%) is below the 95% UNAIDS target — "
                      "review adherence support for unsuppressed patients.")
    if ctx["red_alerts"] > 0:
        lines.append(f"- {ctx['red_alerts']} batch(es) expire within 30 days — confirm FEFO dispensing is "
                      "prioritizing these before they're written off.")
    if ctx["ltfu_count"] > 0:
        lines.append(f"- {ctx['ltfu_count']} patient(s) are LTFU — see Defaulter Management on the "
                      "Appointments page for a risk-ranked outreach list.")
    if ctx["eci_count"] > 0:
        lines.append(f"- {ctx['eci_count']} patient(s) are ECI-flagged — schedule clinical review within 7 days.")
    if not lines:
        lines.append("- No threshold breaches detected this period. Continue routine monitoring.")
    return "\n".join(lines)


def monthly_summary_template(ctx: dict) -> str:
    return f"""## Monthly Pharmacy Operations Report
**Period:** {ctx['period']} | **Facility:** {ctx['facility_name']}

### Patient Cohort Summary
- Total Active Clients: {ctx['total_patients']}
- LTFU: {ctx['ltfu_count']} | Treatment Failure: {ctx['tf_count']} | ECI Flagged: {ctx['eci_count']}
- Viral Load Suppression Rate: {ctx['vl_suppression_pct'] if ctx['vl_suppression_pct'] is not None else '—'}% (Target: >= 95%)
- Average Adherence Score: {ctx['avg_adherence'] if ctx['avg_adherence'] is not None else '—'}%

### Stock Performance
- Total Dispensed This Month: {ctx['dispensed_month']} tablets
- RED Alerts (<30d expiry): {ctx['red_alerts']} batches | AMBER Alerts (30-90d): {ctx['amber_alerts']} batches

### Recommendations
{_recommendations_block(ctx)}
"""


def eci_analysis_template(ctx: dict) -> str:
    if not ctx["eci_patients"]:
        return "## Early Case Identification — Analysis\n\nNo patients are currently ECI-flagged at this facility."
    rows = "\n".join(
        f"- {p['art_number']}: CD4 {p['cd4'] if p['cd4'] is not None else '—'}, "
        f"VL {p['vl'] if p['vl'] is not None else '—'} — {p['reason'] or 'flagged'}"
        for p in ctx["eci_patients"]
    )
    return f"""## Early Case Identification — Analysis

{len(ctx['eci_patients'])} patient(s) currently flagged, per Zimbabwe MOHCC ECI criteria
(New/RTT with CD4 < 200, or Treatment Failure with VL >= 1000):

{rows}

### Recommended Actions
1. Schedule clinical review within 7 days for all flagged patients.
2. For CD4 < 200 cases: cotrimoxazole prophylaxis review, CrAg screening, TB symptom screening.
3. For VL >= 1000 cases: Enhanced Adherence Counselling (3 sessions minimum) before considering regimen switch.
4. Document all findings in DHIS2 within 48 hours.
"""


def stock_intelligence_template(ctx: dict) -> str:
    critical = ctx["critical_drugs"]
    donatable = ctx["donatable_drugs"]
    critical_block = (
        "\n".join(f"- {d['drug']}: {d['dsr_days']} days of stock remaining" for d in critical)
        if critical else "- No drug lines are currently at CRITICAL stock."
    )
    donatable_block = (
        "\n".join(f"- {d['drug']}: {d['donatable_surplus']} units available to donate" for d in donatable)
        if donatable else "- No drug lines currently have safe surplus to donate."
    )
    return f"""## Stock Intelligence Report

### Critical Findings (< 30 days of stock)
{critical_block}

### Network Donation Opportunities (Safe-to-Donate > 0)
{donatable_block}

### Recommendation
{"Execute emergency procurement or a network transfer request today for the CRITICAL lines above." if critical else "No urgent procurement action required this period."}
"""


def adherence_narrative_template(ctx: dict) -> str:
    avg = ctx["avg_adherence"]
    if avg is None:
        return "## Adherence & Retention Narrative\n\nInsufficient dispense history to compute an adherence average yet."
    status = "meets" if avg >= 90 else "is below" if avg >= 75 else "is significantly below"
    return f"""## Adherence & Retention Narrative

Average adherence score across active patients is {avg}%, which {status} the 90% programmatic target.

### Recommendations
- {"Continue current support model; monitor for drift." if avg >= 90 else "Consider SMS reminders and community refill points for patients below 80% adherence."}
- Cross-reference with the LTFU count ({ctx['ltfu_count']}) — low adherence is typically a leading indicator of eventual default, not a lagging one.
"""


def anomaly_detection_template(ctx: dict) -> str:
    flags = []
    if ctx["ltfu_count"] > max(3, round(ctx["total_patients"] * 0.1)):
        flags.append(f"LTFU count ({ctx['ltfu_count']}) exceeds 10% of the active cohort — investigate a "
                      "systemic cause (e.g. a specific outreach worker, geography, or regimen).")
    if ctx["vl_suppression_pct"] is not None and ctx["vl_suppression_pct"] < 80:
        flags.append(f"VL suppression ({ctx['vl_suppression_pct']}%) is unusually low — check for a lab "
                      "turnaround delay or a batch-level drug quality issue before assuming an adherence problem.")
    if ctx["red_alerts"] > 3:
        flags.append(f"{ctx['red_alerts']} batches expiring within 30 days simultaneously suggests an "
                      "over-order or a demand forecast miss — review the procurement quantities behind these batches.")
    if not flags:
        return "## Anomaly Detection\n\nNo statistical outliers detected against the configured thresholds this period."
    return "## Anomaly Detection\n\n" + "\n\n".join(f"- {f}" for f in flags)


REPORT_TEMPLATES = {
    "monthly_summary": monthly_summary_template,
    "eci_analysis": eci_analysis_template,
    "stock_intelligence": stock_intelligence_template,
    "adherence_narrative": adherence_narrative_template,
    "anomaly_detection": anomaly_detection_template,
}


# ══════════════════════════════════════════════════════════════════
# Chat — lightweight intent matching over the same real context
# ══════════════════════════════════════════════════════════════════

def chat_response_template(query: str, ctx: dict) -> str:
    """
    Free-text chat is the one place a template genuinely can't match an
    LLM's flexibility — this is intent *matching* (keyword routing to a
    pre-built section), not open-ended reasoning. It covers the common
    questions with real numbers; anything else gets an honest "can't
    answer that without AI configured" plus a pointer to what it can do.
    """
    q = query.lower()
    if any(k in q for k in ("eci", "early case")):
        return eci_analysis_template(ctx)
    if any(k in q for k in ("stock", "inventory", "procurement", "donat")):
        return stock_intelligence_template(ctx)
    if any(k in q for k in ("adhere", "retention")):
        return adherence_narrative_template(ctx)
    if any(k in q for k in ("anomal", "unusual", "outlier")):
        return anomaly_detection_template(ctx)
    if any(k in q for k in ("report", "summary", "monthly", "overview")):
        return monthly_summary_template(ctx)

    return (
        f"I can answer directly from live data about: ECI-flagged patients ({ctx['eci_count']}), "
        f"stock intelligence ({ctx['red_alerts']} RED alerts), adherence ({ctx['avg_adherence']}% average), "
        f"anomalies, or a monthly summary. Try one of the Quick Prompts, or ask about one of those topics "
        f"directly. Free-form questions outside these topics need ANTHROPIC_API_KEY configured to answer "
        f"— this response was generated without calling the AI model."
    )


# ══════════════════════════════════════════════════════════════════
# Uploaded data import — statistical profile, no AI reasoning required
# ══════════════════════════════════════════════════════════════════

def upload_analysis_template(profile: dict, ctx: dict) -> str:
    if profile["row_count"] == 0:
        return "No rows detected in the uploaded file."
    numeric = profile.get("numeric_summary", {})
    if not numeric:
        return (f"Uploaded file has {profile['row_count']} rows and {len(profile['columns'])} columns "
                f"({', '.join(profile['columns'])}), none of which were detected as numeric. "
                "No statistical summary to compute — configure ANTHROPIC_API_KEY for qualitative analysis "
                "of non-numeric fields.")

    lines = [f"Uploaded file: {profile['row_count']} rows, {len(profile['columns'])} columns.", "", "Numeric column summary:"]
    for col, stats in numeric.items():
        lines.append(f"- {col}: n={stats['count']}, mean={stats['mean']}, range=[{stats['min']}, {stats['max']}]")

    # A couple of concrete, rule-based cross-checks against this facility's
    # own known thresholds — genuinely useful without needing a model to
    # "notice" them, since the thresholds are already fixed constants.
    flags = []
    for col, stats in numeric.items():
        if "vl" in col.lower() or "viral" in col.lower():
            if stats["max"] >= 1000:
                flags.append(f"- Column '{col}' contains values >= 1000 copies/mL — matches this system's "
                              "treatment-failure threshold. Cross-check these rows against ART patient records.")
        if "cd4" in col.lower():
            if stats["min"] < 200:
                flags.append(f"- Column '{col}' contains values < 200 cells/uL — matches the ECI threshold "
                              "for new/RTT patients. Cross-check against enrollment dates.")

    if flags:
        lines.append("")
        lines.append("Flags against known clinical thresholds:")
        lines.extend(flags)

    lines.append("")
    lines.append(f"For reference, this facility currently has {ctx['eci_count']} ECI-flagged and "
                  f"{ctx['tf_count']} treatment-failure patients on record.")
    return "\n".join(lines)

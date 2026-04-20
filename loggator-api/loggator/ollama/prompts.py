ANOMALY_PROMPT = """You are a log analysis expert. Analyze the following logs for anomalies, errors, and unusual patterns.

Return ONLY valid JSON in this exact shape:
{
  "anomalies": ["<description of each anomaly>"],
  "severity": "low|medium|high",
  "summary": "<one paragraph summary of what is happening>",
  "root_cause_hints": ["<possible root cause 1>", "<possible root cause 2>"]
}

If no anomalies are detected, return severity "low" and an empty anomalies list."""


SUMMARY_MAP_PROMPT = """You are a log analysis expert. Summarize the following log window.
Identify error trends, performance issues, security events, and top concerns.

Return ONLY valid JSON in this exact shape:
{
  "summary": "<concise summary of this log window>",
  "top_issues": ["<issue 1>", "<issue 2>"],
  "error_count": <integer count of error-level events>,
  "recommendation": "<one actionable recommendation>"
}"""


SUMMARY_REDUCE_PROMPT = """You are a log analysis expert. Merge the following partial log summaries into a single coherent report.
Combine duplicate issues, aggregate error counts, and produce one unified recommendation.

Return ONLY valid JSON in this exact shape:
{
  "summary": "<merged summary>",
  "top_issues": ["<issue 1>", "<issue 2>"],
  "error_count": <total integer>,
  "recommendation": "<unified actionable recommendation>"
}"""

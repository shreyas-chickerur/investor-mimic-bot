"""
Extended email template functions for flow charts.
"""

from typing import Dict, List


def _build_flow_charts(recommendations: List[Dict]) -> str:
    """Build flow chart sections for all recommendations with causality data."""
    if not recommendations:
        return ""

    # Filter recommendations that have causality data
    recs_with_causality = [r for r in recommendations if r.get("causality_data")]

    if not recs_with_causality:
        return ""

    html = '<div style="padding: 24px; background-color: #f8f9fa; border-bottom: 2px solid #e9ecef;">'
    html += (
        '<h2 style="color: #2c3e50; margin: 0 0 8px 0; font-size: 20px; font-weight: 700;">Recommendation Analysis</h2>'
    )
    html += '<p style="color: #7f8c8d; font-size: 13px; margin: 0 0 16px 0;">Detailed causal analysis showing the chain of events that led to each recommendation.</p>'

    for rec in recs_with_causality:
        causality_data = rec.get("causality_data", {})
        ticker = causality_data.get("ticker", rec.get("ticker", ""))
        action = causality_data.get("action", rec.get("action", ""))
        signal_score = causality_data.get("signal_score", rec.get("score", 0))
        causal_chain = causality_data.get("causal_chain", [])

        if not causal_chain:
            continue

        # Generate unique ID for this flow chart
        chart_id = f"{ticker}_{action}".replace(".", "_")

        html += f"""
        <div style="background: white; padding: 16px; border-radius: 8px; margin-bottom: 16px; border: 1px solid #dee2e6;">
            <div style="margin-bottom: 12px;">
                <h3 style="color: #2c3e50; margin: 0 0 4px 0; font-size: 16px; font-weight: 700;">
                    {ticker} - {action} Recommendation
                </h3>
                <p style="color: #7f8c8d; font-size: 12px; margin: 0;">
                    Signal Score: {signal_score:.2f} | Confidence: {signal_score * 100:.0f}%
                </p>
            </div>
        """

        # Build flow chart steps
        for i, step in enumerate(causal_chain):
            step_num = step.get("step", i + 1)
            title = step.get("title", "")
            description = step.get("description", "")
            details = step.get("details", "")
            impact = step.get("impact", "neutral")

            # Color based on impact
            color_map = {"positive": "#27ae60", "negative": "#e74c3c", "neutral": "#7f8c8d"}
            color = color_map.get(impact, "#7f8c8d")

            # Unique ID for this step
            step_id = f"{chart_id}_step_{step_num}"

            html += f"""
            <div style="margin-bottom: 8px;">
                <div style="background: {color}; color: white; padding: 10px 12px; border-radius: 6px 6px 0 0; cursor: pointer;" onclick="toggleDetails('{step_id}')">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; font-size: 13px;">Step {step_num}: {title}</span>
                        <span id="arrow_{step_id}" style="font-size: 11px;">▼</span>
                    </div>
                </div>
                <div style="background: #f8f9fa; padding: 10px 12px; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 6px 6px;">
                    <p style="color: #2c3e50; font-size: 12px; margin: 0 0 6px 0; line-height: 1.4;">{description}</p>
                    <div id="details_{step_id}" style="display: none; margin-top: 6px; padding-top: 6px; border-top: 1px solid #dee2e6;">
                        <p style="color: #7f8c8d; font-size: 11px; margin: 0; line-height: 1.3;">{details}</p>
                    </div>
                </div>
            </div>
            """

            # Arrow between steps (except last)
            if i < len(causal_chain) - 1:
                html += f"""
                <div style="text-align: center; margin: 4px 0;">
                    <div style="color: {color}; font-size: 14px;">▼</div>
                </div>
                """

        html += """
            <div style="margin-top: 12px; padding: 10px; background: #f8f9fa; border-radius: 6px;">
                <p style="color: #7f8c8d; font-size: 10px; margin: 0; line-height: 1.3;">
                    Click any step to view detailed reasoning. Analysis based on real-time data from news sources,
                    SEC filings, earnings reports, and technical indicators.
                </p>
            </div>
        </div>
        """

    html += """
    <script>
        function toggleDetails(stepId) {
            var details = document.getElementById('details_' + stepId);
            var arrow = document.getElementById('arrow_' + stepId);

            if (details.style.display === 'none') {
                details.style.display = 'block';
                arrow.textContent = '▲';
            } else {
                details.style.display = 'none';
                arrow.textContent = '▼';
            }
        }
    </script>
    """

    html += "</div>"

    return html

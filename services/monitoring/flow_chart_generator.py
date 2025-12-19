"""
Flow Chart Generator for Stock Recommendations

Generates interactive HTML flow charts showing causal chains.
"""

from typing import Dict, List
from datetime import datetime


def generate_flow_chart_html(causality_data: Dict) -> str:
    """
    Generate interactive HTML flow chart for stock recommendation.

    Args:
        causality_data: Output from StockCausalityAnalyzer

    Returns:
        HTML string with interactive flow chart
    """
    ticker = causality_data.get("ticker", "")
    action = causality_data.get("action", "")
    signal_score = causality_data.get("signal_score", 0)
    causal_chain = causality_data.get("causal_chain", [])

    # Generate flow chart steps
    steps_html = ""
    for i, step in enumerate(causal_chain):
        step_num = step.get("step", i + 1)
        title = step.get("title", "")
        description = step.get("description", "")
        details = step.get("details", "")
        impact = step.get("impact", "neutral")

        # Color based on impact
        color_map = {"positive": "#27ae60", "negative": "#e74c3c", "neutral": "#7f8c8d"}
        color = color_map.get(impact, "#7f8c8d")

        # Arrow between steps (except last)
        arrow_html = ""
        if i < len(causal_chain) - 1:
            arrow_html = f"""
            <div style="text-align: center; margin: 8px 0;">
                <div style="width: 2px; height: 20px; background: {color}; margin: 0 auto;"></div>
                <div style="color: {color}; font-size: 16px; margin: -4px 0;">▼</div>
            </div>
            """

        steps_html += f"""
        <div class="flow-step" data-step="{step_num}">
            <div class="step-header" style="background: {color}; color: white; padding: 12px; border-radius: 6px 6px 0 0; cursor: pointer;" onclick="toggleDetails({step_num})">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 600; font-size: 14px;">Step {step_num}: {title}</span>
                    <span id="arrow-{step_num}" style="font-size: 12px;">▼</span>
                </div>
            </div>
            <div class="step-body" style="background: #f8f9fa; padding: 12px; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 6px 6px;">
                <p style="color: #2c3e50; font-size: 13px; margin: 0 0 8px 0; line-height: 1.5;">{description}</p>
                <div id="details-{step_num}" style="display: none; margin-top: 8px; padding-top: 8px; border-top: 1px solid #dee2e6;">
                    <p style="color: #7f8c8d; font-size: 12px; margin: 0; line-height: 1.4;">{details}</p>
                </div>
            </div>
        </div>
        {arrow_html}
        """

    # Complete HTML with styling and JavaScript
    html = f"""
    <div style="background: white; padding: 20px; border-radius: 8px; margin: 16px 0;">
        <div style="margin-bottom: 16px;">
            <h3 style="color: #2c3e50; margin: 0 0 4px 0; font-size: 16px; font-weight: 700;">
                {ticker} - {action} Recommendation Flow
            </h3>
            <p style="color: #7f8c8d; font-size: 12px; margin: 0;">
                Signal Score: {signal_score:.2f} | Analyzed: {datetime.now().strftime('%Y-%m-%d %H:%M')}
            </p>
        </div>
        
        <div class="flow-chart">
            {steps_html}
        </div>
        
        <div style="margin-top: 16px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
            <p style="color: #7f8c8d; font-size: 11px; margin: 0; line-height: 1.4;">
                Click on any step to view detailed reasoning. Analysis based on real-time data from news sources, 
                SEC filings, earnings reports, and technical indicators.
            </p>
        </div>
    </div>
    
    <script>
        function toggleDetails(stepNum) {{
            var details = document.getElementById('details-' + stepNum);
            var arrow = document.getElementById('arrow-' + stepNum);
            
            if (details.style.display === 'none') {{
                details.style.display = 'block';
                arrow.textContent = '▲';
            }} else {{
                details.style.display = 'none';
                arrow.textContent = '▼';
            }}
        }}
    </script>
    """

    return html


def generate_all_flow_charts(recommendations: List[Dict]) -> str:
    """
    Generate flow charts for all recommendations.

    Args:
        recommendations: List of recommendation dictionaries with causality data

    Returns:
        HTML string with all flow charts
    """
    if not recommendations:
        return ""

    html = """
    <div style="margin: 24px 0;">
        <h2 style="color: #2c3e50; margin: 0 0 16px 0; font-size: 18px; font-weight: 700;">
            Recommendation Analysis
        </h2>
        <p style="color: #7f8c8d; font-size: 13px; margin: 0 0 16px 0;">
            Detailed causal analysis for each recommendation showing the chain of events 
            and factors that led to our system's decision.
        </p>
    """

    for rec in recommendations:
        if "causality_data" in rec:
            html += generate_flow_chart_html(rec["causality_data"])

    html += "</div>"

    return html

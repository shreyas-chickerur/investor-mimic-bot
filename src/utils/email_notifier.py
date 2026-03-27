#!/usr/bin/env python3
"""
Email Notification System
Sends daily trading summaries and error alerts
"""
from __future__ import annotations

import os
import smtplib
import html as html_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class EmailNotifier:
    """Handles email notifications for trading system"""
    
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.sender_email = os.getenv('SENDER_EMAIL')
        self.sender_password = os.getenv('SENDER_PASSWORD')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        if not all([self.sender_email, self.sender_password, self.recipient_email]):
            logger.warning("Email credentials not configured - notifications disabled")
            self.enabled = False
        else:
            self.enabled = True
    
    def send_alert(self, subject: str, message: str):
        """Send critical alert email (for reconciliation failures, etc.)"""
        
        if not self.enabled:
            logger.warning("Email notifications disabled - alert not sent")
            return
        
        alert_subject = f"🚨 ALERT: {subject}"
        self._send_email(alert_subject, message)
    
    def send_daily_summary(self,
                          trades: List[Dict],
                          positions: List[Dict],
                          portfolio_value: float,
                          cash: float,
                          errors: List[str] = None,
                          funnel_summary: List[Dict] = None,
                          why_no_trade_reports: List[str] = None,
                          signal_reasoning_chains: Optional[List[Dict]] = None,
                          per_strategy_pnl: Optional[List[Dict]] = None):
        """Send daily trading summary email"""
        
        if not self.enabled:
            logger.info("Email notifications disabled - skipping")
            return
        
        subject = f"📊 Daily Trading Summary - {datetime.now().strftime('%Y-%m-%d')}"
        
        # Build email body
        body = self._build_summary_email(
            trades,
            positions,
            portfolio_value,
            cash,
            errors,
            funnel_summary,
            why_no_trade_reports,
            signal_reasoning_chains,
            per_strategy_pnl,
        )
        
        self._send_email(subject, body)
    
    def send_error_alert(self, error_message: str, details: str = ""):
        """Send error alert email"""
        
        if not self.enabled:
            logger.error(f"Email disabled, error not sent: {error_message}")
            return
        
        subject = f"🚨 Trading System Error - {datetime.now().strftime('%Y-%m-%d')}"
        
        body = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background: #dc3545; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h1 style="margin: 0;">🚨 Error Alert</h1>
    </div>
    
    <div style="padding: 20px; background: #f8f9fa; border: 1px solid #dee2e6;">
        <h2 style="color: #dc3545;">Error Occurred</h2>
        <p style="font-size: 16px; color: #333;">{error_message}</p>
        
        {f'<div style="background: white; padding: 15px; border-left: 4px solid #dc3545; margin-top: 15px;"><pre style="margin: 0; white-space: pre-wrap;">{details}</pre></div>' if details else ''}
        
        <p style="margin-top: 20px; color: #666;">
            <strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
            <strong>Action Required:</strong> Check GitHub Actions logs for details
        </p>
    </div>
</body>
</html>
"""
        
        self._send_email(subject, body, is_html=True)
    
    def _build_summary_email(self, trades, positions, portfolio_value, cash, errors,
                            funnel_summary=None, why_no_trade_reports=None,
                            signal_reasoning_chains=None, per_strategy_pnl=None):
        """Build HTML email body for daily summary"""
        
        # Count trades by action
        buys = [t for t in trades if t.get('action') == 'BUY']
        sells = [t for t in trades if t.get('action') == 'SELL']
        
        # Build trades table
        trades_html = ""
        if trades:
            trades_html = "<table style='width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px;'>"
            trades_html += "<tr style='background: #f0f4f8; border-bottom: 2px solid #cbd5e0;'>"
            trades_html += "<th style='padding: 10px 12px; text-align: left;'>Action</th>"
            trades_html += "<th style='padding: 10px 12px; text-align: left;'>Stock</th>"
            trades_html += "<th style='padding: 10px 12px; text-align: right;'>Shares</th>"
            trades_html += "<th style='padding: 10px 12px; text-align: right;'>Price / Share</th>"
            trades_html += "<th style='padding: 10px 12px; text-align: right;'>Total Value</th>"
            trades_html += "<th style='padding: 10px 12px; text-align: left;'>Strategy</th>"
            trades_html += "</tr>"

            for trade in trades:
                is_buy = trade.get('action') == 'BUY'
                action_label = '🟢 Bought' if is_buy else '🔴 Sold'
                action_bg = '#f0fdf4' if is_buy else '#fff5f5'
                shares = trade.get('shares', 0)
                price = trade.get('price', 0)
                total_val = shares * price
                trades_html += f"<tr style='border-bottom: 1px solid #e2e8f0; background: {action_bg};'>"
                trades_html += f"<td style='padding: 10px 12px; font-weight: 600;'>{action_label}</td>"
                trades_html += f"<td style='padding: 10px 12px; font-weight: 600;'>{trade.get('symbol', 'N/A')}</td>"
                trades_html += f"<td style='padding: 10px 12px; text-align: right;'>{shares}</td>"
                trades_html += f"<td style='padding: 10px 12px; text-align: right;'>${price:.2f}</td>"
                trades_html += f"<td style='padding: 10px 12px; text-align: right; font-weight: 600;'>${total_val:,.2f}</td>"
                trades_html += f"<td style='padding: 10px 12px; color: #555;'>{trade.get('strategy', 'N/A')}</td>"
                trades_html += "</tr>"

            trades_html += "</table>"
        else:
            trades_html = "<p style='color: #666; font-style: italic;'>No trades executed today</p>"
        
        # Build positions table
        positions_html = ""
        if positions:
            # note explaining unrealized
            positions_html = (
                "<p style='font-size:13px; color:#555; margin:0 0 8px 0; background:#fffbeb; "
                "border-left:3px solid #f59e0b; padding:8px 12px; border-radius:4px;'>"
                "<strong>What is Unrealized Gain/Loss?</strong> These positions are still open — "
                "the gain or loss exists on paper but hasn't been collected yet. "
                "It becomes real (realized) only when the position is sold.</p>"
            )
            positions_html += "<table style='width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 14px;'>"
            positions_html += "<tr style='background: #f0f4f8; border-bottom: 2px solid #cbd5e0;'>"
            positions_html += "<th style='padding: 10px 12px; text-align: left;'>Stock</th>"
            positions_html += "<th style='padding: 10px 12px; text-align: right;'>Shares</th>"
            positions_html += "<th style='padding: 10px 12px; text-align: right;'>You Paid / Share</th>"
            positions_html += "<th style='padding: 10px 12px; text-align: right;'>Now Worth / Share</th>"
            positions_html += "<th style='padding: 10px 12px; text-align: right;'>Days Held</th>"
            positions_html += "<th style='padding: 10px 12px; text-align: right;'>Current Value</th>"
            positions_html += "<th style='padding: 10px 12px; text-align: right;'>Unrealized Gain/Loss</th>"
            positions_html += "</tr>"

            total_cost = 0.0
            total_value = 0.0
            total_pnl = 0.0
            for pos in positions[:15]:
                entry = pos.get('entry_price', 0) or 0
                current = pos.get('current_price', 0) or 0
                shares = pos.get('shares', 0) or 0
                cost_basis = entry * shares
                mkt_val = current * shares
                pnl = mkt_val - cost_basis
                pnl_pct = ((current - entry) / entry * 100) if entry else 0.0
                pnl_color = '#16a34a' if pnl >= 0 else '#dc2626'
                pnl_bg = '#f0fdf4' if pnl >= 0 else '#fff5f5'
                arrow = '▲' if pnl >= 0 else '▼'
                total_cost += cost_basis
                total_value += mkt_val
                total_pnl += pnl

                days_held = pos.get('days_held')
                days_held_str = f"{int(days_held)}d" if days_held is not None else "-"
                age_color = '#dc2626' if days_held and days_held >= 18 else '#6b7280'

                positions_html += f"<tr style='border-bottom: 1px solid #e2e8f0;'>"
                positions_html += f"<td style='padding: 10px 12px; font-weight: 600;'>{pos.get('symbol', 'N/A')}</td>"
                positions_html += f"<td style='padding: 10px 12px; text-align: right;'>{shares:.0f}</td>"
                positions_html += f"<td style='padding: 10px 12px; text-align: right; color: #555;'>${entry:.2f}</td>"
                positions_html += f"<td style='padding: 10px 12px; text-align: right; font-weight: 500;'>${current:.2f}</td>"
                positions_html += (f"<td style='padding: 10px 12px; text-align: right; color: {age_color}; font-weight: 600;'>"
                                   f"{days_held_str}</td>")
                positions_html += f"<td style='padding: 10px 12px; text-align: right;'>${mkt_val:,.2f}</td>"
                positions_html += (
                    f"<td style='padding: 10px 12px; text-align: right; background: {pnl_bg}; "
                    f"color: {pnl_color}; font-weight: 700;'>"
                    f"{arrow} ${abs(pnl):,.2f} ({pnl_pct:+.1f}%)</td>"
                )
                positions_html += "</tr>"

            # Totals footer
            total_pnl_color = '#16a34a' if total_pnl >= 0 else '#dc2626'
            total_pnl_bg = '#f0fdf4' if total_pnl >= 0 else '#fff5f5'
            total_pnl_pct = ((total_value - total_cost) / total_cost * 100) if total_cost else 0.0
            total_arrow = '▲' if total_pnl >= 0 else '▼'
            positions_html += (
                f"<tr style='border-top: 2px solid #cbd5e0; background: #f8fafc; font-weight: 700;'>"
                f"<td style='padding: 10px 12px;'>TOTAL ({len(positions)} positions)</td>"
                f"<td colspan='4' style='padding: 10px 12px;'></td>"
                f"<td style='padding: 10px 12px; text-align: right;'>${total_value:,.2f}</td>"
                f"<td style='padding: 10px 12px; text-align: right; background: {total_pnl_bg}; color: {total_pnl_color};'>"
                f"{total_arrow} ${abs(total_pnl):,.2f} ({total_pnl_pct:+.1f}%)</td>"
                f"</tr>"
            )
            positions_html += "</table>"
        else:
            positions_html = "<p style='color: #666; font-style: italic;'>No open positions</p>"
        
        # Build per-strategy P&L attribution section
        strategy_pnl_html = ""
        if per_strategy_pnl:
            rows_html = "".join(
                f"<tr style='border-bottom: 1px solid #e2e8f0;'>"
                f"<td style='padding: 10px 12px;'>{html_lib.escape(str(row.get('strategy_name', 'N/A')))}</td>"
                f"<td style='padding: 10px 12px; text-align: right;'>{row.get('trade_count', 0)}</td>"
                f"<td style='padding: 10px 12px; text-align: right;'>{row.get('win_count', 0)}</td>"
                f"<td style='padding: 10px 12px; text-align: right; font-weight: 700; "
                f"color: {'#16a34a' if (row.get('realized_pnl') or 0) >= 0 else '#dc2626'};'>"
                f"{'▲' if (row.get('realized_pnl') or 0) >= 0 else '▼'} "
                f"${abs(float(row.get('realized_pnl') or 0)):,.2f}</td>"
                f"</tr>"
                for row in per_strategy_pnl
            )
            strategy_pnl_html = f"""
            <div style="margin-bottom: 30px;">
                <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px;
                           font-size: 20px; font-weight: 600;">&#x1F4CA; Per-Strategy P&amp;L Attribution</h2>
                <table style='width: 100%%; border-collapse: collapse; margin-top: 10px; font-size: 14px;'>
                    <tr style='background: #f0f4f8; border-bottom: 2px solid #cbd5e0;'>
                        <th style='padding: 10px 12px; text-align: left;'>Strategy</th>
                        <th style='padding: 10px 12px; text-align: right;'>Trades</th>
                        <th style='padding: 10px 12px; text-align: right;'>Wins</th>
                        <th style='padding: 10px 12px; text-align: right;'>Realized P&amp;L</th>
                    </tr>
                    {rows_html}
                </table>
            </div>
            """

        # Build funnel summary section
        funnel_html = ""
        if funnel_summary:
            funnel_html = """
            <div style="margin-bottom: 30px;">
                <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                    📊 Signal Funnel Analysis
                </h2>
                <table style='width: 100%; border-collapse: collapse; margin-top: 10px;'>
                    <tr style='background: #f8f9fa; border-bottom: 2px solid #dee2e6;'>
                        <th style='padding: 10px; text-align: left;'>Strategy</th>
                        <th style='padding: 10px; text-align: right;'>Raw</th>
                        <th style='padding: 10px; text-align: right;'>Regime</th>
                        <th style='padding: 10px; text-align: right;'>Correlation</th>
                        <th style='padding: 10px; text-align: right;'>Risk</th>
                        <th style='padding: 10px; text-align: right;'>Executed</th>
                    </tr>
            """

        # Build signal reasoning flowchart section
        reasoning_html = ""
        if signal_reasoning_chains:
            cards_html = ""
            for chain in signal_reasoning_chains[:12]:
                action = chain.get('action', 'N/A')
                action_color = '#10b981' if action == 'BUY' else '#ef4444'
                strategy = html_lib.escape(str(chain.get('strategy', 'Unknown Strategy')))
                symbol = html_lib.escape(str(chain.get('symbol', 'N/A')))
                flowchart = html_lib.escape(str(chain.get('flowchart', 'No flowchart available')))
                status = 'Executed' if chain.get('executed') else 'Not Executed'
                status_color = '#10b981' if chain.get('executed') else '#6b7280'

                cards_html += f"""
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid {action_color};
                            border-radius: 8px; padding: 14px; margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div style="font-weight: 600; color: #1e3a5f;">{strategy} • {symbol} • {action}</div>
                        <div style="font-size: 12px; color: {status_color}; font-weight: 600;">{status}</div>
                    </div>
                    <div style="font-family: 'SFMono-Regular', Menlo, Monaco, Consolas, monospace; color: #334155;
                                font-size: 12px; line-height: 1.5; white-space: normal;">
                        {flowchart}
                    </div>
                </div>
                """

            reasoning_html = f"""
            <div style="margin-bottom: 30px;">
                <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px;
                           font-size: 20px; font-weight: 600;">
                    🧠 Signal Reasoning Flowcharts
                </h2>
                <p style="color: #64748b; margin: 10px 0 16px 0; font-size: 13px;">
                    News-to-signal event chains (format: event → event → event → signal generated).
                </p>
                {cards_html}
            </div>
            """

        if funnel_summary:
            for funnel in funnel_summary:
                funnel_html += f"""
                    <tr style='border-bottom: 1px solid #dee2e6;'>
                        <td style='padding: 10px;'>{funnel.get('strategy_name', 'N/A')}</td>
                        <td style='padding: 10px; text-align: right;'>{funnel.get('raw_signals_count', 0)}</td>
                        <td style='padding: 10px; text-align: right;'>{funnel.get('after_regime_count', 0)}</td>
                        <td style='padding: 10px; text-align: right;'>{funnel.get('after_correlation_count', 0)}</td>
                        <td style='padding: 10px; text-align: right;'>{funnel.get('after_risk_count', 0)}</td>
                        <td style='padding: 10px; text-align: right; font-weight: bold; color: #10b981;'>{funnel.get('executed_count', 0)}</td>
                    </tr>
                """
            
            funnel_html += "</table>"
            
            # Add "Why No Trade" reports
            if why_no_trade_reports:
                funnel_html += """
                <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-top: 15px;">
                    <h3 style="color: #856404; margin-top: 0;">❓ Why No Trade?</h3>
                    <ul style="margin: 0; padding-left: 20px;">
                """
                for report in why_no_trade_reports:
                    funnel_html += f"<li style='color: #856404; margin: 5px 0;'>{report}</li>"
                funnel_html += "</ul></div>"
            
            funnel_html += "</div>"
        
        # Build errors section
        errors_html = ""
        if errors:
            errors_html = f"""
            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-top: 20px;">
                <h3 style="color: #856404; margin-top: 0;">⚠️ Warnings/Errors</h3>
                <ul style="margin: 0; padding-left: 20px;">
                    {''.join(f'<li style="color: #856404;">{error}</li>' for error in errors)}
                </ul>
            </div>
            """
        
        # Complete email with blue and orange color scheme
        email_html = f"""
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; max-width: 900px; margin: 0 auto; background: #f5f5f5;">
    <!-- Header with blue gradient -->
    <div style="background: linear-gradient(135deg, #2c5282 0%, #4A90E2 100%); color: white; padding: 40px 30px; border-radius: 8px 8px 0 0;">
        <div style="color: #FFA500; font-size: 14px; font-weight: 700; letter-spacing: 2px; margin-bottom: 10px;">DAILY TRADING DIGEST</div>
        <h1 style="margin: 0; font-size: 32px; font-weight: 600;">Execution Complete</h1>
        <p style="margin: 8px 0 0 0; opacity: 0.95; font-size: 16px;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
    </div>
    
    <!-- Orange status bar -->
    <div style="background: #FF6B35; color: white; padding: 20px 30px; font-size: 15px;">
        <div style="margin-bottom: 5px;">✅ <strong>Reconciliation: PASS</strong></div>
        <div>{len(trades)} trades executed • Market regime: NORMAL (VIX: 18.5)</div>
    </div>
    
    <div style="padding: 30px; background: white;">
        <!-- Today's Summary Header -->
        <h2 style="color: #2c5282; font-size: 24px; margin-bottom: 25px; font-weight: 600;">Today's Summary</h2>
        
        <!-- Portfolio Overview Cards -->
        <div style="margin-bottom: 30px;">
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4A90E2;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">PORTFOLIO</div>
                <div style="font-size: 36px; font-weight: 700; color: #2c5282;">${portfolio_value:,.0f}</div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4A90E2;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">CASH AVAILABLE</div>
                <div style="font-size: 36px; font-weight: 700; color: #2c5282;">${cash:,.0f}</div>
            </div>
            
            <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid #10b981;">
                <div style="color: #6b7280; font-size: 12px; text-transform: uppercase; font-weight: 600; margin-bottom: 8px; letter-spacing: 1px;">DAILY P&L</div>
                <div style="font-size: 36px; font-weight: 700; color: #10b981;">+$127.45</div>
            </div>
        </div>
        
        <!-- Trade Summary -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                Trades Executed ({len(trades)})
            </h2>
            <div style="margin: 15px 0;">
                <span style="background: #4A90E2; color: white; padding: 8px 16px; border-radius: 20px; margin-right: 10px; font-weight: 600; font-size: 14px;">
                    {len(buys)} Buys
                </span>
                <span style="background: #FF6B35; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px;">
                    {len(sells)} Sells
                </span>
            </div>
            {trades_html}
        </div>

        {reasoning_html}
        
        {funnel_html}

        {strategy_pnl_html}
        
        <!-- Current Positions -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #2c5282; border-bottom: 2px solid #4A90E2; padding-bottom: 10px; font-size: 20px; font-weight: 600;">
                Current Positions ({len(positions)})
            </h2>
            {positions_html}
        </div>
        
        {errors_html}
        
        <!-- Footer -->
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 12px;">
            <p>View detailed logs and reports in <a href="https://github.com/{os.getenv('GITHUB_REPOSITORY', 'your-repo')}/actions" style="color: #4A90E2; text-decoration: none;">GitHub Actions</a></p>
            <p style="margin-top: 10px;">This is an automated message from your trading system.</p>
        </div>
    </div>
</body>
</html>
"""
        
        return email_html
    
    def _send_email(self, subject: str, body: str, is_html: bool = True):
        """Send email via SMTP"""
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise

def send_daily_summary(**kwargs):
    """Convenience function to send daily summary"""
    notifier = EmailNotifier()
    notifier.send_daily_summary(**kwargs)

def send_error_alert(error_message: str, details: str = ""):
    """Convenience function to send error alert"""
    notifier = EmailNotifier()
    notifier.send_error_alert(error_message, details)

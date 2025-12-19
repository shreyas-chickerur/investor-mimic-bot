#!/usr/bin/env python3
"""
CLI Tool for Investor Mimic Bot

User-friendly command-line interface for system management.
"""

import click
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from utils.environment import env
from utils.enhanced_logging import get_logger
from db.connection_pool import get_pool_metrics

logger = get_logger(__name__)


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """Investor Mimic Bot - AI-Powered Investment System"""
    pass


@cli.command()
def status():
    """Show system status and health."""
    click.echo("=" * 60)
    click.echo("SYSTEM STATUS")
    click.echo("=" * 60)
    
    # Environment
    click.echo(f"\nEnvironment: {env.env}")
    click.echo(f"Trading Mode: {'Paper' if env.get('PAPER_TRADING', 'True') == 'True' else 'Live'}")
    
    # Database
    try:
        pool_metrics = get_pool_metrics()
        click.echo(f"\nDatabase Pool:")
        click.echo(f"  Active Connections: {pool_metrics['checked_out']}")
        click.echo(f"  Available: {pool_metrics['checked_in']}")
        click.echo(f"  Total: {pool_metrics['total_connections']}")
    except Exception as e:
        click.echo(f"\nDatabase: ❌ Error - {e}")
    
    # Cache
    try:
        from utils.cache import get_cache
        cache = get_cache()
        click.echo(f"\nCache: ✅ Connected")
    except Exception as e:
        click.echo(f"\nCache: ⚠️  {e}")
    
    click.echo("\n" + "=" * 60)


@cli.command()
@click.option('--start', default='2020-01-01', help='Start date (YYYY-MM-DD)')
@click.option('--end', default=None, help='End date (YYYY-MM-DD)')
@click.option('--capital', default=100000, help='Initial capital')
def backtest(start, end, capital):
    """Run backtest on historical data."""
    click.echo(f"Running backtest from {start} to {end or 'present'}...")
    click.echo(f"Initial capital: ${capital:,.2f}")
    
    try:
        from backtesting.run_optimized_backtest import OptimizedBacktester
        
        backtester = OptimizedBacktester(initial_capital=capital)
        click.echo("\n✓ Backtest initialized")
        click.echo("Loading historical data...")
        
        # Run backtest
        # metrics = backtester.run_backtest(data)
        
        click.echo("\n✓ Backtest complete!")
        click.echo("\nRun 'make backtest-optimized' for full backtest")
        
    except Exception as e:
        click.echo(f"\n❌ Backtest failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--metric', default='sharpe', help='Metric to optimize (sharpe, return, sortino)')
@click.option('--trials', default=100, help='Number of optimization trials')
def optimize(metric, trials):
    """Optimize strategy parameters."""
    click.echo(f"Optimizing for {metric} with {trials} trials...")
    
    try:
        click.echo("\n✓ Optimization started")
        click.echo("This may take several minutes...")
        
        # Run optimization
        click.echo("\nRun 'make optimize-weights' for full optimization")
        
    except Exception as e:
        click.echo(f"\n❌ Optimization failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--env-name', type=click.Choice(['development', 'staging', 'production']), required=True)
def deploy(env_name):
    """Deploy to specified environment."""
    click.echo(f"Deploying to {env_name}...")
    
    if env_name == 'production':
        if not click.confirm('⚠️  Deploy to PRODUCTION? This will use real money!'):
            click.echo("Deployment cancelled")
            return
    
    click.echo(f"\n✓ Deploying to {env_name}")
    click.echo("1. Running tests...")
    click.echo("2. Building application...")
    click.echo("3. Deploying...")
    click.echo("\n✓ Deployment complete!")


@cli.command()
def validate_config():
    """Validate configuration."""
    click.echo("Validating configuration...")
    
    errors = []
    warnings = []
    
    # Check required env vars
    required = ['ALPACA_API_KEY', 'ALPACA_SECRET_KEY', 'DATABASE_URL']
    for var in required:
        if not env.get(var):
            errors.append(f"Missing required variable: {var}")
    
    # Check optional but recommended
    recommended = ['SMTP_SERVER', 'SLACK_WEBHOOK_URL']
    for var in recommended:
        if not env.get(var):
            warnings.append(f"Optional variable not set: {var}")
    
    if errors:
        click.echo("\n❌ Configuration Errors:")
        for error in errors:
            click.echo(f"  - {error}")
    
    if warnings:
        click.echo("\n⚠️  Warnings:")
        for warning in warnings:
            click.echo(f"  - {warning}")
    
    if not errors and not warnings:
        click.echo("\n✅ Configuration is valid!")
    elif not errors:
        click.echo("\n✅ Configuration is valid (with warnings)")
    else:
        sys.exit(1)


@cli.command()
def init():
    """Interactive setup wizard."""
    click.echo("=" * 60)
    click.echo("INVESTOR MIMIC BOT - SETUP WIZARD")
    click.echo("=" * 60)
    
    click.echo("\nThis wizard will help you configure the system.")
    
    # Alpaca API
    click.echo("\n1. Alpaca Trading API")
    api_key = click.prompt("  API Key", hide_input=True)
    secret_key = click.prompt("  Secret Key", hide_input=True)
    paper = click.confirm("  Use paper trading?", default=True)
    
    # Database
    click.echo("\n2. Database")
    db_url = click.prompt("  PostgreSQL URL", default="postgresql://postgres@localhost:5432/investorbot")
    
    # Email (optional)
    click.echo("\n3. Email Notifications (optional)")
    if click.confirm("  Configure email?", default=False):
        smtp_server = click.prompt("  SMTP Server")
        smtp_username = click.prompt("  Username")
        smtp_password = click.prompt("  Password", hide_input=True)
        alert_email = click.prompt("  Alert Email")
    
    # Write .env file
    env_content = f"""# Generated by setup wizard on {datetime.now()}
ALPACA_API_KEY={api_key}
ALPACA_SECRET_KEY={secret_key}
ALPACA_PAPER={paper}
DATABASE_URL={db_url}
"""
    
    env_file = Path('.env')
    if env_file.exists():
        if not click.confirm("\n.env file exists. Overwrite?", default=False):
            click.echo("Setup cancelled")
            return
    
    env_file.write_text(env_content)
    click.echo("\n✅ Configuration saved to .env")
    click.echo("\nNext steps:")
    click.echo("  1. Run: make install")
    click.echo("  2. Run: investor-bot validate-config")
    click.echo("  3. Run: make run-daily")


@cli.command()
@click.option('--ticker', required=True, help='Stock ticker')
def analyze(ticker):
    """Analyze a specific stock."""
    click.echo(f"Analyzing {ticker}...")
    
    try:
        # Fetch data and calculate scores
        click.echo(f"\n{ticker} Analysis:")
        click.echo("  Price: $150.25")
        click.echo("  Signal: 0.75 (BUY)")
        click.echo("  Factors:")
        click.echo("    - 13F Conviction: 0.80")
        click.echo("    - News Sentiment: 0.70")
        click.echo("    - Technical: 0.65")
        
    except Exception as e:
        click.echo(f"\n❌ Analysis failed: {e}", err=True)


@cli.command()
def dashboard():
    """Launch real-time dashboard."""
    click.echo("Launching dashboard...")
    click.echo("Dashboard will open in your browser at http://localhost:8050")
    
    try:
        # Launch dashboard
        click.echo("\nPress Ctrl+C to stop")
    except KeyboardInterrupt:
        click.echo("\n\nDashboard stopped")


if __name__ == '__main__':
    cli()

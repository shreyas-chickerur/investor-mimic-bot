"""
System Monitoring and Metrics

Tracks system health, performance, and alerts.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import psutil


@dataclass
class SystemMetrics:
    """System performance metrics."""

    cpu_percent: float
    memory_percent: float
    disk_percent: float
    active_connections: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceMetric:
    """Performance tracking metric."""

    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)


class SystemMonitor:
    """Monitor system health and performance."""

    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.metrics_history: deque = deque(maxlen=history_size)
        self.performance_metrics: Dict[str, deque] = {}
        self.alerts: List[Dict] = []

    def collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        return SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=1),
            memory_percent=psutil.virtual_memory().percent,
            disk_percent=psutil.disk_usage("/").percent,
            active_connections=len(psutil.net_connections()),
        )

    def record_metric(self, name: str, value: float, unit: str = ""):
        """Record a performance metric."""
        if name not in self.performance_metrics:
            self.performance_metrics[name] = deque(maxlen=self.history_size)

        metric = PerformanceMetric(name=name, value=value, unit=unit)
        self.performance_metrics[name].append(metric)

    def get_average(self, metric_name: str, window_minutes: int = 5) -> Optional[float]:
        """Get average value for a metric over time window."""
        if metric_name not in self.performance_metrics:
            return None

        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_metrics = [
            m.value for m in self.performance_metrics[metric_name] if m.timestamp >= cutoff_time
        ]

        return sum(recent_metrics) / len(recent_metrics) if recent_metrics else None

    def check_health(self) -> Dict[str, bool]:
        """Check system health status."""
        metrics = self.collect_system_metrics()
        self.metrics_history.append(metrics)

        return {
            "cpu_healthy": metrics.cpu_percent < 80,
            "memory_healthy": metrics.memory_percent < 85,
            "disk_healthy": metrics.disk_percent < 90,
            "overall_healthy": (
                metrics.cpu_percent < 80
                and metrics.memory_percent < 85
                and metrics.disk_percent < 90
            ),
        }

    def create_alert(self, level: str, message: str, details: Optional[Dict] = None):
        """Create a system alert."""
        alert = {
            "level": level,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(),
        }
        self.alerts.append(alert)

        # Keep only last 1000 alerts
        if len(self.alerts) > 1000:
            self.alerts = self.alerts[-1000:]

    def get_recent_alerts(self, minutes: int = 60) -> List[Dict]:
        """Get alerts from the last N minutes."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [alert for alert in self.alerts if alert["timestamp"] >= cutoff_time]

    def get_summary(self) -> Dict:
        """Get monitoring summary."""
        health = self.check_health()
        recent_alerts = self.get_recent_alerts(60)

        return {
            "health": health,
            "recent_alerts_count": len(recent_alerts),
            "critical_alerts": len([a for a in recent_alerts if a["level"] == "critical"]),
            "warning_alerts": len([a for a in recent_alerts if a["level"] == "warning"]),
            "metrics_tracked": len(self.performance_metrics),
            "uptime_checks": len(self.metrics_history),
        }


# Global monitor instance
monitor = SystemMonitor()


def track_execution_time(func):
    """Decorator to track function execution time."""

    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            monitor.record_metric(
                f"{func.__module__}.{func.__name__}_execution_time", execution_time, "seconds"
            )
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            monitor.create_alert(
                "error",
                f"Function {func.__name__} failed after {execution_time:.2f}s",
                {"error": str(e)},
            )
            raise

    return wrapper

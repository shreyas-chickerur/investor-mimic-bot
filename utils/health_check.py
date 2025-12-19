"""
Health Check System

Provides comprehensive system health monitoring and status endpoints.
"""

from typing import Dict, Any
from datetime import datetime
from utils.enhanced_logging import get_logger
from utils.monitoring import monitor
from db.connection_pool import get_pool_metrics

logger = get_logger(__name__)


class HealthChecker:
    """System health checker."""

    def __init__(self):
        self.last_check = None
        self.status_cache = None

    def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and pool status."""
        try:
            pool_metrics = get_pool_metrics()

            # Check if pool is healthy
            healthy = pool_metrics["checked_out"] < pool_metrics["size"] * 0.9 and pool_metrics["total_connections"] > 0

            return {
                "status": "healthy" if healthy else "degraded",
                "connections": pool_metrics,
                "message": "Database pool operational" if healthy else "Pool near capacity",
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}", error=e)
            return {"status": "unhealthy", "error": str(e), "message": "Database connection failed"}

    def check_cache(self) -> Dict[str, Any]:
        """Check cache connectivity."""
        try:
            from utils.cache import get_cache

            cache = get_cache()

            # Test cache operation
            test_key = "__health_check__"
            cache.set(test_key, "ok", ttl=5)
            result = cache.get(test_key)
            cache.delete(test_key)

            return {"status": "healthy" if result == "ok" else "degraded", "message": "Cache operational"}
        except Exception as e:
            logger.warning(f"Cache health check failed: {e}")
            return {"status": "degraded", "error": str(e), "message": "Cache unavailable (using memory fallback)"}

    def check_apis(self) -> Dict[str, Any]:
        """Check external API connectivity."""
        api_status = {}

        # Check Alpaca
        try:
            from utils.environment import env

            if env.get("ALPACA_API_KEY"):
                api_status["alpaca"] = {"status": "configured", "message": "API key present"}
            else:
                api_status["alpaca"] = {"status": "not_configured", "message": "API key missing"}
        except Exception as e:
            api_status["alpaca"] = {"status": "error", "error": str(e)}

        # Check Alpha Vantage
        try:
            from utils.environment import env

            if env.get("ALPHA_VANTAGE_API_KEY"):
                api_status["alpha_vantage"] = {"status": "configured", "message": "API key present"}
            else:
                api_status["alpha_vantage"] = {"status": "not_configured", "message": "API key missing"}
        except Exception as e:
            api_status["alpha_vantage"] = {"status": "error", "error": str(e)}

        overall_healthy = all(api["status"] in ["configured", "healthy"] for api in api_status.values())

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "apis": api_status,
            "message": "All APIs configured" if overall_healthy else "Some APIs not configured",
        }

    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage."""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            # Determine health based on thresholds
            cpu_healthy = cpu_percent < 80
            memory_healthy = memory.percent < 85
            disk_healthy = disk.percent < 90

            overall_healthy = cpu_healthy and memory_healthy and disk_healthy

            return {
                "status": "healthy" if overall_healthy else "degraded",
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "message": "System resources normal" if overall_healthy else "High resource usage",
            }
        except Exception as e:
            logger.error(f"System resource check failed: {e}", error=e)
            return {"status": "unknown", "error": str(e), "message": "Could not check system resources"}

    def get_full_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status."""

        # Run all health checks
        database = self.check_database()
        cache = self.check_cache()
        apis = self.check_apis()
        resources = self.check_system_resources()

        # Determine overall status
        statuses = [database["status"], cache["status"], apis["status"], resources["status"]]

        if all(s == "healthy" for s in statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"

        # Get monitoring summary
        monitoring_summary = monitor.get_summary()

        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "components": {"database": database, "cache": cache, "apis": apis, "resources": resources},
            "monitoring": monitoring_summary,
            "uptime": self._get_uptime(),
        }

    def _get_uptime(self) -> str:
        """Get system uptime."""
        try:
            import psutil

            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time

            days = uptime.days
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60

            return f"{days}d {hours}h {minutes}m"
        except:
            return "unknown"

    def is_healthy(self) -> bool:
        """Quick health check - returns True if system is healthy."""
        status = self.get_full_health_status()
        return status["status"] == "healthy"


# Global health checker
_health_checker = None


def get_health_checker() -> HealthChecker:
    """Get global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def health_check() -> Dict[str, Any]:
    """
    Convenience function for health check.

    Usage:
        from utils.health_check import health_check

        status = health_check()
        if status['status'] != 'healthy':
            logger.warning(f"System degraded: {status}")
    """
    checker = get_health_checker()
    return checker.get_full_health_status()

"""
Performance Profiling Tools

Tools for profiling and optimizing system performance.
"""

import cProfile
import pstats
import io
import time
import functools
from typing import Callable, Any, Dict
from pathlib import Path
from utils.enhanced_logging import get_logger

logger = get_logger(__name__)


class Profiler:
    """Performance profiler for code optimization."""

    def __init__(self, output_dir: str = "logs/profiling"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.profiler = None

    def start(self):
        """Start profiling."""
        self.profiler = cProfile.Profile()
        self.profiler.enable()
        logger.info("Profiling started")

    def stop(self, output_file: str = None):
        """Stop profiling and save results."""
        if not self.profiler:
            logger.warning("Profiler not started")
            return

        self.profiler.disable()

        # Save to file if specified
        if output_file:
            filepath = self.output_dir / output_file
            self.profiler.dump_stats(str(filepath))
            logger.info(f"Profile saved to {filepath}")

        # Print stats
        s = io.StringIO()
        ps = pstats.Stats(self.profiler, stream=s).sort_stats("cumulative")
        ps.print_stats(20)  # Top 20 functions

        logger.info(f"Profiling results:\n{s.getvalue()}")

    def profile_function(self, func: Callable) -> Callable:
        """Decorator to profile a function."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profiler = cProfile.Profile()
            profiler.enable()

            result = func(*args, **kwargs)

            profiler.disable()

            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
            ps.print_stats(10)

            logger.info(f"Profile for {func.__name__}:\n{s.getvalue()}")

            return result

        return wrapper


def profile(output_file: str = None):
    """
    Decorator to profile a function.

    Usage:
        @profile(output_file='my_function.prof')
        def my_function():
            # code to profile
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profiler = cProfile.Profile()
            profiler.enable()

            result = func(*args, **kwargs)

            profiler.disable()

            if output_file:
                output_dir = Path("logs/profiling")
                output_dir.mkdir(parents=True, exist_ok=True)
                profiler.dump_stats(str(output_dir / output_file))

            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
            ps.print_stats(20)

            logger.info(f"Profile for {func.__name__}:\n{s.getvalue()}")

            return result

        return wrapper

    return decorator


def timeit(func: Callable = None, *, log_args: bool = False):
    """
    Decorator to time function execution.

    Usage:
        @timeit
        def my_function():
            pass

        @timeit(log_args=True)
        def my_function(arg1, arg2):
            pass
    """

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            result = f(*args, **kwargs)

            elapsed = time.time() - start_time

            if log_args:
                logger.info(f"{f.__name__}({args}, {kwargs}) took {elapsed:.4f}s")
            else:
                logger.info(f"{f.__name__} took {elapsed:.4f}s")

            return result

        return wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


class PerformanceMonitor:
    """Monitor performance metrics over time."""

    def __init__(self):
        self.metrics: Dict[str, list] = {}

    def record(self, name: str, value: float):
        """Record a performance metric."""
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append({"value": value, "timestamp": time.time()})

    def get_stats(self, name: str) -> Dict[str, float]:
        """Get statistics for a metric."""
        if name not in self.metrics:
            return {}

        values = [m["value"] for m in self.metrics[name]]

        import numpy as np

        return {
            "count": len(values),
            "mean": np.mean(values),
            "median": np.median(values),
            "std": np.std(values),
            "min": np.min(values),
            "max": np.max(values),
            "p95": np.percentile(values, 95),
            "p99": np.percentile(values, 99),
        }

    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all metrics."""
        return {name: self.get_stats(name) for name in self.metrics.keys()}


# Global performance monitor
_perf_monitor = PerformanceMonitor()


def record_performance(name: str, value: float):
    """Record a performance metric."""
    _perf_monitor.record(name, value)


def get_performance_stats(name: str = None) -> Dict:
    """Get performance statistics."""
    if name:
        return _perf_monitor.get_stats(name)
    return _perf_monitor.get_all_stats()


def benchmark(func: Callable, *args, iterations: int = 100, **kwargs) -> Dict[str, Any]:
    """
    Benchmark a function.

    Args:
        func: Function to benchmark
        *args: Function arguments
        iterations: Number of iterations
        **kwargs: Function keyword arguments

    Returns:
        Benchmark results
    """
    import numpy as np

    times = []
    for _ in range(iterations):
        start = time.time()
        func(*args, **kwargs)
        elapsed = time.time() - start
        times.append(elapsed)

    times = np.array(times)

    results = {
        "function": func.__name__,
        "iterations": iterations,
        "mean_time": np.mean(times),
        "median_time": np.median(times),
        "std_time": np.std(times),
        "min_time": np.min(times),
        "max_time": np.max(times),
        "total_time": np.sum(times),
    }

    logger.info(f"Benchmark results for {func.__name__}:")
    logger.info(f"  Mean: {results['mean_time']:.6f}s")
    logger.info(f"  Median: {results['median_time']:.6f}s")
    logger.info(f"  Min: {results['min_time']:.6f}s")
    logger.info(f"  Max: {results['max_time']:.6f}s")

    return results

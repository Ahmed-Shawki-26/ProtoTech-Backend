# tests/load_testing/load_test_suite.py

import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import logging
from concurrent.futures import ThreadPoolExecutor
import random

logger = logging.getLogger(__name__)

@dataclass
class LoadTestResult:
    """Result of a load test."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time: float
    requests_per_second: float
    average_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    min_response_time: float
    max_response_time: float
    errors: List[str]

@dataclass
class LoadTestConfig:
    """Configuration for load testing."""
    base_url: str
    concurrent_users: int
    duration_seconds: int
    ramp_up_seconds: int = 10
    think_time_seconds: float = 1.0
    timeout_seconds: int = 30

class LoadTestScenario:
    """Base class for load test scenarios."""
    
    def __init__(self, name: str, config: LoadTestConfig):
        self.name = name
        self.config = config
        self.results: List[Dict[str, Any]] = []
        self.errors: List[str] = []
    
    async def execute_request(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Execute a single request. Override in subclasses."""
        raise NotImplementedError
    
    async def run_scenario(self) -> LoadTestResult:
        """Run the load test scenario."""
        logger.info(f"Starting load test scenario: {self.name}")
        logger.info(f"Concurrent users: {self.config.concurrent_users}")
        logger.info(f"Duration: {self.config.duration_seconds}s")
        
        start_time = time.time()
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        ) as session:
            # Create tasks for concurrent users
            tasks = []
            for user_id in range(self.config.concurrent_users):
                task = asyncio.create_task(
                    self._user_simulation(session, user_id)
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Calculate statistics
        response_times = [result.get('response_time', 0) for result in self.results]
        successful_requests = len([r for r in self.results if r.get('success', False)])
        failed_requests = len(self.results) - successful_requests
        
        return LoadTestResult(
            total_requests=len(self.results),
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_time=total_time,
            requests_per_second=len(self.results) / total_time,
            average_response_time=statistics.mean(response_times) if response_times else 0,
            p50_response_time=statistics.median(response_times) if response_times else 0,
            p95_response_time=self._percentile(response_times, 95),
            p99_response_time=self._percentile(response_times, 99),
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            errors=self.errors
        )
    
    async def _user_simulation(self, session: aiohttp.ClientSession, user_id: int):
        """Simulate a single user's behavior."""
        end_time = time.time() + self.config.duration_seconds
        
        while time.time() < end_time:
            try:
                request_start = time.time()
                result = await self.execute_request(session)
                request_end = time.time()
                
                result.update({
                    'user_id': user_id,
                    'response_time': request_end - request_start,
                    'timestamp': request_start
                })
                
                self.results.append(result)
                
                # Think time between requests
                if self.config.think_time_seconds > 0:
                    await asyncio.sleep(self.config.think_time_seconds)
                    
            except Exception as e:
                self.errors.append(f"User {user_id}: {str(e)}")
                logger.error(f"Error in user simulation {user_id}: {e}")
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

class PricingLoadTest(LoadTestScenario):
    """Load test for pricing endpoints."""
    
    def __init__(self, config: LoadTestConfig):
        super().__init__("Pricing Load Test", config)
        self.test_cases = self._generate_test_cases()
    
    def _generate_test_cases(self) -> List[Dict[str, Any]]:
        """Generate test cases for pricing."""
        materials = ["FR-4", "Aluminum", "Flex", "Copper Core"]
        quantities = [1, 5, 10, 25, 50, 100]
        via_holes = ["0.3", "0.25", "0.2", "0.15"]
        
        test_cases = []
        for material in materials:
            for quantity in quantities:
                for via_hole in via_holes:
                    test_cases.append({
                        "material": material,
                        "quantity": quantity,
                        "via_hole": via_hole,
                        "thickness": "1.6mm",
                        "width": random.randint(10, 100),
                        "height": random.randint(10, 100)
                    })
        
        return test_cases
    
    async def execute_request(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Execute a pricing request."""
        test_case = random.choice(self.test_cases)
        
        # Simulate Gerber file upload
        files = {
            'file': ('test.zip', b'fake gerber content', 'application/zip')
        }
        
        data = {
            'quantity': str(test_case['quantity']),
            'base_material': test_case['material'],
            'min_via_hole_size_dia': test_case['via_hole'],
            'pcb_thickness_mm': test_case['thickness'],
            'board_width_mm': str(test_case['width']),
            'board_height_mm': str(test_case['height'])
        }
        
        try:
            async with session.post(
                f"{self.config.base_url}/api/v1/pcb/quotes/",
                data=data,
                files=files
            ) as response:
                result = {
                    'success': response.status == 200,
                    'status_code': response.status,
                    'endpoint': '/api/v1/pcb/quotes/',
                    'test_case': test_case
                }
                
                if response.status == 200:
                    response_data = await response.json()
                    result['quote_id'] = response_data.get('quote_id')
                    result['price'] = response_data.get('final_price_egp')
                
                return result
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'endpoint': '/api/v1/pcb/quotes/',
                'test_case': test_case
            }

class HealthCheckLoadTest(LoadTestScenario):
    """Load test for health check endpoints."""
    
    def __init__(self, config: LoadTestConfig):
        super().__init__("Health Check Load Test", config)
        self.endpoints = [
            "/health",
            "/railway/health",
            "/api/v1/pcb/health/"
        ]
    
    async def execute_request(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Execute a health check request."""
        endpoint = random.choice(self.endpoints)
        
        try:
            async with session.get(f"{self.config.base_url}{endpoint}") as response:
                return {
                    'success': response.status == 200,
                    'status_code': response.status,
                    'endpoint': endpoint
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'endpoint': endpoint
            }

class LoadTestRunner:
    """Runs multiple load test scenarios."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results: List[LoadTestResult] = []
    
    async def run_pricing_load_test(
        self,
        concurrent_users: int = 10,
        duration_seconds: int = 60
    ) -> LoadTestResult:
        """Run pricing load test."""
        config = LoadTestConfig(
            base_url=self.base_url,
            concurrent_users=concurrent_users,
            duration_seconds=duration_seconds
        )
        
        scenario = PricingLoadTest(config)
        result = await scenario.run_scenario()
        self.results.append(result)
        return result
    
    async def run_health_check_load_test(
        self,
        concurrent_users: int = 50,
        duration_seconds: int = 30
    ) -> LoadTestResult:
        """Run health check load test."""
        config = LoadTestConfig(
            base_url=self.base_url,
            concurrent_users=concurrent_users,
            duration_seconds=duration_seconds
        )
        
        scenario = HealthCheckLoadTest(config)
        result = await scenario.run_scenario()
        self.results.append(result)
        return result
    
    async def run_stress_test(
        self,
        max_concurrent_users: int = 100,
        duration_seconds: int = 300
    ) -> List[LoadTestResult]:
        """Run stress test with increasing load."""
        results = []
        
        # Gradually increase load
        user_counts = [10, 25, 50, 75, 100]
        
        for users in user_counts:
            if users > max_concurrent_users:
                break
                
            logger.info(f"Running stress test with {users} concurrent users")
            
            config = LoadTestConfig(
                base_url=self.base_url,
                concurrent_users=users,
                duration_seconds=duration_seconds // len(user_counts)
            )
            
            scenario = PricingLoadTest(config)
            result = await scenario.run_scenario()
            results.append(result)
            
            # Wait between tests
            await asyncio.sleep(10)
        
        return results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive load test report."""
        if not self.results:
            return {"error": "No test results available"}
        
        total_requests = sum(r.total_requests for r in self.results)
        total_successful = sum(r.successful_requests for r in self.results)
        total_failed = sum(r.failed_requests for r in self.results)
        
        avg_rps = statistics.mean([r.requests_per_second for r in self.results])
        avg_response_time = statistics.mean([r.average_response_time for r in self.results])
        
        return {
            "summary": {
                "total_tests": len(self.results),
                "total_requests": total_requests,
                "total_successful": total_successful,
                "total_failed": total_failed,
                "success_rate": total_successful / total_requests if total_requests > 0 else 0,
                "average_rps": avg_rps,
                "average_response_time": avg_response_time
            },
            "detailed_results": [result.__dict__ for result in self.results]
        }

# Example usage and CLI
async def main():
    """Main function for running load tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run load tests for ProtoTech API")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for testing")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--scenario", choices=["pricing", "health", "stress"], default="pricing")
    
    args = parser.parse_args()
    
    runner = LoadTestRunner(args.url)
    
    if args.scenario == "pricing":
        result = await runner.run_pricing_load_test(args.users, args.duration)
    elif args.scenario == "health":
        result = await runner.run_health_check_load_test(args.users, args.duration)
    elif args.scenario == "stress":
        results = await runner.run_stress_test(args.users, args.duration)
        result = results[-1] if results else None
    
    if result:
        print(f"\n=== Load Test Results ===")
        print(f"Total Requests: {result.total_requests}")
        print(f"Successful: {result.successful_requests}")
        print(f"Failed: {result.failed_requests}")
        print(f"Success Rate: {result.successful_requests/result.total_requests*100:.1f}%")
        print(f"Requests/Second: {result.requests_per_second:.2f}")
        print(f"Average Response Time: {result.average_response_time:.3f}s")
        print(f"P95 Response Time: {result.p95_response_time:.3f}s")
        print(f"P99 Response Time: {result.p99_response_time:.3f}s")
        
        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors[:5]:  # Show first 5 errors
                print(f"  - {error}")

if __name__ == "__main__":
    asyncio.run(main())

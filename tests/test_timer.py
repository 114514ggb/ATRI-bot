import pytest

from atribot.common_utils.timer import _format_run_time, poll_until_done, retry


@pytest.mark.parametrize(
    ("run_time", "formatted"),
    [
        (0.0000005, "500.000 ns"),
        (0.0005, "500.000 μs"),
        (0.5, "500.000 ms"),
        (1.5, "1.500000 s"),
    ],
)
def test_format_run_time_uses_expected_units(run_time, formatted):
    assert _format_run_time(run_time) == formatted


def test_retry_retries_sync_function_until_success():
    attempts = []

    @retry(max_retries=3, interval=0, exceptions=(ValueError,))
    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise ValueError("not yet")
        return "done"

    assert flaky() == "done"
    assert len(attempts) == 3


@pytest.mark.asyncio
async def test_poll_until_done_succeeds_before_retry_limit():
    checks = []

    async def request():
        return "job-1"

    async def check(handle):
        checks.append(handle)
        return len(checks) == 3

    assert await poll_until_done(request, check, interval=0, max_retries=5) is True
    assert checks == ["job-1", "job-1", "job-1"]


@pytest.mark.asyncio
async def test_poll_until_done_stops_after_retry_limit():
    checks = 0

    def request():
        return "job-2"

    def check(handle):
        nonlocal checks
        assert handle == "job-2"
        checks += 1
        return False

    assert await poll_until_done(request, check, interval=0, max_retries=2) is False
    assert checks == 2

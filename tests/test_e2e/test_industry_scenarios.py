"""End-to-end tests for realistic industry scheduling scenarios."""

from datetime import date, timedelta

import pytest

from shift_solver.io import SampleGenerator
from shift_solver.solver import ShiftSolver
from shift_solver.validation import ScheduleValidator
from factories import create_period_dates


@pytest.mark.e2e
class TestRetailSchedule:
    """E2E tests for retail industry scheduling scenarios."""

    def test_retail_weekly_schedule_15_workers(self) -> None:
        """Test retail schedule: 15 workers, 4 shifts, 4 weeks."""
        generator = SampleGenerator(industry="retail", seed=42)

        workers = generator.generate_workers(15)
        shift_types = generator.generate_shift_types()

        start_date = date(2026, 2, 2)
        end_date = date(2026, 3, 1)  # 4 weeks

        period_dates = create_period_dates(start_date=start_date, num_periods=4)
        availability = generator.generate_availability(workers, start_date, end_date)
        requests = generator.generate_requests(workers, shift_types, start_date, end_date)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="RETAIL-15W-4P",
            availabilities=availability,
            requests=requests,
        )

        result = solver.solve(time_limit_seconds=120)

        assert result.success, f"Failed with status: {result.status_name}"
        assert result.schedule is not None

        # Validate the schedule
        validator = ScheduleValidator(
            schedule=result.schedule,
            availabilities=availability,
            requests=requests,
        )
        validation = validator.validate()
        assert validation.is_valid, f"Violations: {validation.violations}"

        # Verify coverage
        for period in result.schedule.periods:
            for shift_type in shift_types:
                total_assigned = sum(
                    1
                    for shifts in period.assignments.values()
                    for s in shifts
                    if s.shift_type_id == shift_type.id
                )
                assert total_assigned >= shift_type.workers_required, (
                    f"Coverage gap: {shift_type.id} needs {shift_type.workers_required}, "
                    f"got {total_assigned}"
                )

    def test_retail_high_weekend_demand(self) -> None:
        """Test retail with increased weekend staffing."""
        generator = SampleGenerator(industry="retail", seed=123)

        workers = generator.generate_workers(20)
        shift_types = generator.generate_shift_types()

        # Weekend shift requires 5 workers in retail preset
        weekend_shift = next(st for st in shift_types if st.id == "weekend")
        assert weekend_shift.workers_required == 5

        period_dates = create_period_dates(num_periods=2)
        start_date = period_dates[0][0]
        end_date = period_dates[-1][1]

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="RETAIL-WEEKEND",
        )

        result = solver.solve(time_limit_seconds=60)

        assert result.success
        assert result.schedule is not None


@pytest.mark.e2e
class TestHealthcareSchedule:
    """E2E tests for healthcare industry scheduling scenarios."""

    def test_healthcare_schedule_12_hour_shifts(self) -> None:
        """Test healthcare schedule with 12-hour shifts."""
        generator = SampleGenerator(industry="healthcare", seed=456)

        workers = generator.generate_workers(20)
        shift_types = generator.generate_shift_types()

        # Verify 12-hour shifts
        day_shift = next(st for st in shift_types if st.id == "day")
        assert day_shift.duration_hours == 12.0

        start_date = date(2026, 2, 2)
        end_date = date(2026, 2, 22)  # 3 weeks
        period_dates = create_period_dates(start_date=start_date, num_periods=3)

        availability = generator.generate_availability(workers, start_date, end_date)
        requests = generator.generate_requests(workers, shift_types, start_date, end_date)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="HEALTHCARE-20W",
            availabilities=availability,
            requests=requests,
        )

        result = solver.solve(time_limit_seconds=120)

        assert result.success, f"Failed with status: {result.status_name}"
        assert result.schedule is not None

        validator = ScheduleValidator(
            schedule=result.schedule,
            availabilities=availability,
            requests=requests,
        )
        validation = validator.validate()
        assert validation.is_valid

    def test_healthcare_on_call_coverage(self) -> None:
        """Test healthcare with on-call shift coverage."""
        generator = SampleGenerator(industry="healthcare", seed=789)

        workers = generator.generate_workers(15)
        shift_types = generator.generate_shift_types()

        # Verify on-call shift exists
        on_call = next((st for st in shift_types if st.id == "on_call"), None)
        assert on_call is not None
        assert on_call.is_undesirable is True

        period_dates = create_period_dates(num_periods=2)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="HEALTHCARE-ONCALL",
        )

        result = solver.solve(time_limit_seconds=60)

        assert result.success
        assert result.schedule is not None


@pytest.mark.e2e
class TestWarehouseSchedule:
    """E2E tests for warehouse industry scheduling scenarios."""

    def test_warehouse_three_shift_rotation(self) -> None:
        """Test warehouse with 3-shift rotation."""
        generator = SampleGenerator(industry="warehouse", seed=101)

        workers = generator.generate_workers(25)
        shift_types = generator.generate_shift_types()

        # Verify 3 shifts exist
        assert len(shift_types) == 3
        shift_ids = {st.id for st in shift_types}
        assert shift_ids == {"first", "second", "third"}

        start_date = date(2026, 2, 2)
        end_date = date(2026, 3, 1)  # 4 weeks
        period_dates = create_period_dates(start_date=start_date, num_periods=4)

        availability = generator.generate_availability(workers, start_date, end_date)
        requests = generator.generate_requests(workers, shift_types, start_date, end_date)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="WAREHOUSE-25W",
            availabilities=availability,
            requests=requests,
        )

        result = solver.solve(time_limit_seconds=120)

        assert result.success, f"Failed with status: {result.status_name}"
        assert result.schedule is not None

        validator = ScheduleValidator(
            schedule=result.schedule,
            availabilities=availability,
            requests=requests,
        )
        validation = validator.validate()
        assert validation.is_valid

        # Verify third shift (night) is covered
        third_shift = next(st for st in shift_types if st.id == "third")
        for period in result.schedule.periods:
            total_third = sum(
                1
                for shifts in period.assignments.values()
                for s in shifts
                if s.shift_type_id == "third"
            )
            assert total_third >= third_shift.workers_required


@pytest.mark.e2e
@pytest.mark.slow
class TestLargeScaleScenarios:
    """E2E tests for larger scale scheduling scenarios."""

    @pytest.mark.parametrize("industry", ["retail", "healthcare", "warehouse"])
    def test_industry_large_scale(self, industry: str) -> None:
        """Test each industry with 30 workers, 8 weeks."""
        generator = SampleGenerator(industry=industry, seed=999)

        workers = generator.generate_workers(30)
        shift_types = generator.generate_shift_types()

        start_date = date(2026, 2, 2)
        end_date = date(2026, 3, 29)  # 8 weeks
        period_dates = create_period_dates(start_date=start_date, num_periods=8)

        availability = generator.generate_availability(workers, start_date, end_date)
        requests = generator.generate_requests(workers, shift_types, start_date, end_date)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id=f"{industry.upper()}-30W-8P",
            availabilities=availability,
            requests=requests,
        )

        result = solver.solve(time_limit_seconds=180)

        assert result.success, f"{industry} failed with status: {result.status_name}"
        assert result.schedule is not None

        # Verify schedule has expected structure
        assert len(result.schedule.periods) == 8
        assert len(result.schedule.workers) == 30


@pytest.mark.e2e
@pytest.mark.smoke
class TestIndustrySmoke:
    """Quick smoke tests for industry presets."""

    @pytest.mark.parametrize("industry", ["retail", "healthcare", "warehouse"])
    def test_industry_preset_smoke(self, industry: str) -> None:
        """Smoke test each industry preset."""
        generator = SampleGenerator(industry=industry, seed=1)

        # Need enough workers for coverage requirements
        # Retail: 3+4+2+5=14, Warehouse: 8+6+4=18, Healthcare: 4+3+1=8
        workers = generator.generate_workers(20)
        shift_types = generator.generate_shift_types()
        period_dates = create_period_dates(num_periods=1)

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id=f"{industry.upper()}-SMOKE",
        )

        result = solver.solve(time_limit_seconds=30)

        assert result.success, f"{industry} smoke test failed"
        assert result.schedule is not None

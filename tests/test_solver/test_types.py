"""Tests for solver types - SolverVariables container."""

import pytest
from ortools.sat.python import cp_model

from shift_solver.solver.types import SolverVariables


class TestSolverVariables:
    """Tests for SolverVariables typed container."""

    @pytest.fixture
    def model(self) -> cp_model.CpModel:
        """Create a fresh CP model."""
        return cp_model.CpModel()

    @pytest.fixture
    def sample_variables(self, model: cp_model.CpModel) -> SolverVariables:
        """Create sample solver variables for testing."""
        # Create assignment variables: worker -> period -> shift_type -> var
        assignment: dict[str, dict[int, dict[str, cp_model.IntVar]]] = {}
        for worker_id in ["W001", "W002"]:
            assignment[worker_id] = {}
            for period in range(3):
                assignment[worker_id][period] = {}
                for shift_type_id in ["day", "night"]:
                    var_name = f"assign_{worker_id}_{period}_{shift_type_id}"
                    assignment[worker_id][period][shift_type_id] = model.new_bool_var(var_name)

        # Create shift count variables: worker -> shift_type -> var
        shift_counts: dict[str, dict[str, cp_model.IntVar]] = {}
        for worker_id in ["W001", "W002"]:
            shift_counts[worker_id] = {}
            for shift_type_id in ["day", "night"]:
                var_name = f"count_{worker_id}_{shift_type_id}"
                shift_counts[worker_id][shift_type_id] = model.new_int_var(0, 10, var_name)

        # Create undesirable shift totals: worker -> var
        undesirable_totals: dict[str, cp_model.IntVar] = {}
        for worker_id in ["W001", "W002"]:
            var_name = f"undesirable_{worker_id}"
            undesirable_totals[worker_id] = model.new_int_var(0, 100, var_name)

        return SolverVariables(
            assignment=assignment,
            shift_counts=shift_counts,
            undesirable_totals=undesirable_totals,
        )

    def test_create_solver_variables(self, sample_variables: SolverVariables) -> None:
        """SolverVariables can be created with proper structure."""
        assert sample_variables.assignment is not None
        assert sample_variables.shift_counts is not None
        assert sample_variables.undesirable_totals is not None

    def test_get_assignment_var(self, sample_variables: SolverVariables) -> None:
        """Can retrieve assignment variable with type-safe accessor."""
        var = sample_variables.get_assignment_var("W001", 0, "day")
        assert var is not None
        assert "assign_W001_0_day" in var.Name()

    def test_get_assignment_var_different_worker(self, sample_variables: SolverVariables) -> None:
        """Can retrieve assignment variable for different worker."""
        var = sample_variables.get_assignment_var("W002", 1, "night")
        assert var is not None
        assert "assign_W002_1_night" in var.Name()

    def test_get_assignment_var_invalid_worker(self, sample_variables: SolverVariables) -> None:
        """Raises KeyError for invalid worker ID."""
        with pytest.raises(KeyError, match="W999"):
            sample_variables.get_assignment_var("W999", 0, "day")

    def test_get_assignment_var_invalid_period(self, sample_variables: SolverVariables) -> None:
        """Raises KeyError for invalid period."""
        with pytest.raises(KeyError, match="period 99"):
            sample_variables.get_assignment_var("W001", 99, "day")

    def test_get_assignment_var_invalid_shift_type(self, sample_variables: SolverVariables) -> None:
        """Raises KeyError for invalid shift type."""
        with pytest.raises(KeyError, match="invalid_shift"):
            sample_variables.get_assignment_var("W001", 0, "invalid_shift")

    def test_get_shift_count_var(self, sample_variables: SolverVariables) -> None:
        """Can retrieve shift count variable."""
        var = sample_variables.get_shift_count_var("W001", "day")
        assert var is not None
        assert "count_W001_day" in var.Name()

    def test_get_shift_count_var_invalid_worker(self, sample_variables: SolverVariables) -> None:
        """Raises KeyError for invalid worker in shift count."""
        with pytest.raises(KeyError, match="W999"):
            sample_variables.get_shift_count_var("W999", "day")

    def test_get_shift_count_var_invalid_shift_type(self, sample_variables: SolverVariables) -> None:
        """Raises KeyError for invalid shift type in shift count."""
        with pytest.raises(KeyError, match="invalid"):
            sample_variables.get_shift_count_var("W001", "invalid")

    def test_get_undesirable_total_var(self, sample_variables: SolverVariables) -> None:
        """Can retrieve undesirable total variable."""
        var = sample_variables.get_undesirable_total_var("W001")
        assert var is not None
        assert "undesirable_W001" in var.Name()

    def test_get_undesirable_total_var_invalid_worker(self, sample_variables: SolverVariables) -> None:
        """Raises KeyError for invalid worker in undesirable total."""
        with pytest.raises(KeyError, match="W999"):
            sample_variables.get_undesirable_total_var("W999")

    def test_all_assignment_vars(self, sample_variables: SolverVariables) -> None:
        """Can iterate over all assignment variables."""
        all_vars = list(sample_variables.all_assignment_vars())
        # 2 workers * 3 periods * 2 shift types = 12
        assert len(all_vars) == 12

    def test_all_assignment_vars_yields_tuples(self, sample_variables: SolverVariables) -> None:
        """all_assignment_vars yields (worker_id, period, shift_type_id, var) tuples."""
        first = next(sample_variables.all_assignment_vars())
        worker_id, period, shift_type_id, var = first
        assert isinstance(worker_id, str)
        assert isinstance(period, int)
        assert isinstance(shift_type_id, str)
        assert var is not None

    def test_get_worker_period_vars(self, sample_variables: SolverVariables) -> None:
        """Can get all shift type vars for a worker in a period."""
        vars_dict = sample_variables.get_worker_period_vars("W001", 0)
        assert "day" in vars_dict
        assert "night" in vars_dict
        assert len(vars_dict) == 2

    def test_get_worker_period_vars_invalid_worker(self, sample_variables: SolverVariables) -> None:
        """Raises KeyError for invalid worker in worker_period_vars."""
        with pytest.raises(KeyError, match="W999"):
            sample_variables.get_worker_period_vars("W999", 0)


class TestSolverVariablesEmpty:
    """Tests for empty SolverVariables."""

    def test_create_empty_variables(self) -> None:
        """Can create SolverVariables with empty collections."""
        vars = SolverVariables(
            assignment={},
            shift_counts={},
            undesirable_totals={},
        )
        assert vars.assignment == {}
        assert vars.shift_counts == {}
        assert vars.undesirable_totals == {}

    def test_all_assignment_vars_empty(self) -> None:
        """all_assignment_vars returns empty iterator for empty variables."""
        vars = SolverVariables(
            assignment={},
            shift_counts={},
            undesirable_totals={},
        )
        assert list(vars.all_assignment_vars()) == []

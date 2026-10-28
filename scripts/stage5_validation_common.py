"""Спільні перевірки еквівалентності моделей для незалежних Stage 5 валідаторів."""

import json
from copy import deepcopy

EQUIVALENCE_FIELDS = ("n_spins", "boundary", "pauli_normalization", "time_unit", "coupling_unit", "hamiltonian_convention", "J_s^-1", "h_s^-1", "times_s")


def comparison_report(project_model: dict, reference_model: dict, differences: dict) -> dict:
    """Build a machine-readable independent-model comparison contract.

    A numerical comparison cannot pass as equivalent when model metadata differs.
    The function deliberately records mismatches instead of silently normalizing them.
    """
    if not all(isinstance(item, dict) for item in (project_model, reference_model, differences)):
        raise TypeError("models and differences must be dictionaries")
    missing_project = [key for key in EQUIVALENCE_FIELDS if key not in project_model]
    missing_reference = [key for key in EQUIVALENCE_FIELDS if key not in reference_model]
    mismatches = {
        key: {"project": project_model.get(key), "reference": reference_model.get(key)}
        for key in EQUIVALENCE_FIELDS
        if key in project_model and key in reference_model and project_model[key] != reference_model[key]
    }
    max_errors = {key: float(value) for key, value in differences.items() if key.startswith("max_")}
    if any(value < 0 or not __import__("math").isfinite(value) for value in max_errors.values()):
        raise ValueError("maximum numerical differences must be finite and nonnegative")
    return {
        "project_model": deepcopy(project_model),
        "reference_model": deepcopy(reference_model),
        "differences": deepcopy(differences),
        "model_mismatches": mismatches,
        "missing_metadata": {"project": missing_project, "reference": missing_reference},
        "equivalent_model": not mismatches and not missing_project and not missing_reference,
        "status": "pass" if not mismatches and not missing_project and not missing_reference and differences.get("passed", True) else "fail",
    }


def emit_report(report: dict) -> None:
    """Надрукувати JSON, за потреби зберегти його в args.output і завершити fail-кодом."""
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))

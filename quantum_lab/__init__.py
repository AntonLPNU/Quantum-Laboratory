"""Quantum Laboratory scientific API, version 0.5.0 Research Preview."""

__version__ = "0.5.0"

# Public Stage 5B surface. These modules use only the existing NumPy/SciPy
# runtime; QuTiP and QuSpin remain optional validation tools.
from .multispin import apply_subsystem_kraus
from .dynamic_receiver import prepare_dynamic_receiver_state, run_dynamic_receiver_experiment, trace_distance
from .deviation import (exact_observable_summary, fit_explicit_model, sample_observable,
                        sample_sequential_measurements, sequential_measurement_distribution,
                        spectrum_uniform_grid)
from .stage5b_statistics import (analyze_secondary_family, estimate_joint_power,
                                 fisher_exact_two_sided, holm_adjust, newcombe_wilson_interval)
from .stage5b_sampling import (analyze_primary_outcomes, lock_quantum_domino_protocol,
                               run_quantum_domino_primary_sampling, sample_blinded_outcomes,
                               verify_preregistration)
from .stage5b_experiments import (load_stage5b_configuration, run_stage5b_experiment,
                                  save_stage5b_experiment)

__all__ = ["__version__", "apply_subsystem_kraus", "prepare_dynamic_receiver_state",
           "run_dynamic_receiver_experiment", "trace_distance", "exact_observable_summary",
           "fit_explicit_model", "sample_observable", "sequential_measurement_distribution",
           "sample_sequential_measurements", "spectrum_uniform_grid", "fisher_exact_two_sided",
           "holm_adjust", "newcombe_wilson_interval", "estimate_joint_power",
           "analyze_secondary_family", "sample_blinded_outcomes", "analyze_primary_outcomes",
           "verify_preregistration", "lock_quantum_domino_protocol",
           "run_quantum_domino_primary_sampling", "run_stage5b_experiment", "save_stage5b_experiment"]
__all__.append("load_stage5b_configuration")

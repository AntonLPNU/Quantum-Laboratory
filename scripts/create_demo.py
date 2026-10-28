"""Regenerate deterministic demonstration experiment records."""
from pathlib import Path

from quantum_lab.experiments import run_chsh_experiment, run_signaling_experiment
from quantum_lab.storage import save_experiment


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "experiments"


def write_demo(results: dict, configuration: dict, stem: str) -> None:
    """Зберегти визначений демонстраційний запис JSON/CSV під стабільною назвою."""
    paths = save_experiment(results, configuration, OUTPUT)
    paths["json"].replace(OUTPUT / f"{stem}.json")
    paths["csv"].replace(OUTPUT / f"{stem}.csv")


def main() -> None:
    """Перегенерувати фіксовані no-signaling та CHSH приклади із зафіксованим seed."""
    write_demo(
        run_signaling_experiment(shots=100_000, seed=20261009),
        {"protocol": "signaling_control", "shots_per_sender_choice": 100_000, "seed": 20261009, "receiver_axis": [0, 0, 1]},
        "demo_no_signaling",
    )
    write_demo(
        run_chsh_experiment(shots_per_setting=10_000, seed=20261009),
        {"protocol": "chsh", "state_name": "singlet", "shots_per_setting": 10_000, "seed": 20261009},
        "demo_chsh",
    )
    print(f"Demo experiment records saved in {OUTPUT}")


if __name__ == "__main__":
    main()

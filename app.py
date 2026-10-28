"""Streamlit presentation layer. Physical calculations live in quantum_lab."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from quantum_lab.experiments import run_chsh_experiment, run_phase_damping_sweep, run_rotation_sweep, run_signaling_experiment, run_state_experiment
from quantum_lab.operations import PAULI
from quantum_lab.apparatus import simulate_binary_readout_correlations
from quantum_lab.scientific_validation import (
    analyze_hensen_2015, analyze_hensen_2016, analyze_no_signaling,
    combine_hensen_results, hensen_ideal_model_baseline,
)
from quantum_lab.storage import save_experiment


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data"
AXES = {"X": [1, 0, 0], "Y": [0, 1, 0], "Z": [0, 0, 1]}

st.set_page_config(page_title="Quantum Laboratory", page_icon="⚛️", layout="wide")


def bloch_vector(rho):
    """Повернути точні середні (⟨σx⟩, ⟨σy⟩, ⟨σz⟩) для 2×2 матриці кубіта."""
    return [float(np.trace(rho @ sigma).real) for sigma in PAULI]


def bloch_figure(rho_a, rho_b):
    """Створити Plotly-схему сфери Блоха з векторами, обчисленими з локальних станів."""
    phi = np.linspace(0, 2 * np.pi, 48)
    theta = np.linspace(0, np.pi, 32)
    x = np.outer(np.cos(phi), np.sin(theta))
    y = np.outer(np.sin(phi), np.sin(theta))
    z = np.outer(np.ones_like(phi), np.cos(theta))
    fig = go.Figure()
    fig.add_trace(go.Surface(x=x, y=y, z=z, opacity=0.12, showscale=False, colorscale=[[0, "#70a1ff"], [1, "#70a1ff"]], name="Bloch sphere", hoverinfo="skip"))
    colors = ["#ff6b6b", "#2ed573"]
    for label, rho, color in (("A", rho_a, colors[0]), ("B", rho_b, colors[1])):
        vector = bloch_vector(rho)
        fig.add_trace(go.Scatter3d(x=[0, vector[0]], y=[0, vector[1]], z=[0, vector[2]], mode="lines+markers", line={"width": 8, "color": color}, marker={"size": [2, 5], "color": color}, name=f"Spin {label}", text=["origin", f"{label}: {vector}"]))
    fig.update_layout(height=430, margin={"l": 0, "r": 0, "t": 10, "b": 0}, scene={"aspectmode": "cube", "xaxis_title": "X", "yaxis_title": "Y", "zaxis_title": "Z"}, legend={"orientation": "h"})
    return fig


def export_plot(fig, label, directory=None):
    """Експортувати фігуру у PNG/SVG з резервним Matplotlib-renderer, якщо потрібно."""
    folder = Path(directory) if directory is not None else OUT / "plots"
    folder.mkdir(parents=True, exist_ok=True)
    saved = []
    for kind in ("png", "svg"):
        path = folder / f"{label}.{kind}"
        try:
            path.write_bytes(fig.to_image(format=kind, scale=2 if kind == "png" else 1))
            saved.append(path)
        except Exception as exc:
            try:
                import matplotlib.pyplot as plt
                is_3d = any(getattr(trace, "type", "") in ("surface", "scatter3d") for trace in fig.data)
                figure = plt.figure(figsize=(7, 5), constrained_layout=True)
                axis = figure.add_subplot(111, projection="3d" if is_3d else None)
                for trace in fig.data:
                    trace_type = getattr(trace, "type", "")
                    if trace_type == "bar" and not is_3d:
                        axis.bar([str(value) for value in trace.x], trace.y, alpha=0.72, label=trace.name or None)
                    elif trace_type == "scatter" and not is_3d:
                        axis.plot(trace.x, trace.y, marker="o" if trace.mode and "markers" in trace.mode else None, label=trace.name or None)
                    elif trace_type == "heatmap" and not is_3d:
                        mesh = axis.pcolormesh(np.asarray(trace.x), np.asarray(trace.y), np.asarray(trace.z), shading="auto", cmap="viridis")
                        figure.colorbar(mesh, ax=axis, label=trace.colorbar.title.text if trace.colorbar.title else "")
                    elif trace_type == "surface" and is_3d:
                        axis.plot_surface(np.asarray(trace.x), np.asarray(trace.y), np.asarray(trace.z), alpha=0.12, color="#70a1ff", linewidth=0)
                    elif trace_type == "scatter3d" and is_3d:
                        axis.plot(trace.x, trace.y, trace.z, linewidth=3, label=trace.name or None)
                if fig.layout.title and fig.layout.title.text:
                    axis.set_title(fig.layout.title.text)
                if fig.layout.xaxis.title and fig.layout.xaxis.title.text:
                    axis.set_xlabel(fig.layout.xaxis.title.text)
                if fig.layout.yaxis.title and fig.layout.yaxis.title.text:
                    axis.set_ylabel(fig.layout.yaxis.title.text)
                if is_3d:
                    axis.set_zlabel("Z")
                if any(getattr(trace, "name", None) for trace in fig.data):
                    axis.legend(loc="best")
                figure.savefig(path, dpi=180 if kind == "png" else 120, format=kind)
                plt.close(figure)
                saved.append(path)
            except Exception as fallback_exc:
                st.warning(f"Не вдалося експортувати {kind.upper()}: {exc}; резервний рендерер: {fallback_exc}")
    return saved


def phase_damping_figures(sweep):
    """Build presentation-only plots from numerical results produced by the core."""
    values = {
        "concurrence": (sweep["concurrence"], "Concurrence C"),
        "chsh_maximal": (sweep["chsh_maximal"], "Оптимізований CHSH Sₘₐₓ"),
        "chsh_fixed": (sweep["chsh_fixed"], "CHSH для фіксованих осей"),
        **{f"correlation_{name}": (grid, f"Спільна кореляція E({name[0].upper()},{name[1].upper()})") for name, grid in sweep["joint_correlations"].items()},
        "local_probability_plus_a": ([[point[1] for point in row] for row in sweep["local_probabilities_a"]], "Локальна P(A=+1)"),
        "local_probability_plus_b": ([[point[1] for point in row] for row in sweep["local_probabilities_b"]], "Локальна P(B=+1)"),
        "local_expectation_a": (sweep["local_expectations"]["a"], "Локальне ⟨σ⟩ A"),
        "local_expectation_b": (sweep["local_expectations"]["b"], "Локальне ⟨σ⟩ B"),
    }
    figures = {}
    for name, (grid, title) in values.items():
        figure = go.Figure(go.Heatmap(
            x=sweep["lambdas_b"], y=sweep["lambdas_a"], z=np.asarray(grid, dtype=float),
            colorbar={"title": title}, hovertemplate="λ_A=%{y:.2f}<br>λ_B=%{x:.2f}<br>%{z:.5f}<extra></extra>",
        ))
        figure.update_layout(title=title, xaxis_title="Фазове затухання λ_B", yaxis_title="Фазове затухання λ_A", height=400)
        figures[name] = figure
    return figures


st.title("⚛️ Quantum Laboratory")
st.caption("Ідеальна модель двох електронних спінів ½. Це чисельний стенд для перевірки моделі, а не відтворення конкретної експериментальної установки.")

with st.sidebar:
    st.header("Параметри")
    upload = st.file_uploader("Завантажити конфігурацію експерименту (JSON)", type=["json"])
    if upload is not None:
        try:
            parsed = json.loads(upload.getvalue().decode("utf-8"))
            config = parsed.get("configuration", parsed)
            if st.button("Застосувати конфігурацію"):
                st.session_state["loaded_config"] = config
                st.rerun()
            st.caption("Конфігурацію прочитано. Натисніть кнопку, щоб застосувати її.")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            st.error(f"Не вдалося прочитати JSON: {exc}")

    loaded = st.session_state.get("loaded_config", {})
    if loaded:
        for key in ("state_name", "rotation_axis_a", "rotation_axis_b", "measurement_axis_a", "measurement_axis_b", "shots", "seed", "angle_a_deg", "angle_b_deg", "lambda_a", "lambda_b", "damping_grid_points", "damping_plot"):
            if key in loaded and key not in st.session_state:
                st.session_state[key] = loaded[key]
    state_name = st.selectbox("Початковий стан", ["singlet", "phi+", "phi-", "psi+"], key="state_name")
    rotation_axis_a = st.selectbox("Вісь обертання A", list(AXES), key="rotation_axis_a")
    angle_a_deg = st.slider("Кут A (градуси)", -360, 360, 0, key="angle_a_deg")
    rotation_axis_b = st.selectbox("Вісь обертання B", list(AXES), key="rotation_axis_b")
    angle_b_deg = st.slider("Кут B (градуси)", -360, 360, 0, key="angle_b_deg")
    measurement_axis_a = st.selectbox("Вісь вимірювання A", list(AXES), index=2, key="measurement_axis_a")
    measurement_axis_b = st.selectbox("Вісь вимірювання B", list(AXES), index=2, key="measurement_axis_b")
    lambda_a = st.slider("Фазове затухання електрона A (λ_A)", 0.0, 1.0, 0.0, 0.01, key="lambda_a")
    lambda_b = st.slider("Фазове затухання електрона B (λ_B)", 0.0, 1.0, 0.0, 0.01, key="lambda_b")
    damping_grid_points = st.slider("Точок на вісь sweep", min_value=3, max_value=51, value=21, step=2, key="damping_grid_points")
    shots = st.number_input("Повторення", min_value=100, max_value=1_000_000, value=10_000, step=100, key="shots")
    seed = st.number_input("Seed генератора випадкових чисел", min_value=0, max_value=2**31 - 1, value=42, step=1, key="seed")

rotation_config = {
    "a": {"axis": AXES[rotation_axis_a], "angle_rad": float(np.deg2rad(angle_a_deg))},
    "b": {"axis": AXES[rotation_axis_b], "angle_rad": float(np.deg2rad(angle_b_deg))},
}
configuration = {
    "protocol": "state_measurement", "state_name": state_name,
    "rotation_axis_a": rotation_axis_a, "angle_a_deg": angle_a_deg,
    "rotation_axis_b": rotation_axis_b, "angle_b_deg": angle_b_deg,
    "measurement_axis_a": measurement_axis_a, "measurement_axis_b": measurement_axis_b,
    "lambda_a": float(lambda_a), "lambda_b": float(lambda_b),
    "shots": int(shots), "seed": int(seed),
}
if st.button("Виконати вимірювання", type="primary") or "current_result" not in st.session_state:
    st.session_state["current_result"] = run_state_experiment(
        state_name, rotation_config, AXES[measurement_axis_a], AXES[measurement_axis_b], int(shots), int(seed),
        dephasing_a=float(lambda_a), dephasing_b=float(lambda_b),
    )
    st.session_state.setdefault("history", []).append(st.session_state["current_result"])

result = st.session_state["current_result"]
tab_overview, tab_bell, tab_damping, tab_signal, tab_time, tab_history, tab_validation, tab_sources = st.tabs(
    ["Огляд", "Белл / CHSH", "Фазове затухання", "No-signaling", "Еволюція", "Запуски та експорт", "Наукова валідація", "Джерела й обмеження"]
)

with tab_overview:
    st.subheader("Локальні та спільні результати")
    st.caption("Ідеальні ймовірності отримані з правила Борна; вибіркові частоти — з заданої кількості стохастичних вимірювань.")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Кореляція E", f"{result['correlator']:.4f}")
    c2.metric("Concurrence", f"{result['concurrence']:.4f}")
    c3.metric("CHSH для фіксованих осей", f"{result['chsh_fixed']:.4f}")
    c4.metric("Оптимізований CHSH Sₘₐₓ", f"{result['chsh_maximal']:.4f}")
    c5.metric("Ентропія стану (біт)", f"{result['global_entropy_bits']:.4f}")
    labels = list(result["joint_probabilities"])
    chart = go.Figure()
    chart.add_bar(name="Теорія", x=labels, y=[result["joint_probabilities"][k] for k in labels], marker_color="#70a1ff")
    chart.add_bar(name="Частота", x=labels, y=[result["joint_counts"][k] / int(shots) for k in labels], marker_color="#ff9f43")
    chart.update_layout(barmode="group", height=340, xaxis_title="Результати A, B (±1)", yaxis_title="Імовірність / відносна частота", legend={"orientation": "h"})
    st.plotly_chart(chart, width="stretch")
    st.subheader("Локальні матриці густини — сфери Блоха")
    local = result["reduced_density_matrices"]
    fig_bloch = bloch_figure(np.asarray(local["a"]), np.asarray(local["b"]))
    st.plotly_chart(fig_bloch, width="stretch")
    columns = st.columns(2)
    columns[0].code("ρ_A =\n" + np.array2string(np.asarray(local["a"]), precision=4))
    columns[1].code("ρ_B =\n" + np.array2string(np.asarray(local["b"]), precision=4))
    st.write("Діагностика матриці густини:", result["diagnostics"])
    if st.button("Зберегти графіки огляду як PNG і SVG"):
        paths = export_plot(chart, "joint_probabilities") + export_plot(fig_bloch, "bloch_spheres")
        st.success("Збережено: " + (", ".join(str(path.relative_to(ROOT)) for path in paths) if paths else "жодного файлу"))

with tab_bell:
    st.subheader("Вибірковий тест CHSH")
    st.markdown("Для кожної з чотирьох пар локальних осей збираються окремі вибірки. Межа локальних прихованих змінних — **2**; квантова межа цієї моделі — **2√2**.")
    chsh_shots = st.number_input("Пострілів на пару осей", 100, 100_000, 5000, 100, key="chsh_shots")
    if st.button("Запустити CHSH вибірку"):
        st.session_state["chsh_result"] = run_chsh_experiment(
            state_name, int(chsh_shots), int(seed), dephasing_a=float(lambda_a), dephasing_b=float(lambda_b), rotations=rotation_config
        )
    if "chsh_result" in st.session_state:
        chsh = st.session_state["chsh_result"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Фіксоване S для осей CHSH", f"{chsh['chsh_fixed']:.4f}")
        col2.metric("Оптимізоване Sₘₐₓ", f"{chsh['chsh_maximal']:.4f}")
        col3.metric("Вибіркове S для цих осей", f"{chsh['sampled_chsh']:.4f}", delta=f"{chsh['sampled_chsh'] - chsh['chsh_fixed']:+.4f} від фіксованої теорії")
        st.caption(f"Орієнтовна 95% статистична невизначеність вибіркового S: ±{1.96 * chsh['sampled_chsh_standard_error']:.4f} (незалежні вибірки чотирьох пар налаштувань).")
        names = list(chsh["settings"])
        fig = go.Figure()
        fig.add_bar(name="Теорія", x=names, y=[chsh["settings"][n]["theoretical_correlation"] for n in names])
        fig.add_bar(name="Вибірка", x=names, y=[chsh["settings"][n]["sampled_correlation"] for n in names])
        fig.update_layout(barmode="group", yaxis_title="E(a,b)", height=360)
        st.plotly_chart(fig, width="stretch")
        st.json(chsh["settings"])
        st.info("Цей симульований тест не моделює просторове розділення, випадковість вибору налаштувань, ефективність детекторів чи інші loopholes установки Hensen et al.")
        if st.button("Зберегти CHSH результат"):
            cfg = {**configuration, "protocol": "chsh", "shots_per_setting": int(chsh_shots)}
            paths = save_experiment(chsh, cfg, OUT / "experiments")
            st.success(f"Збережено {paths['json'].name} і {paths['csv'].name}")

with tab_damping:
    st.subheader("Незалежне фазове затухання електронів A та B")
    st.markdown("Кожна точка обчислюється ядром із двома локальними каналами Крауса на повній матриці **ρ_AB**. Спільні кореляції та заплутаність беруться з повного стану, локальні ймовірності — з його редукцій **ρ_A** та **ρ_B**. Канал діє в лабораторному Z-базисі після заданих локальних обертань.")
    damping_sweep = run_phase_damping_sweep(
        state_name,
        values_a=np.linspace(0.0, 1.0, int(damping_grid_points)),
        values_b=np.linspace(0.0, 1.0, int(damping_grid_points)),
        axis_a=AXES[measurement_axis_a], axis_b=AXES[measurement_axis_b], seed=int(seed), rotations=rotation_config,
    )
    if damping_sweep["analytic_reference_applies"]:
        st.latex(r"q=(1-\lambda_A)(1-\lambda_B),\quad C=q,\quad S_{\max}=2\sqrt{1+q^2}")
        st.caption("S_max оптимізується за всіма локальними осями. S_fixed на карті нижче використовує окремий фіксований набір осей CHSH у площині XY.")
    elif state_name == "singlet":
        st.info("Для цієї сітки ввімкнено локальні обертання перед Z-базисними каналами; еталони C=q та S_max=2√(1+q²) для незміненого singlet тут не застосовуються. Значення обчислені повним ядром.")
    damping_figures = phase_damping_figures(damping_sweep)
    damping_labels = {
        "concurrence": "Concurrence C", "chsh_maximal": "CHSH оптимізований S_max",
        "chsh_fixed": "CHSH для фіксованих осей",
        **{f"correlation_{a}{b}": f"Спільна кореляція E({a.upper()},{b.upper()})" for a in "xyz" for b in "xyz"},
        "local_probability_plus_a": "Локальна ймовірність P(A=+1)",
        "local_probability_plus_b": "Локальна ймовірність P(B=+1)",
        "local_expectation_a": "Локальне середнє ⟨σ⟩ A", "local_expectation_b": "Локальне середнє ⟨σ⟩ B",
    }
    selected_damping_plot = st.selectbox("Показник на 2D-карті", list(damping_labels), format_func=lambda key: damping_labels[key], key="damping_plot")
    st.plotly_chart(damping_figures[selected_damping_plot], width="stretch")
    if damping_sweep["analytic_reference_applies"]:
        concurrence_error = float(np.max(np.abs(np.asarray(damping_sweep["concurrence"]) - np.asarray(damping_sweep["analytic_singlet_concurrence"]))))
        chsh_error = float(np.max(np.abs(np.asarray(damping_sweep["chsh_maximal"]) - np.asarray(damping_sweep["analytic_singlet_chsh_maximal"]))))
        st.caption(f"Максимальна похибка на sweep-сітці щодо аналітичних C=q та S_max: ΔC={concurrence_error:.2e}, ΔS_max={chsh_error:.2e}.")
    st.caption("Параметри λ безрозмірні та феноменологічні; їх не калібровано під конкретну установку. Sweep точний і детермінований, без скінченної вибірки.")
    if st.button("Зберегти всі результати й графіки phase-damping sweep"):
        experiment_directory = OUT / "experiments"
        plot_directory = experiment_directory / "plots" / f"phase_damping_{uuid4().hex[:12]}"
        plot_artifacts = {}
        for plot_name, figure in damping_figures.items():
            saved_paths = export_plot(figure, plot_name, plot_directory)
            plot_artifacts[plot_name] = [str(path.relative_to(experiment_directory)) for path in saved_paths]
        recorded_results = {**damping_sweep, "plotly_figures": {name: figure.to_json() for name, figure in damping_figures.items()}}
        sweep_configuration = {
            "protocol": "phase_damping_sweep", "state_name": state_name,
            "lambda_a_grid": np.asarray(damping_sweep["lambdas_a"]).tolist(),
            "lambda_b_grid": np.asarray(damping_sweep["lambdas_b"]).tolist(),
            "measurement_axis_a": measurement_axis_a, "measurement_axis_b": measurement_axis_b,
            "lambda_a": float(lambda_a), "lambda_b": float(lambda_b), "damping_grid_points": int(damping_grid_points),
            "rotation_axis_a": rotation_axis_a, "angle_a_deg": int(angle_a_deg),
            "rotation_axis_b": rotation_axis_b, "angle_b_deg": int(angle_b_deg),
            "seed": int(seed), "selected_plot": selected_damping_plot,
        }
        paths = save_experiment(recorded_results, sweep_configuration, experiment_directory, artifacts=plot_artifacts)
        st.success(f"Запис збережено: {paths['json'].name}; CSV: {paths['csv'].name}; файли графіків: {sum(map(len, plot_artifacts.values()))}.")

with tab_signal:
    st.subheader("Чи кодує локальна операція A інформацію в локальних вимірюваннях B?")
    st.markdown("Передавач вибирає одну з двох локальних унітарних операцій A. Приймачеві передається тільки результат власного вимірювання B; результати A до декодера не надходять.")
    signal_shots = st.number_input("Пострілів на біт передавача", 100, 1_000_000, 20_000, 100, key="signal_shots")
    if st.button("Запустити контроль передавання"):
        st.session_state["signal_result"] = run_signaling_experiment(int(signal_shots), int(seed), AXES[measurement_axis_b])
    if "signal_result" in st.session_state:
        signal = st.session_state["signal_result"]
        c1, c2 = st.columns(2)
        c1.metric("Точність декодування", f"{signal['decoding_accuracy']:.4f}", delta=f"±{1.96*signal['decoding_standard_error']:.4f} (95% масштаб SE)")
        c2.metric("Очікувана точність без сигналу", "0.5000")
        bits = list(signal["receiver_counts"])
        figure = go.Figure()
        for outcome, label in (("-1", "B: −1"), ("+1", "B: +1")):
            figure.add_bar(name=label, x=bits, y=[signal["receiver_counts"][bit][outcome] / int(signal_shots) for bit in bits])
        figure.update_layout(barmode="group", xaxis_title="Вибір передавача (аналітичне групування)", yaxis_title="Локальна відносна частота B", height=350)
        st.plotly_chart(figure, width="stretch")
        st.json({k: v for k, v in signal.items() if k != "created_at_utc"})
        st.info("Групування за вибраним бітом доступне досліднику для порівняння. Сам приймач бачить лише послідовність своїх результатів і не має цих міток.")
        if st.button("Зберегти no-signaling результат"):
            cfg = {"protocol": "signaling_control", "shots_per_sender_choice": int(signal_shots), "seed": int(seed), "receiver_axis": AXES[measurement_axis_b]}
            paths = save_experiment(signal, cfg, OUT / "experiments")
            st.success(f"Збережено {paths['json'].name} і {paths['csv'].name}")

with tab_time:
    st.subheader("Ідеальна еволюція під дією обертання спіну A")
    st.caption("U(t)=exp(−i ωt n·σ/2). Для фізичних секунд введіть ω у рад/с. Це ізольована когерентна модель без шуму середовища.")
    col1, col2, col3 = st.columns(3)
    end_time = col1.number_input("Кінцевий час (с)", 0.01, 100.0, 6.283, 0.1, key="sweep_time")
    omega = col2.number_input("Кутова частота ω (рад/с)", -100.0, 100.0, 1.0, 0.1, key="sweep_omega")
    sweep_axis = col3.selectbox("Вісь обертання", list(AXES), key="sweep_axis")
    sweep = run_rotation_sweep(np.linspace(0, end_time, 101), state_name=state_name, axis=AXES[sweep_axis], angular_frequency_rad_s=omega, measurement_axis_a=AXES[measurement_axis_a], measurement_axis_b=AXES[measurement_axis_b])
    time_fig = go.Figure()
    time_fig.add_scatter(x=sweep["times"], y=sweep["correlations"], mode="lines", name="Спільна кореляція A-B")
    time_fig.add_scatter(x=sweep["times"], y=sweep["local_expectation_a"], mode="lines", name="Локальне ⟨σ⟩ A")
    time_fig.update_layout(xaxis_title="Час (с)", yaxis_title="Очікуване значення", yaxis_range=[-1.05, 1.05], height=390)
    st.plotly_chart(time_fig, width="stretch")
    st.caption("Локальна ймовірність B не змінюється в цій моделі; локальна унітарна операція A змінює кореляцію, а не віддалений локальний стан.")
    if st.button("Зберегти графік еволюції"):
        paths = export_plot(time_fig, "rotation_sweep")
        st.success("Збережено: " + (", ".join(str(path.relative_to(ROOT)) for path in paths) if paths else "жодного файлу"))

with tab_history:
    st.subheader("Історія й відтворюваний експорт")
    history = st.session_state.get("history", [])
    st.write(f"У поточній сесії: {len(history)} запуск(и).")
    if len(history) >= 2:
        h1, h2 = history[-2], history[-1]
        st.dataframe({"метрика": ["E", "CHSH", "concurrence"], "попередній запуск": [h1["correlator"], h1["chsh_maximal_axes_value"], h1["concurrence"]], "поточний запуск": [h2["correlator"], h2["chsh_maximal_axes_value"], h2["concurrence"]]}, width="stretch", hide_index=True)
    if st.button("Зберегти поточний експеримент у JSON і CSV"):
        paths = save_experiment(result, configuration, OUT / "experiments")
        st.session_state["last_saved"] = paths
    if "last_saved" in st.session_state:
        paths = st.session_state["last_saved"]
        st.success(f"Збережено в data/experiments/{paths['json'].name} та {paths['csv'].name}")
        st.download_button("Завантажити JSON", paths["json"].read_bytes(), paths["json"].name, "application/json")
        st.download_button("Завантажити CSV", paths["csv"].read_bytes(), paths["csv"].name, "text/csv")
    st.write("Конфігурацію можна повторно завантажити через поле зліва.")

with tab_sources:
    st.subheader("Реєстр наукових джерел")
    st.markdown("""
- **SRC-001 — Hensen et al. (2015), Nature 526, 682–686.** Реальний event-ready тест CHSH із віддаленими електронними спінами; у статті повідомлено S=2.42±0.20 за 245 спроб. [Nature, DOI 10.1038/nature15759](https://doi.org/10.1038/nature15759). Установка тут не відтворюється.
- **SRC-002 — Koppens et al. (2006), Nature 442, 766–771.** Експериментальні когерентні обертання електронного спіну й осциляції Рабі в подвійній квантовій точці. [Nature, DOI 10.1038/nature05065](https://doi.org/10.1038/nature05065). Інтерфейсні обертання — ідеальні унітарні операції, а не параметрична модель конкретного пристрою.
- **SRC-003 — Simon, Bužek & Gisin (2001), PRL 87, 170405.** Обговорює зв’язок лінійних повністю позитивних відображень і умови no-signaling. [APS, DOI 10.1103/PhysRevLett.87.170405](https://doi.org/10.1103/PhysRevLett.87.170405).
- **SRC-004 — QuTiP documentation.** Документація tensor products і partial trace. Ядро використовує прозорі операції NumPy, тому QuTiP не є runtime-залежністю. [QuTiP tensor guide](https://qutip.readthedocs.io/en/stable/guide/guide-tensor.html).
- **SRC-005 — NIST/CODATA 2022.** Електронне гіромагнітне відношення γₑ=1.76085962784(55)×10¹¹ s⁻¹ T⁻¹ наведено для довідки; у першій версії симулятора воно не використовується для підгонки параметрів. [NIST value](https://physics.nist.gov/cgi-bin/cuu/Value?gammae%7Csearch_for=electron-neutron).
- **SRC-006 — Nielsen & Chuang, *Quantum Computation and Quantum Information* (Cambridge University Press, 2000).** Стандартне джерело для матриць густини, вимірювань і CHSH. [Cambridge University Press](https://www.cambridge.org/highereducation/books/quantum-computation-and-quantum-information/01E10196D0A682A6AEFFEA52D53BE9AE).
- **SRC-007 — Wootters (1998), PRL 80, 2245.** Першоджерело для concurrence двокубітного стану. [APS, DOI 10.1103/PhysRevLett.80.2245](https://doi.org/10.1103/PhysRevLett.80.2245).

### Припущення і межі

Стан описано матрицею густини двох спінів ½; результати вимірювань обчислюються правилом Борна. Обертання використовують U=exp(−iθ n·σ/2). Спільні результати — ідеальні проєктивні вимірювання. Немає декогеренції, шуму, втрат, просторово-часової моделі, похибок керування чи детекторів. Зміни локального унітарного керування A зберігають редуковану матрицю B; це випливає з реалізованої лінійної квантової динаміки й перевіряється тестами, а не програмною гілкою, що примусово блокує сигнал.
""")
    st.warning("Симуляція не є свідченням нового фізичного явища. Будь-яке відхилення потрібно спершу перевіряти незалежним розрахунком, збіжністю, кодом і фізичними припущеннями.")

with tab_validation:
    st.subheader("Hensen 2015 / 2016: незалежне відтворення та статистична перевірка")
    experiment = st.radio("Оберіть незалежний набір даних", ["Hensen 2015", "Hensen 2016"], horizontal=True)
    data_2015 = ROOT / "data" / "references" / "hensen_2015" / "original_files" / "bell_open_data.txt"
    data_2016_dir = ROOT / "data" / "references" / "hensen_2016" / "original_files"
    old_apd = data_2016_dir / "bell_open_data_2_old_detector.txt"
    new_apd = data_2016_dir / "bell_open_data_2_new_detector.txt"
    result_2015 = analyze_hensen_2015(data_2015)
    result_2016 = analyze_hensen_2016(old_apd, new_apd)
    combined = combine_hensen_results(result_2015, result_2016)
    validation = result_2015 if experiment.endswith("2015") else result_2016
    no_signaling = analyze_no_signaling(validation["trials"])

    if experiment.endswith("2015"):
        paper = {"S": 2.42, "SE": 0.20, "n": 245}
        with data_2015.open("r", encoding="ascii", newline="") as source:
            source_rows = list(csv.reader(source))
        st.markdown("[Hensen et al. (2015), Nature, DOI 10.1038/nature15759](https://doi.org/10.1038/nature15759) · [первинні дані, Figshare/4TU](https://figshare.com/articles/dataset/Loophole-free_Bell-inequality_violation_using_electron_spins_separated_by_1_3_kilometres/12703235/1)")
        st.caption("2015 аналіз використовує власні часові пороги та критерії автора; ψ− (синглет) і конфігурація пристрою 2015 року залишаються окремими від другого запуску.")
    else:
        paper = {"S": 2.35, "SE": 0.18, "n": 300}
        source_rows = []
        for file_path in (old_apd, new_apd):
            with file_path.open("r", encoding="ascii", newline="") as source:
                for row in csv.reader(source):
                    source_rows.append([file_path.name, *row])
        st.markdown("[Hensen et al. (2016), Scientific Reports, DOI 10.1038/srep30289](https://doi.org/10.1038/srep30289) · [первинні дані, Figshare/4TU, версія 1](https://figshare.com/articles/dataset/Loophole-free_Bell_test_using_electron_spins_in_diamond_second_experiment_and_additional_analysis/12694403)")
        st.caption("2016 дані аналізуються окремо: старий APD та замінний APD мають окремі SHA-256 і різні стартові пороги каналу 0 (різниця 700 ps). Використано вікна з авторського скрипту, включно зі скороченим вікном ψ+ для after-pulsing.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Спроби після фільтрів", str(validation["valid_trials"]))
    c2.metric("CHSH S з даних", f"{validation['chsh_s']:.4f} ± {validation['chsh_standard_error']:.4f}")
    p_value = validation.get("complete_p_value", validation.get("local_realist_p_value"))
    c3.metric("Повний авторський score p-value", f"{p_value:.5g}")
    c4.metric("Відтворення даних", validation["analysis_status"])

    if experiment.endswith("2016"):
        state_rows = []
        for state_name, state_result in validation["states"].items():
            state_rows.append({"Heralded стан": state_name, "N": state_result["valid_trials"],
                               "CHSH S": state_result["chsh_s"], "SE(S)": state_result["chsh_standard_error"],
                               "Перемоги": state_result["wins"], "Налаштування": state_result["setting_counts"]})
        st.markdown("#### Окремі heralded-стани")
        st.dataframe(state_rows, width="stretch", hide_index=True)

    names = ["00", "01", "10", "11"]
    ideal = hensen_ideal_model_baseline("singlet")
    figure = go.Figure()
    correlation_rows = []
    if experiment.endswith("2015"):
        figure.add_trace(go.Scatter(x=names, y=[validation["correlations"][name] for name in names], mode="markers",
                                    name="Сирі дані Hensen 2015",
                                    error_y={"type": "data", "array": [validation["correlation_standard_errors"][name] for name in names], "visible": True},
                                    marker={"size": 10, "color": "#ff9f43"}))
        figure.add_trace(go.Scatter(x=names, y=[ideal["correlations"][name] for name in names], mode="markers+lines",
                                    name="Ідеальний ψ− / singlet", marker={"size": 8, "color": "#70a1ff"}))
        for name in names:
            correlation_rows.append({"Стан": "psi_minus", "Налаштування": name,
                "N": validation["setting_counts"][name], "Кореляція": validation["correlations"][name],
                "SE": validation["correlation_standard_errors"][name],
                "Ідеальний baseline того самого стану": ideal["correlations"][name],
                "Різниця дані − baseline": validation["correlations"][name] - ideal["correlations"][name]})
    else:
        for state_name, color, bell_state_name in (("psi_minus", "#ff9f43", "singlet"), ("psi_plus", "#e056fd", "psi+")):
            state_result = validation["states"][state_name]
            figure.add_trace(go.Scatter(x=names, y=[state_result["correlations"][name] for name in names], mode="markers",
                                        name=f"Сирі дані {state_name}",
                                        error_y={"type": "data", "array": [state_result["correlation_standard_errors"][name] for name in names], "visible": True},
                                        marker={"size": 10, "color": color}))
            state_ideal = hensen_ideal_model_baseline("singlet") if state_name == "psi_minus" else None
            if state_ideal is not None:
                figure.add_trace(go.Scatter(x=names, y=[state_ideal["correlations"][name] for name in names], mode="lines",
                                            name="Ідеальний singlet reference", line={"dash": "dash"}))
            for name in names:
                ideal_value = None if state_ideal is None else state_ideal["correlations"][name]
                correlation_rows.append({"Стан": state_name, "Налаштування": name,
                    "N": state_result["setting_counts"][name], "Кореляція": state_result["correlations"][name],
                    "SE": state_result["correlation_standard_errors"][name],
                    "Ідеальний singlet baseline": ideal_value,
                    "Різниця дані − baseline": None if ideal_value is None else state_result["correlations"][name] - ideal_value})
    figure.update_layout(height=360, xaxis={"type": "category", "categoryorder": "array", "categoryarray": names,
                                             "title": "Пара налаштувань (a,b)"},
                         yaxis_title="Кореляція E(a,b)", yaxis_range=[-1.05, 1.05], legend={"orientation": "h"})
    st.plotly_chart(figure, width="stretch")
    st.caption("Для ψ− наведено singlet reference; ψ+ показано окремо без апаратного baseline, бо відповідність його знаків і базисів в Hensen setup ще не реалізована. Жодна різниця не є калібрувальною ціллю.")
    st.dataframe(correlation_rows, width="stretch", hide_index=True)

    st.markdown("#### Порівняння з публікацією та об'єднаний результат")
    compare_rows = [
        {"Набір": "Hensen 2015", "N": result_2015["valid_trials"], "S з даних": result_2015["chsh_s"],
         "SE": result_2015["chsh_standard_error"], "S публікації": 2.42, "SE публікації": 0.20},
        {"Набір": "Hensen 2016", "N": result_2016["valid_trials"], "S з даних": result_2016["chsh_s"],
         "SE": result_2016["chsh_standard_error"], "S публікації": 2.35, "SE публікації": 0.18},
        {"Набір": "2015 + 2016, зважено", "N": combined["total_trials"], "S з даних": combined["chsh_s"],
         "SE": combined["chsh_standard_error"], "S публікації": 2.38, "SE публікації": 0.14},
    ]
    st.dataframe(compare_rows, width="stretch", hide_index=True)
    mismatch = go.Figure()
    mismatch.add_bar(x=[row["Набір"] for row in compare_rows],
                     y=[row["S з даних"] - row["S публікації"] for row in compare_rows],
                     marker_color=["#2ed573" if abs(row["S з даних"] - row["S публікації"]) < row["SE публікації"] else "#ff6b6b" for row in compare_rows])
    mismatch.add_hline(y=0, line_dash="dash", line_color="white")
    mismatch.update_layout(height=260, yaxis_title="S з даних − S публікації", xaxis_title="Окремі експерименти / зважене об'єднання")
    st.plotly_chart(mismatch, width="stretch")
    st.write(f"Сумарний score: {combined['complete_p_value_trials'][0]}/{combined['total_trials']} перемог; p={combined['complete_p_value']:.5g}. У статті наведено single-test p=0.0080; інші методики об'єднання дають conventional p=0.0026 та Fisher p=0.017.")

    st.markdown("#### Запуск часткової моделі readout")
    st.caption("Це аналітичний симулятор лише локальних похибок призначення бінарного результату; він використовує ідеальні singlet кореляції як вхід і не моделює повний Hensen apparatus. Значення fidelity за замовчуванням 1.0, щоб не трактувати combined initialization/readout оцінки як чисте калібрування детектора.")
    fidelity_columns = st.columns(2)
    fidelity_a = fidelity_columns[0].number_input("Модельна assignment fidelity A", 0.0, 1.0, 1.0, 0.001, key="readout_fidelity_a")
    fidelity_b = fidelity_columns[1].number_input("Модельна assignment fidelity B", 0.0, 1.0, 1.0, 0.001, key="readout_fidelity_b")
    if st.button("Запустити аналітичний readout канал"):
        component = simulate_binary_readout_correlations(ideal["correlations"], float(fidelity_a), float(fidelity_b))
        st.session_state["readout_component_result"] = component
    if "readout_component_result" in st.session_state:
        component = st.session_state["readout_component_result"]
        st.dataframe([{"Налаштування": name, "Вхідна ідеальна кореляція": component["input_correlations"][name],
                       "Після локального assignment noise": component["correlations"][name]} for name in names],
                     width="stretch", hide_index=True)
        st.caption(f"Модель {component['model_version']} · метод: {component['numerical_method']} · attenuation={component['attenuation']:.6f} · seed={component['seed']} · статус: {component['status']}")
        if st.button("Зберегти параметри й результат каналу"):
            config = {"protocol": "binary_readout_component", "model_version": component["model_version"],
                      "fidelity_a": component["fidelity_a"], "fidelity_b": component["fidelity_b"],
                      "numerical_method": component["numerical_method"], "seed": component["seed"]}
            paths = save_experiment(component, config, OUT / "experiments")
            st.success(f"Збережено {paths['json'].name} та {paths['csv'].name}")

    st.markdown("#### No-signaling у локальних маргінальних частотах")
    st.write(f"Статус: **{no_signaling['status']}** · двосторонній Fisher exact, Holm family-wise α={no_signaling['family_alpha']:.2f}. Це conditional analysis для heralded/відфільтрованої вибірки.")
    ns_rows = []
    for item in no_signaling["tests"]:
        c0, c1 = item["conditional_frequencies"]
        ns_rows.append({"Стан": item["state"], "Сторона": item["party"],
                        "Локальне налаштування": item["local_setting"],
                        "Віддалене налаштування": item["remote_setting_name"],
                        "N(remote=0)": c0["n"], "P(+1|remote=0)": c0["plus_frequency"],
                        "95% Wilson, remote=0": c0["wilson_95"],
                        "N(remote=1)": c1["n"], "P(+1|remote=1)": c1["plus_frequency"],
                        "95% Wilson, remote=1": c1["wilson_95"],
                        "p": item["p_value"], "p Holm": item["holm_p_value"]})
    st.dataframe(ns_rows, width="stretch", hide_index=True)
    st.caption(no_signaling["interpretation"] + " " + no_signaling["communication_note"] + " Довірчі інтервали показують локальні маргінальні частоти; невідхилення не доводить відсутність ефекту. Тест не є memory-robust і тому статус залишається INCONCLUSIVE.")

    with st.expander("Переглянути первинні та відфільтровані записи"):
        st.caption(f"Первинні рядки: {len(source_rows)}. Вони відображаються зі збереженими сирими полями; підсумковий розбір використовує {validation['valid_trials']} прийнятих подій.")
        st.dataframe(source_rows, width="stretch", height=360, hide_index=True)
        st.dataframe(validation["trials"], width="stretch", height=360, hide_index=True)
    st.caption("SHA-256 набору: " + json.dumps(validation.get("source_sha256", validation.get("dataset_sha256")), ensure_ascii=False))

    st.markdown("#### Роздільні статуси та межі фізичної моделі")
    st.success(f"A. Математична перевірка: чинні аналітичні спінові операції проходять свої інваріантні тести. B. Відтворення сирих даних {experiment}: {validation['analysis_status']}.")
    st.warning("C. Валідація фізичної установки: NOT IMPLEMENTED. Реалізований лише окремий симетричний канал похибки binary assignment; він не моделює Heralding, NV-підготовку, керування, детекторну ефективність, втрати, часові умови або відбір повної установки. Збіг CHSH не може підтвердити повну модель.")
    st.markdown("**Обмежений фізичний компонент:** readout assignment channel застосовує локальне перевертання результату з імовірністю 1−F. Стаття Hensen 2015 повідомляє combined initialization+readout fidelity A=0.971±0.002 і B=0.963±0.003; це не окреме калібрування детектора, тому значення не підставляються у відтворення даних. Статус компонента — phenomenological, не device-validated.")
    st.markdown("**QuTiP / Lindblad:** розглянуто, але не запущено. Для фізично інформативного `mesolve` потрібні незалежно виміряні T1/T2, спектри шуму, driven Hamiltonian та pulse histories; набори Bell-подій цих калібрувань не містять. Додавати довільні rates зараз означало б вигадати параметри.")
    st.markdown("**Відмінності установок:** 2016 включає замінний APD із затримкою 700 ps на каналі 0, інший алгоритм RNG (додані класичні випадкові біти) та опубліковані state-dependent after-pulsing вікна. Вони збережені в окремих сирих файлах і фільтрах, а не перенесені з 2015.")
    with st.expander("Таблиця фізичних параметрів, одиниць, значень і джерел"):
        parameter_doc = ROOT / "docs" / "apparatus_parameters.md"
        st.markdown(parameter_doc.read_text(encoding="utf-8"))

    st.markdown("Джерела: [Hensen 2015, Nature](https://doi.org/10.1038/nature15759) · [Hensen 2016, Nature Scientific Reports](https://doi.org/10.1038/srep30289) · [Figshare/4TU 2016 dataset](https://doi.org/10.4121/uuid:53644d31-d862-4f9f-9ad2-0b571874b829) · [QuTiP master-equation guide](https://qutip.readthedocs.io/en/stable/guide/dynamics/dynamics-master.html). Методика no-signaling і критерії α зафіксовані до аналізу в docs/scientific_validation.md.")

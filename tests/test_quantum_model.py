"""Unit tests for the Quantum-Like Computational Model (src/models/quantum_model.py)."""

import math
from pathlib import Path
import numpy as np
import pytest

from src.models.quantum_model import (
    CognitiveState,
    MemeStimulus,
    apply_stimulus,
    construct_hamiltonian,
    compute_polarization_metric,
    compute_asymmetry_metric,
    run_simulation,
    run_classical_baseline,
    plot_simulation_results,
    SIGMA_X,
    SIGMA_Y,
    SIGMA_Z,
    IDENTITY_2,
)


# ==============================================================================
# 1. Tests for CognitiveState
# ==============================================================================

class TestCognitiveState:
    def test_default_initialization(self):
        """Default initialization should be the maximally mixed state."""
        state = CognitiveState()
        assert state.validate()
        assert np.isclose(state.p_pro, 0.5)
        assert np.isclose(state.p_contra, 0.5)
        assert np.isclose(state.belief_value, 0.0)
        assert np.isclose(state.coherence, 0.0)
        assert np.isclose(state.purity, 0.5)

    def test_pure_state_pro_and_contra(self):
        """Pure state |0> (pro) and |1> (contra) should have exact alignments."""
        pro_state = CognitiveState.from_pure_state(1.0, 0.0)
        assert pro_state.validate()
        assert np.isclose(pro_state.p_pro, 1.0)
        assert np.isclose(pro_state.p_contra, 0.0)
        assert np.isclose(pro_state.belief_value, 1.0)
        assert np.isclose(pro_state.purity, 1.0)
        assert np.isclose(pro_state.coherence, 0.0)

        contra_state = CognitiveState.from_pure_state(0.0, 1.0)
        assert contra_state.validate()
        assert np.isclose(contra_state.p_pro, 0.0)
        assert np.isclose(contra_state.p_contra, 1.0)
        assert np.isclose(contra_state.belief_value, -1.0)
        assert np.isclose(contra_state.purity, 1.0)

    def test_superposition_state(self):
        """Equal superposition state (|0> + |1>)/sqrt(2) has maximum coherence."""
        sup_state = CognitiveState.from_pure_state(1.0 / math.sqrt(2), 1.0 / math.sqrt(2))
        assert sup_state.validate()
        assert np.isclose(sup_state.p_pro, 0.5)
        assert np.isclose(sup_state.p_contra, 0.5)
        assert np.isclose(sup_state.belief_value, 0.0)
        assert np.isclose(sup_state.coherence, 0.5)
        assert np.isclose(sup_state.purity, 1.0)

    def test_from_belief(self):
        """Test constructing state directly from belief and coherence ratio."""
        state = CognitiveState.from_belief(belief=0.6, coherence_ratio=0.5, phase=np.pi / 4)
        assert state.validate()
        assert np.isclose(state.belief_value, 0.6, atol=1e-5)
        assert np.isclose(state.p_pro, 0.8, atol=1e-5)
        assert np.isclose(state.p_contra, 0.2, atol=1e-5)
        assert state.coherence > 0.0
        assert np.isclose(state.phase, np.pi / 4, atol=1e-5)

    def test_bloch_vector(self):
        """Bloch vector for |0> should be (0, 0, 1)."""
        state = CognitiveState.from_pure_state(1.0, 0.0)
        rx, ry, rz = state.to_bloch_vector()
        assert np.isclose(rx, 0.0, atol=1e-5)
        assert np.isclose(ry, 0.0, atol=1e-5)
        assert np.isclose(rz, 1.0, atol=1e-5)

    def test_entropy_properties(self):
        """Pure state has zero entropy; mixed state has positive entropy."""
        pure = CognitiveState.from_pure_state(1.0, 0.0)
        mixed = CognitiveState()
        assert pure.entropy < 1e-4
        assert mixed.entropy > 0.6  # ln(2) approx 0.693

    def test_matrix_validation_and_normalization(self):
        """Un-normalized or noisy matrices should be properly validated and repaired."""
        # Non-hermitian matrix
        non_hermitian = np.array([[0.7, 0.2], [0.1, 0.3]], dtype=complex)
        s = CognitiveState.__new__(CognitiveState)
        s.matrix = non_hermitian
        assert not s.validate()
        s.normalize()
        assert s.validate()

    def test_invalid_dimension_raises(self):
        """Passing non-2x2 matrices must raise ValueError."""
        with pytest.raises(ValueError, match="Density matrix must be 2x2"):
            CognitiveState(np.eye(3))


# ==============================================================================
# 2. Tests for MemeStimulus
# ==============================================================================

class TestMemeStimulus:
    def test_from_dict_defaults(self):
        """Test parsing a minimal meme dict."""
        data = {
            "id": "meme_101",
            "caption": "Meme politik pemilu seru!",
            "engagement": {"upvotes": 50, "score": 50},
        }
        stim = MemeStimulus.from_dict(data)
        assert stim.meme_id == "meme_101"
        assert 0.15 <= stim.coupling_strength <= 1.0
        assert -np.pi <= stim.phase_shift <= np.pi
        assert -1.0 <= stim.bias_direction <= 1.0

    def test_coupling_strength_increases_with_engagement(self):
        """Viral memes with higher upvotes must yield stronger coupling strength."""
        low_eng = MemeStimulus.from_dict({"engagement": {"upvotes": 0}})
        high_eng = MemeStimulus.from_dict({"engagement": {"upvotes": 10000}})
        assert high_eng.coupling_strength > low_eng.coupling_strength

    def test_toxic_label_phase_shift(self):
        """Toxic labeled memes should shift phase towards negative antagonism."""
        toxic_data = {
            "id": "meme_toxic",
            "caption": "GUOBLOOK ANAK TK JUGA TAU",
            "label": "Toxic",
            "confidence": 0.95,
            "engagement": {"upvotes": 10},
        }
        stim = MemeStimulus.from_dict(toxic_data)
        assert stim.bias_direction < 0.0
        assert stim.phase_shift < 0.0

    def test_load_from_jsonl(self, tmp_path):
        """Test loading from a jsonl file."""
        jsonl_file = tmp_path / "test_memes.jsonl"
        lines = [
            json_line({"id": "m1", "caption": "Capres hebat solusi maju", "engagement": {"upvotes": 20}}),
            json_line({"id": "m2", "caption": "Rezim korupsi rusak bobrok", "engagement": {"upvotes": 100}}),
        ]
        jsonl_file.write_text("\n".join(lines), encoding="utf-8")

        stimuli = MemeStimulus.load_from_jsonl(jsonl_file)
        assert len(stimuli) == 2
        assert stimuli[0].meme_id == "m1"
        assert stimuli[1].meme_id == "m2"


def json_line(d: dict) -> str:
    import json
    return json.dumps(d)


# ==============================================================================
# 3. Tests for Hamiltonian and apply_stimulus
# ==============================================================================

class TestApplyStimulus:
    def test_hamiltonian_hermiticity(self):
        """Cognitive Hamiltonian must always be Hermitian."""
        H = construct_hamiltonian(coupling_strength=0.7, phase_shift=1.2, bias_direction=-0.4)
        assert np.allclose(H, H.conj().T)

    def test_unitary_evolution_preserves_density_matrix_properties(self):
        """Unitary evolution must preserve Hermiticity, unit trace, and purity."""
        initial_state = CognitiveState.from_pure_state(0.8, 0.6)
        stim = MemeStimulus(
            meme_id="stim_1",
            coupling_strength=0.5,
            phase_shift=np.pi / 3,
            bias_direction=0.6,
        )
        evolved = apply_stimulus(initial_state, stim, time_step=1.0, method="unitary")
        assert evolved.validate()
        assert np.isclose(evolved.purity, 1.0, atol=1e-5)
        assert np.isclose(np.trace(evolved.matrix), 1.0, atol=1e-5)

    def test_lindblad_evolution_preserves_validity(self):
        """Lindblad evolution must produce a strictly valid physical density matrix."""
        initial_state = CognitiveState.from_belief(belief=0.0, coherence_ratio=0.4)
        stim = MemeStimulus(
            meme_id="stim_lindblad",
            coupling_strength=0.6,
            phase_shift=0.5,
            bias_direction=0.8,
        )
        evolved = apply_stimulus(
            initial_state,
            stim,
            time_step=1.0,
            method="lindblad",
            dephasing_rate=0.1,
            relaxation_rate=0.05,
        )
        assert evolved.validate()
        assert 0.0 <= evolved.p_pro <= 1.0
        assert 0.0 <= evolved.p_contra <= 1.0
        assert -1.0 <= evolved.belief_value <= 1.0

    def test_pro_stimulus_increases_pro_probability(self):
        """Exposure to strong pro-stimulus should increase belief value towards pro (+1)."""
        neutral = CognitiveState()
        pro_stim = MemeStimulus(
            meme_id="pro_stim",
            coupling_strength=0.8,
            phase_shift=0.1,
            bias_direction=0.9,
        )
        evolved = apply_stimulus(neutral, pro_stim, time_step=1.5, method="lindblad", relaxation_rate=0.1)
        assert evolved.belief_value > neutral.belief_value

    def test_contra_stimulus_decreases_pro_probability(self):
        """Exposure to strong contra-stimulus should decrease belief value towards contra (-1)."""
        neutral = CognitiveState()
        contra_stim = MemeStimulus(
            meme_id="contra_stim",
            coupling_strength=0.8,
            phase_shift=-0.1,
            bias_direction=-0.9,
        )
        evolved = apply_stimulus(neutral, contra_stim, time_step=1.5, method="lindblad", relaxation_rate=0.1)
        assert evolved.belief_value < neutral.belief_value

    def test_invalid_evolution_method(self):
        """Unknown method should raise ValueError."""
        neutral = CognitiveState()
        stim = MemeStimulus("m", 0.5, 0.0, 0.0)
        with pytest.raises(ValueError, match="Unknown evolution method"):
            apply_stimulus(neutral, stim, method="invalid_quantum_method")


# ==============================================================================
# 4. Tests for Polarization Metrics
# ==============================================================================

class TestPolarizationMetrics:
    def test_consensus_has_zero_polarization(self):
        """All agents with identical beliefs have zero polarization."""
        beliefs = np.array([0.5, 0.5, 0.5, 0.5])
        assert compute_polarization_metric(beliefs) == 0.0

    def test_extreme_polarization(self):
        """Bimodal split (+1 vs -1) has maximum polarization variance = 1.0."""
        beliefs = np.array([1.0, 1.0, -1.0, -1.0])
        assert np.isclose(compute_polarization_metric(beliefs), 1.0)
        assert np.isclose(compute_asymmetry_metric(beliefs), 2.0)


# ==============================================================================
# 5. Tests for Simulation and Classical Baseline End-to-End
# ==============================================================================

class TestSimulations:
    def test_run_simulation_synthetic(self):
        """Test running quantum simulation with synthetic inputs."""
        time_steps = 5
        results = run_simulation(
            text_data_path=None,
            meme_data_path=None,
            time_steps=time_steps,
            population_size=30,
            method="lindblad",
            random_seed=123,
        )
        assert len(results["time_steps"]) == time_steps + 1
        assert len(results["polarization"]) == time_steps + 1
        assert len(results["asymmetry"]) == time_steps + 1
        assert len(results["mean_coherence"]) == time_steps + 1
        assert results["agent_beliefs"].shape == (time_steps + 1, 30)

        # Polarization and asymmetry must be finite and >= 0
        for p in results["polarization"]:
            assert 0.0 <= p <= 1.0
        for a in results["asymmetry"]:
            assert a >= 0.0

    def test_run_classical_baseline_synthetic(self):
        """Test running classical Friedkin-Johnsen baseline."""
        time_steps = 5
        c_results = run_classical_baseline(
            text_data_path=None,
            meme_data_path=None,
            time_steps=time_steps,
            population_size=30,
            random_seed=123,
        )
        assert len(c_results["time_steps"]) == time_steps + 1
        assert len(c_results["polarization"]) == time_steps + 1
        assert len(c_results["asymmetry"]) == time_steps + 1
        assert c_results["agent_beliefs"].shape == (time_steps + 1, 30)

    def test_plot_simulation_results(self, tmp_path):
        """Test saving visualization to file."""
        time_steps = 3
        q_res = run_simulation(time_steps=time_steps, population_size=20, random_seed=42)
        c_res = run_classical_baseline(time_steps=time_steps, population_size=20, random_seed=42)

        out_img = tmp_path / "test_polarization.png"
        fig = plot_simulation_results(q_res, c_res, output_path=out_img)
        assert out_img.is_file()
        assert out_img.stat().st_size > 1000

    def test_run_simulation_with_real_files_if_exist(self):
        """Test run_simulation with actual data files from data/processed/."""
        posts_path = Path("data/processed/posts.jsonl")
        memes_path = Path("data/processed/memes.jsonl")
        if posts_path.is_file() and memes_path.is_file():
            res = run_simulation(
                text_data_path=posts_path,
                meme_data_path=memes_path,
                time_steps=4,
                population_size=40,
                method="lindblad",
            )
            assert len(res["polarization"]) == 5

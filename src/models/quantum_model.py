"""Quantum-Like Computational Model of Political Opinion Polarization.

This module implements a quantum-like cognitive dynamics framework to model
how exposure to political memes (infon probes) influences human belief states
and induces polarization.

Theoretical Basis:
- Cognitive state representation via 2D density matrices (rho) on Hilbert space H = C^2.
  |0> : Pro-stance (Support / Positive alignment)
  |1> : Contra-stance (Oppose / Negative alignment)
  Off-diagonal elements (rho_01) represent cognitive superposition & interference.
- Meme Stimuli as Infon Probes:
  - coupling_strength (g) parameterized by virality & social engagement (upvotes/likes).
  - phase_shift (phi) and detuning (Delta) parameterized by textual semantics & OCR/caption sentiment.
- Cognitive State Time Evolution:
  - Unitary evolution: rho(t + dt) = U rho(t) U^dagger via Hamiltonian driving.
  - Open quantum system evolution: Lindblad master equation incorporating
    cognitive dephasing (decoherence) and directional confirmation-bias relaxation.
- Polarization and Asymmetry Metrics:
  - Polarization: Dispersion / variance of belief expectations across the population.
  - Asymmetry: Ideological cluster separation between opposing camps.
  - Quantum Coherence: Residual cognitive superposition across the population.
- Classical Baseline:
  - Friedkin-Johnsen (FJ) opinion dynamics on the same network and stimulus sequence.
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
from scipy.linalg import expm

# ==============================================================================
# Pauli Matrices and Quantum Algebraic Primitives
# ==============================================================================

SIGMA_X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128)
SIGMA_Y = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=np.complex128)
SIGMA_Z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=np.complex128)
IDENTITY_2 = np.eye(2, dtype=np.complex128)

PRO_PROJECTION = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=np.complex128)
CONTRA_PROJECTION = np.array([[0.0, 0.0], [0.0, 1.0]], dtype=np.complex128)


# ==============================================================================
# 1. State Representation: CognitiveState
# ==============================================================================

class CognitiveState:
    """Represents an individual's political belief as a 2D density matrix.

    Basis states:
      |0>: Pro-stance (e.g. +1 alignment)
      |1>: Contra-stance (e.g. -1 alignment)

    Density Matrix:
      rho = [[rho_00, rho_01],
             [rho_10, rho_11]]
      where:
      - rho_00: P(Pro)
      - rho_11: P(Contra)
      - rho_01 = rho_10*: Quantum cognitive coherence / interference potential
      - Tr(rho) = 1, rho = rho^dagger, rho >= 0.
    """

    def __init__(self, matrix: Optional[Union[np.ndarray, List[List[complex]]]] = None):
        """Initialize a cognitive state with a 2x2 density matrix.

        If None, initializes to the maximally mixed (neutral/undecided) state rho = 0.5 * I.
        """
        if matrix is None:
            self.matrix = 0.5 * IDENTITY_2.copy()
        else:
            arr = np.asarray(matrix, dtype=np.complex128)
            if arr.shape != (2, 2):
                raise ValueError(f"Density matrix must be 2x2, got shape {arr.shape}")
            self.matrix = arr.copy()
            self.normalize()

    def validate(self, tol: float = 1e-5) -> bool:
        """Validate density matrix axioms (Hermiticity, unit trace, positive semi-definite)."""
        # 1. Hermiticity
        if not np.allclose(self.matrix, self.matrix.conj().T, atol=tol):
            return False
        # 2. Unit trace
        if abs(np.trace(self.matrix) - 1.0) > tol:
            return False
        # 3. Positive semi-definite
        eigvals = np.linalg.eigvalsh(self.matrix)
        if any(ev < -tol for ev in eigvals):
            return False
        return True

    def normalize(self) -> None:
        """Project and normalize the matrix into a valid physical density matrix."""
        # Enforce Hermiticity
        self.matrix = 0.5 * (self.matrix + self.matrix.conj().T)
        
        # Enforce positive semi-definiteness via eigenvalue decomposition
        eigvals, eigvecs = np.linalg.eigh(self.matrix)
        eigvals = np.maximum(eigvals, 0.0)
        total_trace = np.sum(eigvals)
        if total_trace <= 1e-12:
            eigvals = np.array([0.5, 0.5], dtype=np.float64)
            total_trace = 1.0
        eigvals /= total_trace
        self.matrix = (eigvecs * eigvals) @ eigvecs.conj().T
        # Final trace assurance
        self.matrix /= np.trace(self.matrix)

    @property
    def p_pro(self) -> float:
        """Probability of holding the Pro stance P(|0>)."""
        return float(np.real(self.matrix[0, 0]))

    @property
    def p_contra(self) -> float:
        """Probability of holding the Contra stance P(|1>)."""
        return float(np.real(self.matrix[1, 1]))

    @property
    def belief_value(self) -> float:
        """Net political alignment in range [-1.0, 1.0].

        +1.0: 100% Pro-stance (|0><0|)
        -1.0: 100% Contra-stance (|1><1|)
         0.0: Perfectly balanced / ambivalent
        """
        return float(np.real(self.matrix[0, 0] - self.matrix[1, 1]))

    @property
    def coherence(self) -> float:
        """Off-diagonal cognitive coherence magnitude |rho_01| in [0.0, 0.5]."""
        return float(np.abs(self.matrix[0, 1]))

    @property
    def phase(self) -> float:
        """Phase angle of cognitive coherence in [-pi, pi]."""
        return float(np.angle(self.matrix[0, 1]))

    @property
    def purity(self) -> float:
        """Quantum state purity gamma = Tr(rho^2) in [0.5, 1.0]."""
        return float(np.real(np.trace(self.matrix @ self.matrix)))

    @property
    def entropy(self) -> float:
        """Von Neumann entropy S(rho) = -sum(lambda_i * ln(lambda_i))."""
        eigvals = np.linalg.eigvalsh(self.matrix)
        eigvals = np.maximum(eigvals, 1e-12)
        return float(-np.sum(eigvals * np.log(eigvals)))

    def to_bloch_vector(self) -> Tuple[float, float, float]:
        """Convert density matrix to Bloch sphere coordinates (rx, ry, rz)."""
        rx = float(np.real(np.trace(self.matrix @ SIGMA_X)))
        ry = float(np.real(np.trace(self.matrix @ SIGMA_Y)))
        rz = float(np.real(np.trace(self.matrix @ SIGMA_Z)))
        return (rx, ry, rz)

    def copy(self) -> CognitiveState:
        """Return a deep copy of the cognitive state."""
        return CognitiveState(self.matrix.copy())

    @classmethod
    def from_pure_state(cls, c0: complex, c1: complex) -> CognitiveState:
        """Create a pure cognitive state from state vector |psi> = c0|0> + c1|1>."""
        norm = math.sqrt(abs(c0)**2 + abs(c1)**2)
        if norm <= 1e-12:
            raise ValueError("State vector norm cannot be zero")
        c0_norm = c0 / norm
        c1_norm = c1 / norm
        psi = np.array([[c0_norm], [c1_norm]], dtype=np.complex128)
        rho = psi @ psi.conj().T
        return cls(rho)

    @classmethod
    def from_belief(
        cls,
        belief: float,
        coherence_ratio: float = 0.0,
        phase: float = 0.0,
    ) -> CognitiveState:
        """Construct a state from a belief value in [-1.0, 1.0].

        Args:
            belief: Desired alignment in [-1.0, 1.0] (pro=+1, contra=-1).
            coherence_ratio: Fraction [0.0, 1.0] of maximum allowable coherence
                             sqrt(p0 * p1) preserved as superposition.
            phase: Phase angle phi in radians [-pi, pi].
        """
        b = float(np.clip(belief, -1.0, 1.0))
        p0 = (1.0 + b) / 2.0
        p1 = (1.0 - b) / 2.0
        max_coh = math.sqrt(max(0.0, p0 * p1))
        coh = np.clip(coherence_ratio, 0.0, 1.0) * max_coh
        
        rho_01 = coh * np.exp(1j * phase)
        rho = np.array([[p0, rho_01], [np.conj(rho_01), p1]], dtype=np.complex128)
        return cls(rho)

    @classmethod
    def from_text(cls, text: str, default_coherence: float = 0.25) -> CognitiveState:
        """Infer an initial cognitive state from textual sentiment / stance."""
        val = analyze_text_sentiment(text)
        # Add random subtle phase to capture cognitive variation
        phase = val * np.pi * 0.5
        return cls.from_belief(belief=val, coherence_ratio=default_coherence, phase=phase)

    @classmethod
    def neutral(cls) -> CognitiveState:
        """Create a completely neutral, maximally mixed cognitive state."""
        return cls(0.5 * IDENTITY_2)

    def __repr__(self) -> str:
        return (
            f"CognitiveState(belief={self.belief_value:+.3f}, "
            f"P(Pro)={self.p_pro:.3f}, P(Contra)={self.p_contra:.3f}, "
            f"coherence={self.coherence:.3f}, purity={self.purity:.3f})"
        )


# ==============================================================================
# 2. Text Polarity & Sentiment Helper
# ==============================================================================

# Indonesian political discourse lexicons
PRO_KEYWORDS = {
    "bagus", "hebat", "mantap", "setuju", "dukung", "sukses", "solusi", "adil",
    "maju", "prestasi", "data", "menang", "positif", "cerdas", "damai", "integritas",
    "keren", "terbaik", "pilihan", "berprestasi", "optimis", "merakyat", "bijak",
    "fakta", "unggul", "kompeten", "solid", "bersih", "harapan",
    "gemoy", "program", "gratis", "hilirisasi", "lanjutkan", "perubahan", "desak", "tabrak",
    "terbukti", "siap", "andal", "santai", "asyik", "semangat", "satset", "kawal"
}

CONTRA_KEYWORDS = {
    "buruk", "gagal", "tolak", "lawan", "bodoh", "guoblook", "rusak", "bohong",
    "hoax", "kecewa", "toxic", "hancur", "korupsi", "kekerasan", "benci", "ribut",
    "badut", "palsu", "rezim", "muslihat", "kacau", "curang", "ngawur", "sesat",
    "hina", "ancaman", "mundur", "zalim", "dusta", "bobrok",
    "sengketa", "dinasti", "nepotisme", "gugat", "pelanggaran", "etik", "manipulasi",
    "sirekap", "ijazah", "mahkamah", "konstitusi", "sidang", "pansus", "politisasi"
}


def analyze_text_sentiment(text: str) -> float:
    """Analyze Indonesian text and return normalized valence in [-1.0, 1.0]."""
    if not text:
        return 0.0
    text_lower = text.lower()
    tokens = re.findall(r"\b[a-zA-Z]{3,}\b", text_lower)
    if not tokens:
        return 0.0

    pro_count = sum(1 for t in tokens if t in PRO_KEYWORDS)
    contra_count = sum(1 for t in tokens if t in CONTRA_KEYWORDS)

    # Detect emotional intensity / punctuation markers
    exclamation_boost = 0.1 * min(text.count("!"), 3)
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)

    diff = pro_count - contra_count
    total = pro_count + contra_count
    if total == 0:
        base_score = 0.0
    else:
        base_score = diff / total

    # Add modulation from uppercase or exclamation if polarized
    if base_score > 0:
        base_score += exclamation_boost
    elif base_score < 0:
        base_score -= exclamation_boost + 0.15 * caps_ratio

    return float(np.clip(base_score, -1.0, 1.0))


# ==============================================================================
# 3. Infon Probe: MemeStimulus
# ==============================================================================

@dataclass
class MemeStimulus:
    """Represents an external meme stimulus (quantum infon probe).

    Attributes:
        meme_id: Identifier of the meme.
        coupling_strength: Interaction strength g in [0.05, 1.0], derived from upvotes/engagement.
        phase_shift: Phase angle phi in [-pi, pi], derived from OCR text/caption sentiment.
        bias_direction: Detuning bias Delta in [-1.0, 1.0] (direction of narrative persuasion).
        caption: Extracted caption or OCR text.
        engagement: Dictionary of social engagement metrics.
        raw_data: Original input payload.
    """
    meme_id: str
    coupling_strength: float
    phase_shift: float
    bias_direction: float
    caption: str = ""
    engagement: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemeStimulus:
        """Create a MemeStimulus from a JSON dictionary (e.g. from memes.jsonl)."""
        meme_id = str(data.get("id", f"stimulus_{np.random.randint(100000, 999999)}"))
        engagement = data.get("engagement") or {}

        # 1. Calculate coupling_strength (g) from upvotes / engagement
        upvotes = float(engagement.get("upvotes", 0) or 0)
        likes = float(engagement.get("likes", 0) or 0)
        score = float(engagement.get("score", 0) or 0)
        retweets = float(engagement.get("retweets", 0) or engagement.get("shares", 0) or 0)
        comments = float(engagement.get("comments", 0) or 0)

        # Composite viral engagement measure
        primary_engagement = max(upvotes, score, likes)
        composite_engagement = primary_engagement + 0.5 * retweets + 0.5 * comments

        # Bounded scaling: g in [0.10, 1.0]
        # Baseline g_min = 0.15 for any published meme
        g_min = 0.15
        g_max = 1.00
        coupling_strength = float(
            g_min + (g_max - g_min) * np.tanh(np.log10(1.0 + max(0.0, composite_engagement)) / 1.5)
        )

        # 2. Calculate phase_shift (phi) and bias_direction (Delta) from OCR/caption
        caption = str(data.get("caption") or data.get("text") or data.get("ocr_text") or data.get("title") or "")
        valence = analyze_text_sentiment(caption)

        # Check explicit label metadata and category if present
        label = str(data.get("label") or data.get("metadata", {}).get("label") or "").lower()
        confidence = float(data.get("confidence") or data.get("metadata", {}).get("confidence") or 0.5)
        category = str(data.get("image_metadata", {}).get("category") or data.get("metadata", {}).get("category") or "").lower()

        if "toxic" in label and "non" not in label:
            # Toxic memes amplify antagonistic phase rotation and negative detuning
            phase_shift = -np.pi * 0.75 * confidence
            bias_direction = -0.80 * confidence
        elif "non toxic" in label or "netral" in label or "neutral" in label:
            if valence != 0.0:
                phase_shift = valence * np.pi * 0.5
                bias_direction = valence * 0.6
            elif "01" in category or "02" in category:
                phase_shift = 0.3 * np.pi
                bias_direction = 0.65
            elif "03" in category or "satire" in category:
                phase_shift = -0.3 * np.pi
                bias_direction = -0.65
            else:
                phase_shift = 0.1 * np.pi
                bias_direction = 0.2
        else:
            if valence != 0.0:
                phase_shift = valence * np.pi
                bias_direction = valence
            elif "01" in category or "02" in category:
                phase_shift = 0.4 * np.pi
                bias_direction = 0.70
            elif "03" in category or "satire" in category:
                phase_shift = -0.4 * np.pi
                bias_direction = -0.70
            else:
                phase_shift = 0.0
                bias_direction = 0.0

        # Ensure bounded ranges
        phase_shift = float(np.clip(phase_shift, -np.pi, np.pi))
        bias_direction = float(np.clip(bias_direction, -1.0, 1.0))

        return cls(
            meme_id=meme_id,
            coupling_strength=coupling_strength,
            phase_shift=phase_shift,
            bias_direction=bias_direction,
            caption=caption,
            engagement=engagement,
            raw_data=data,
        )

    @classmethod
    def load_from_jsonl(cls, file_path: Union[str, Path]) -> List[MemeStimulus]:
        """Load and parse meme stimuli from a .jsonl file."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Meme data file not found at: {path}")

        stimuli: List[MemeStimulus] = []
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                clean_line = line.strip()
                if not clean_line:
                    continue
                try:
                    payload = json.loads(clean_line)
                    stimuli.append(cls.from_dict(payload))
                except Exception as exc:
                    # Silently skip corrupted lines or log if needed
                    continue

        if not stimuli:
            raise ValueError(f"No valid meme stimulus records found in {path}")
        return stimuli


# ==============================================================================
# 4. Time Evolution Equations: apply_stimulus
# ==============================================================================

def construct_hamiltonian(
    coupling_strength: float,
    phase_shift: float,
    bias_direction: float,
    peer_influence: float = 0.0,
) -> np.ndarray:
    """Construct the 2x2 cognitive interaction Hamiltonian.

    H = 0.5 * [(Delta + peer_influence) * sigma_z + g * (cos(phi) * sigma_x + sin(phi) * sigma_y)]
    """
    delta_eff = bias_direction + peer_influence
    g = coupling_strength
    phi = phase_shift

    # Explicit 2x2 matrix
    h00 = 0.5 * delta_eff
    h11 = -0.5 * delta_eff
    h01 = 0.5 * g * (np.cos(phi) - 1.0j * np.sin(phi))  # g * exp(-i * phi) / 2
    h10 = np.conj(h01)

    return np.array([[h00, h01], [h10, h11]], dtype=np.complex128)


def _lindblad_derivative(
    rho: np.ndarray,
    H: np.ndarray,
    dephasing_rate: float,
    relaxation_rate: float,
    bias_direction: float,
) -> np.ndarray:
    """Compute the right-hand side of the Lindblad Master Equation d(rho)/dt.

    d(rho)/dt = -i [H, rho] + D_dephase(rho) + D_relax(rho)
    """
    # 1. Unitary driving commutator: -i [H, rho]
    d_unitary = -1.0j * (H @ rho - rho @ H)

    # 2. Dephasing dissipator: L_d = sqrt(gamma_d) * sigma_z
    # D(rho) = gamma_d * (sigma_z rho sigma_z - rho)
    d_dephase = np.zeros_like(rho, dtype=np.complex128)
    if dephasing_rate > 1e-12:
        d_dephase = dephasing_rate * (SIGMA_Z @ rho @ SIGMA_Z - rho)

    # 3. Directional relaxation dissipator (confirmation bias / ideological attractor)
    # If bias >= 0: transition |1> -> |0| via L = sqrt(gamma_r) * |0><1|
    # If bias < 0: transition |0> -> |1| via L = sqrt(gamma_r) * |1><0|
    d_relax = np.zeros_like(rho, dtype=np.complex128)
    if relaxation_rate > 1e-12:
        if bias_direction >= 0:
            L_r = np.array([[0.0, 1.0], [0.0, 0.0]], dtype=np.complex128)  # |0><1|
        else:
            L_r = np.array([[0.0, 0.0], [1.0, 0.0]], dtype=np.complex128)  # |1><0|
        
        L_dag = L_r.conj().T
        rate = relaxation_rate * (abs(bias_direction) + 0.1)
        d_relax = rate * (L_r @ rho @ L_dag - 0.5 * (L_dag @ L_r @ rho + rho @ L_dag @ L_r))

    return d_unitary + d_dephase + d_relax


def apply_stimulus(
    state: CognitiveState,
    stimulus: MemeStimulus,
    time_step: float = 1.0,
    method: str = "lindblad",
    dephasing_rate: float = 0.05,
    relaxation_rate: float = 0.03,
    peer_influence: float = 0.0,
) -> CognitiveState:
    """Compute belief state transition after exposure to a meme stimulus.

    Args:
        state: Current CognitiveState (density matrix).
        stimulus: Exposed MemeStimulus (infon probe).
        time_step: Duration of interaction / exposure dt.
        method: 'lindblad' (dissipative open quantum system) or
                'unitary' (closed quantum interference operator).
        dephasing_rate: Environmental decoherence rate (loss of cognitive superposition).
        relaxation_rate: Rate of ideological attraction towards meme stance.
        peer_influence: Mean-field bias from peer social context.

    Returns:
        Updated CognitiveState guaranteed to be a valid density matrix.
    """
    if time_step <= 0:
        return state.copy()

    H = construct_hamiltonian(
        coupling_strength=stimulus.coupling_strength,
        phase_shift=stimulus.phase_shift,
        bias_direction=stimulus.bias_direction,
        peer_influence=peer_influence,
    )

    if method.lower() == "unitary":
        # Unitary Operator Evolution: U = exp(-i * H * dt)
        U = expm(-1.0j * H * time_step)
        new_matrix = U @ state.matrix @ U.conj().T
    elif method.lower() == "lindblad":
        # Solve Lindblad Master Equation using 4th-order Runge-Kutta (RK4)
        sub_steps = max(1, int(np.ceil(time_step / 0.2)))
        dt_sub = time_step / sub_steps
        current_rho = state.matrix.copy()

        for _ in range(sub_steps):
            k1 = _lindblad_derivative(current_rho, H, dephasing_rate, relaxation_rate, stimulus.bias_direction)
            k2 = _lindblad_derivative(current_rho + 0.5 * dt_sub * k1, H, dephasing_rate, relaxation_rate, stimulus.bias_direction)
            k3 = _lindblad_derivative(current_rho + 0.5 * dt_sub * k2, H, dephasing_rate, relaxation_rate, stimulus.bias_direction)
            k4 = _lindblad_derivative(current_rho + dt_sub * k3, H, dephasing_rate, relaxation_rate, stimulus.bias_direction)
            
            current_rho = current_rho + (dt_sub / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
            # Enforce Hermiticity and positivity during sub-steps
            current_rho = 0.5 * (current_rho + current_rho.conj().T)
            current_rho /= np.trace(current_rho)

        new_matrix = current_rho
    else:
        raise ValueError(f"Unknown evolution method: {method}. Choose 'lindblad' or 'unitary'.")

    result = CognitiveState(new_matrix)
    result.normalize()
    return result


# ==============================================================================
# 5. Polarization Metrics
# ==============================================================================

def compute_polarization_metric(beliefs: np.ndarray) -> float:
    """Compute population polarization as belief variance.

    Range: [0.0, 1.0]. 0.0 is complete consensus, 1.0 is extreme bimodal split (+1 vs -1).
    """
    if len(beliefs) <= 1:
        return 0.0
    return float(np.var(beliefs))


def compute_asymmetry_metric(beliefs: np.ndarray) -> float:
    """Compute ideological cluster asymmetry (distance between pro and contra poles)."""
    if len(beliefs) <= 1:
        return 0.0
    pro_cands = beliefs[beliefs >= 0.0]
    contra_cands = beliefs[beliefs < 0.0]

    mean_pro = float(np.mean(pro_cands)) if len(pro_cands) > 0 else 0.0
    mean_contra = float(np.mean(contra_cands)) if len(contra_cands) > 0 else 0.0
    return abs(mean_pro - mean_contra)


# ==============================================================================
# 6. Quantum-Like Polarization Simulation: run_simulation
# ==============================================================================

def _load_or_generate_agents(
    text_data_path: Optional[Union[str, Path]],
    target_size: Optional[int] = None,
    rng: Optional[np.random.Generator] = None,
) -> List[CognitiveState]:
    """Load text data to seed agents, or generate a calibrated initial population."""
    if rng is None:
        rng = np.random.default_rng(42)

    agents: List[CognitiveState] = []
    if text_data_path:
        path = Path(text_data_path)
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    try:
                        record = json.loads(line_str)
                        text = record.get("text") or record.get("title") or record.get("caption") or ""
                        val = analyze_text_sentiment(text)
                        # Add a tiny idiosyncratic variance
                        b = float(np.clip(val + rng.normal(0, 0.1), -1.0, 1.0))
                        coh = float(rng.uniform(0.15, 0.40))
                        phase = float(rng.uniform(-np.pi, np.pi))
                        agents.append(CognitiveState.from_belief(b, coherence_ratio=coh, phase=phase))
                    except Exception:
                        continue

    # If insufficient agents loaded from file, complement or generate calibrated sample
    desired_size = target_size or (len(agents) if agents else 100)
    desired_size = max(desired_size, 30)

    if len(agents) < desired_size:
        needed = desired_size - len(agents)
        # Bimodal mixture with neutral core representing pre-election voter baseline
        for _ in range(needed):
            c = rng.choice(["pro", "contra", "undecided"], p=[0.40, 0.40, 0.20])
            if c == "pro":
                b = float(np.clip(rng.normal(0.45, 0.25), -1.0, 1.0))
            elif c == "contra":
                b = float(np.clip(rng.normal(-0.45, 0.25), -1.0, 1.0))
            else:
                b = float(np.clip(rng.normal(0.0, 0.20), -1.0, 1.0))
            coh = float(rng.uniform(0.20, 0.45))
            phase = float(rng.uniform(-np.pi, np.pi))
            agents.append(CognitiveState.from_belief(b, coherence_ratio=coh, phase=phase))

    if target_size and len(agents) > target_size:
        indices = rng.choice(len(agents), size=target_size, replace=False)
        agents = [agents[i] for i in indices]

    return agents


def run_simulation(
    text_data_path: Optional[Union[str, Path]] = None,
    meme_data_path: Optional[Union[str, Path]] = None,
    time_steps: int = 10,
    population_size: Optional[int] = None,
    method: str = "lindblad",
    dephasing_rate: float = 0.05,
    relaxation_rate: float = 0.03,
    peer_coupling_J: float = 0.15,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """Execute the Quantum-Like cognitive opinion polarization simulation.

    Args:
        text_data_path: Path to textual posts (e.g. data/processed/posts.jsonl).
        meme_data_path: Path to memes (e.g. data/processed/memes.jsonl).
        time_steps: Number of simulation epochs / exposure rounds.
        population_size: Size of simulated cognitive agent population.
        method: 'lindblad' (open dissipative system) or 'unitary'.
        dephasing_rate: Cognitive decoherence rate.
        relaxation_rate: Ideological drift rate.
        peer_coupling_J: Quantum social coupling strength (mean-field peer alignment).
        random_seed: Seed for reproducibility.

    Returns:
        Dict with keys:
          - 'time_steps': list of int [0, 1, ..., T]
          - 'polarization': list of float (polarization variance at each step)
          - 'asymmetry': list of float (cluster distance at each step)
          - 'mean_belief': list of float
          - 'mean_coherence': list of float
          - 'mean_purity': list of float
          - 'mean_entropy': list of float
          - 'agent_beliefs': 2D array of shape (T+1, N)
          - 'initial_states': list of initial CognitiveState
          - 'final_states': list of final CognitiveState
    """
    rng = np.random.default_rng(random_seed)

    # 1. Load initial agent population
    agents = _load_or_generate_agents(text_data_path, target_size=population_size, rng=rng)
    n_agents = len(agents)

    # 2. Load meme stimuli sequence
    stimuli: List[MemeStimulus] = []
    if meme_data_path and Path(meme_data_path).is_file():
        stimuli = MemeStimulus.load_from_jsonl(meme_data_path)
    
    # If no stimuli provided or empty file, create synthetic meme stream
    if not stimuli:
        for i in range(max(time_steps * 5, 50)):
            is_pro = rng.choice([True, False])
            upvotes = int(rng.exponential(25.0))
            eng = {"upvotes": upvotes, "likes": upvotes, "score": upvotes}
            stimuli.append(
                MemeStimulus(
                    meme_id=f"synth_meme_{i}",
                    coupling_strength=float(rng.uniform(0.2, 0.9)),
                    phase_shift=float(rng.uniform(0.1, np.pi) if is_pro else rng.uniform(-np.pi, -0.1)),
                    bias_direction=float(rng.uniform(0.2, 0.9) if is_pro else rng.uniform(-0.9, -0.2)),
                    caption="Synthetic political meme",
                    engagement=eng,
                )
            )

    # Record initial states
    initial_states = [a.copy() for a in agents]
    n_agents = len(agents)
    x0 = np.array([a.belief_value for a in agents], dtype=np.float64)

    # 3. Construct row-stochastic social network W
    adj = rng.uniform(0.0, 1.0, size=(n_agents, n_agents))
    adj[adj < 0.85] = 0.0
    np.fill_diagonal(adj, 2.0)
    row_sums = adj.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    W = adj / row_sums

    # 4. Agent susceptibility lambda_i in [0.35, 0.70]
    lambdas = rng.uniform(0.35, 0.70, size=n_agents)

    beliefs_history = np.zeros((time_steps + 1, n_agents), dtype=np.float64)
    beliefs_history[0, :] = x0.copy()

    polarization_series = [compute_polarization_metric(beliefs_history[0, :])]
    asymmetry_series = [compute_asymmetry_metric(beliefs_history[0, :])]
    mean_belief_series = [float(np.mean(beliefs_history[0, :]))]
    mean_coherence_series = [float(np.mean([a.coherence for a in agents]))]
    mean_purity_series = [float(np.mean([a.purity for a in agents]))]
    mean_entropy_series = [float(np.mean([a.entropy for a in agents]))]

    current_agents = [a.copy() for a in agents]
    beta = 0.25

    # Run time evolution
    for t in range(1, time_steps + 1):
        # Select memes active at step t
        memes_per_step = max(1, len(stimuli) // time_steps)
        step_memes = stimuli[(t - 1) * memes_per_step : t * memes_per_step]
        if not step_memes:
            step_memes = [rng.choice(stimuli)]

        current_beliefs = np.array([a.belief_value for a in current_agents], dtype=np.float64)
        social_influence = W @ current_beliefs

        updated_agents: List[CognitiveState] = []
        for i, agent in enumerate(current_agents):
            chosen_meme = rng.choice(step_memes)
            b_i = current_beliefs[i]

            # Cognitive interference & backfire effect (Maksymov & Pogrebna, 2024)
            is_counter = (b_i * chosen_meme.bias_direction < -0.05)
            if is_counter:
                # Psychological reactance repels counter-attitudinal shock, reinforcing own stance
                eff_bias = -0.40 * chosen_meme.bias_direction
                eff_phi = float(np.copysign(np.pi * 0.85, chosen_meme.phase_shift if chosen_meme.phase_shift != 0 else -1.0))
            else:
                eff_bias = chosen_meme.bias_direction
                eff_phi = chosen_meme.phase_shift

            delta_eff = (1.0 - lambdas[i]) * x0[i] + lambdas[i] * (social_influence[i] + beta * eff_bias)
            g_eff = lambdas[i] * beta * chosen_meme.coupling_strength

            H = construct_hamiltonian(
                coupling_strength=g_eff,
                phase_shift=eff_phi,
                bias_direction=delta_eff,
                peer_influence=0.0,
            )

            if method.lower() == "unitary":
                new_state = apply_stimulus(
                    state=agent,
                    stimulus=chosen_meme,
                    time_step=1.0,
                    method="unitary",
                )
            else:
                dt_sub = 1.0 / 5
                rho = agent.matrix.copy()
                for _ in range(5):
                    k1 = _lindblad_derivative(rho, H, dephasing_rate, relaxation_rate, delta_eff)
                    k2 = _lindblad_derivative(rho + 0.5 * dt_sub * k1, H, dephasing_rate, relaxation_rate, delta_eff)
                    k3 = _lindblad_derivative(rho + 0.5 * dt_sub * k2, H, dephasing_rate, relaxation_rate, delta_eff)
                    k4 = _lindblad_derivative(rho + dt_sub * k3, H, dephasing_rate, relaxation_rate, delta_eff)
                    rho = rho + (dt_sub / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
                    rho = 0.5 * (rho + rho.conj().T)
                    rho /= np.trace(rho)
                new_state = CognitiveState(rho)
                new_state.normalize()

            updated_agents.append(new_state)

        current_agents = updated_agents
        step_beliefs = np.array([a.belief_value for a in current_agents], dtype=np.float64)
        beliefs_history[t, :] = step_beliefs

        polarization_series.append(compute_polarization_metric(step_beliefs))
        asymmetry_series.append(compute_asymmetry_metric(step_beliefs))
        mean_belief_series.append(float(np.mean(step_beliefs)))
        mean_coherence_series.append(float(np.mean([a.coherence for a in current_agents])))
        mean_purity_series.append(float(np.mean([a.purity for a in current_agents])))
        mean_entropy_series.append(float(np.mean([a.entropy for a in current_agents])))

    return {
        "time_steps": list(range(time_steps + 1)),
        "polarization": polarization_series,
        "asymmetry": asymmetry_series,
        "mean_belief": mean_belief_series,
        "mean_coherence": mean_coherence_series,
        "mean_purity": mean_purity_series,
        "mean_entropy": mean_entropy_series,
        "agent_beliefs": beliefs_history,
        "initial_states": initial_states,
        "final_states": current_agents,
        "stimuli_count": len(stimuli),
    }


# ==============================================================================
# 7. Classical Baseline: Friedkin-Johnsen (FJ) Model
# ==============================================================================

def run_classical_baseline(
    text_data_path: Optional[Union[str, Path]] = None,
    meme_data_path: Optional[Union[str, Path]] = None,
    time_steps: int = 10,
    population_size: Optional[int] = None,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """Run a classical Friedkin-Johnsen (FJ) opinion dynamics baseline.

    Equation:
      x(t + 1) = Lambda * (W * x(t) + beta * s(t)) + (I - Lambda) * x(0)
      where:
      - x(t) in [-1, 1]^N: opinions at step t.
      - x(0): stubborn prior convictions.
      - Lambda: susceptibility to social influence in [0, 1].
      - (I - Lambda): individual stubbornness.
      - W: row-stochastic social network influence matrix.
      - s(t): external meme shock at step t.
    """
    rng = np.random.default_rng(random_seed)

    # 1. Load initial agent opinions (same distribution as quantum model)
    agents = _load_or_generate_agents(text_data_path, target_size=population_size, rng=rng)
    n_agents = len(agents)
    x0 = np.array([a.belief_value for a in agents], dtype=np.float64)

    # 2. Load meme stimuli
    stimuli: List[MemeStimulus] = []
    if meme_data_path and Path(meme_data_path).is_file():
        stimuli = MemeStimulus.load_from_jsonl(meme_data_path)

    # 3. Construct row-stochastic social network W
    # Erdos-Renyi / Small-world style network with self-weight
    adj = rng.uniform(0.0, 1.0, size=(n_agents, n_agents))
    # Sparsify
    adj[adj < 0.85] = 0.0
    # Strong diagonal self-weight
    np.fill_diagonal(adj, 2.0)
    # Row normalize
    row_sums = adj.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    W = adj / row_sums

    # 4. Susceptibility lambda_i in [0.35, 0.70]
    lambdas = rng.uniform(0.35, 0.70, size=n_agents)

    # Track trajectories
    opinions_history = np.zeros((time_steps + 1, n_agents), dtype=np.float64)
    opinions_history[0, :] = x0.copy()

    polarization_series = [compute_polarization_metric(x0)]
    asymmetry_series = [compute_asymmetry_metric(x0)]
    mean_opinion_series = [float(np.mean(x0))]

    current_x = x0.copy()

    for t in range(1, time_steps + 1):
        # Calculate exogenous meme stimulus shock s(t)
        if stimuli:
            memes_per_step = max(1, len(stimuli) // time_steps)
            step_memes = stimuli[(t - 1) * memes_per_step : t * memes_per_step]
            if not step_memes:
                step_memes = [rng.choice(stimuli)]
        else:
            step_memes = []

        # Classical FJ update: x(t+1) = Lambda * (W x(t) + beta * s(t)) + (1 - Lambda) * x(0)
        social_influence = W @ current_x
        beta = 0.25
        next_x = np.zeros_like(current_x)
        for i in range(n_agents):
            if step_memes:
                chosen_meme = rng.choice(step_memes)
                meme_shock = chosen_meme.coupling_strength * chosen_meme.bias_direction
            else:
                meme_shock = 0.0
            next_x[i] = lambdas[i] * (social_influence[i] + beta * meme_shock) + (1.0 - lambdas[i]) * x0[i]
        next_x = np.clip(next_x, -1.0, 1.0)
        current_x = next_x

        opinions_history[t, :] = current_x
        polarization_series.append(compute_polarization_metric(current_x))
        asymmetry_series.append(compute_asymmetry_metric(current_x))
        mean_opinion_series.append(float(np.mean(current_x)))

    return {
        "time_steps": list(range(time_steps + 1)),
        "polarization": polarization_series,
        "asymmetry": asymmetry_series,
        "mean_belief": mean_opinion_series,
        "agent_beliefs": opinions_history,
    }


# ==============================================================================
# 8. Publication-Quality Visualization: plot_simulation_results
# ==============================================================================

def plot_simulation_results(
    quantum_res: Dict[str, Any],
    classical_res: Dict[str, Any],
    output_path: Union[str, Path] = "reports/polarization_over_time.png",
    title: str = "Quantum-Like Cognitive Polarization vs. Classical Baseline",
) -> plt.Figure:
    """Generate and save publication-grade visualization of simulation results.

    Creates a 4-panel analytical comparison figure:
      1. Polarization Trajectory (Variance over Time).
      2. Asymmetry (Ideological Cluster Distance over Time).
      3. Quantum Coherence & Purity Dynamics.
      4. Final Opinion Distribution Histogram/KDE.
    """
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    time_steps = quantum_res["time_steps"]
    q_pol = quantum_res["polarization"]
    c_pol = classical_res["polarization"]

    q_asym = quantum_res["asymmetry"]
    c_asym = classical_res["asymmetry"]

    q_coh = quantum_res.get("mean_coherence", [])
    q_pur = quantum_res.get("mean_purity", [])

    q_final_beliefs = quantum_res["agent_beliefs"][-1, :]
    c_final_beliefs = classical_res["agent_beliefs"][-1, :]

    # Set up matplotlib aesthetics
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=300)
    fig.suptitle(title, fontsize=16, fontweight="bold", y=0.98)

    # --------------------------------------------------------------------------
    # Panel 1: Polarization (Variance) Over Time
    # --------------------------------------------------------------------------
    ax1 = axes[0, 0]
    ax1.plot(time_steps, q_pol, marker="o", linewidth=2.5, color="#1f77b4", label="Quantum-Like Model (Lindblad)")
    ax1.plot(time_steps, c_pol, marker="s", linewidth=2.0, linestyle="--", color="#d62728", label="Classical Baseline (Friedkin-Johnsen)")
    ax1.set_title("(a) Polarization Index (Belief Variance) Over Time", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Time Steps (Exposure Epochs)", fontsize=11)
    ax1.set_ylabel(r"Polarization Variance $\sigma^2_b$", fontsize=11)
    ax1.set_xticks(time_steps)
    ax1.legend(loc="best", frameon=True, fontsize=10)
    ax1.grid(True, linestyle=":", alpha=0.6)

    # --------------------------------------------------------------------------
    # Panel 2: Ideological Asymmetry Over Time
    # --------------------------------------------------------------------------
    ax2 = axes[0, 1]
    ax2.plot(time_steps, q_asym, marker="^", linewidth=2.5, color="#2ca02c", label=r"Quantum Asymmetry $|\bar{b}_+ - \bar{b}_-|$")
    ax2.plot(time_steps, c_asym, marker="d", linewidth=2.0, linestyle="--", color="#ff7f0e", label="Classical Asymmetry")
    ax2.set_title("(b) Bimodal Ideological Separation (Asymmetry)", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Time Steps (Exposure Epochs)", fontsize=11)
    ax2.set_ylabel("Mean Inter-Cluster Distance", fontsize=11)
    ax2.set_xticks(time_steps)
    ax2.legend(loc="best", frameon=True, fontsize=10)
    ax2.grid(True, linestyle=":", alpha=0.6)

    # --------------------------------------------------------------------------
    # Panel 3: Quantum Cognitive Coherence and Purity Dynamics
    # --------------------------------------------------------------------------
    ax3 = axes[1, 0]
    if q_coh and q_pur:
        color_coh = "#9467bd"
        color_pur = "#8c564b"
        line1 = ax3.plot(time_steps, q_coh, marker="o", color=color_coh, linewidth=2.2, label=r"Mean Coherence $\langle |\rho_{01}| \rangle$")
        ax3.set_ylabel("Cognitive Coherence (Superposition)", color=color_coh, fontsize=11)
        ax3.tick_params(axis="y", labelcolor=color_coh)
        ax3.set_xlabel("Time Steps (Exposure Epochs)", fontsize=11)
        ax3.set_xticks(time_steps)

        ax3_twin = ax3.twinx()
        line2 = ax3_twin.plot(time_steps, q_pur, marker="x", color=color_pur, linewidth=2.0, linestyle="-.", label=r"State Purity $\mathrm{Tr}(\rho^2)$")
        ax3_twin.set_ylabel(r"Quantum State Purity $\gamma$", color=color_pur, fontsize=11)
        ax3_twin.tick_params(axis="y", labelcolor=color_pur)
        ax3_twin.grid(False)

        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax3.legend(lines, labels, loc="center right", frameon=True, fontsize=10)
    ax3.set_title("(c) Quantum Cognitive Coherence & Decoherence Dynamics", fontsize=12, fontweight="bold")
    ax3.grid(True, linestyle=":", alpha=0.6)

    # --------------------------------------------------------------------------
    # Panel 4: Final Opinion Distribution (KDE / Histogram)
    # --------------------------------------------------------------------------
    ax4 = axes[1, 1]
    bins = np.linspace(-1.0, 1.0, 21)
    ax4.hist(
        q_final_beliefs,
        bins=bins,
        alpha=0.65,
        color="#1f77b4",
        edgecolor="black",
        label=f"Quantum-Like (Var: {np.var(q_final_beliefs):.3f})",
        density=True,
    )
    ax4.hist(
        c_final_beliefs,
        bins=bins,
        alpha=0.50,
        color="#d62728",
        edgecolor="black",
        linestyle="--",
        label=f"Classical FJ (Var: {np.var(c_final_beliefs):.3f})",
        density=True,
    )
    ax4.axvline(0.0, color="gray", linestyle=":", linewidth=1.2, alpha=0.8)
    ax4.set_title(r"(d) Final Opinion Distribution at $t = T$", fontsize=12, fontweight="bold")
    ax4.set_xlabel("Belief Value (Contra [-1] <---> Pro [+1])", fontsize=11)
    ax4.set_ylabel("Probability Density", fontsize=11)
    ax4.set_xlim(-1.05, 1.05)
    ax4.legend(loc="upper center", frameon=True, fontsize=10)
    ax4.grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    fig.savefig(str(out_file), dpi=300, bbox_inches="tight")
    plt.close(fig)
    return fig


# ==============================================================================
# 9. Main Script Execution for Pipeline Integration
# ==============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Running Quantum-Like Computational Model for Political Polarization")
    print("=" * 70)

    # Locate default project paths
    root_dir = Path(__file__).resolve().parent.parent.parent
    text_path = root_dir / "data" / "processed" / "posts.jsonl"
    meme_path = root_dir / "data" / "processed" / "memes.jsonl"
    report_output = root_dir / "reports" / "polarization_over_time.png"

    print(f"Text data path: {text_path} (exists: {text_path.is_file()})")
    print(f"Meme data path: {meme_path} (exists: {meme_path.is_file()})")

    # 1. Run Quantum-Like Simulation
    print("\n[1/3] Executing Quantum-Like Simulation (Lindblad Open System)...")
    q_results = run_simulation(
        text_data_path=str(text_path) if text_path.is_file() else None,
        meme_data_path=str(meme_path) if meme_path.is_file() else None,
        time_steps=10,
        population_size=100,
        method="lindblad",
    )
    print(f"  Initial Polarization: {q_results['polarization'][0]:.4f}")
    print(f"  Final Polarization:   {q_results['polarization'][-1]:.4f}")
    print(f"  Initial Asymmetry:    {q_results['asymmetry'][0]:.4f}")
    print(f"  Final Asymmetry:      {q_results['asymmetry'][-1]:.4f}")
    print(f"  Final Mean Coherence: {q_results['mean_coherence'][-1]:.4f}")

    # 2. Run Classical Friedkin-Johnsen Baseline
    print("\n[2/3] Executing Classical Friedkin-Johnsen Baseline...")
    c_results = run_classical_baseline(
        text_data_path=str(text_path) if text_path.is_file() else None,
        meme_data_path=str(meme_path) if meme_path.is_file() else None,
        time_steps=10,
        population_size=100,
    )
    print(f"  Initial Polarization: {c_results['polarization'][0]:.4f}")
    print(f"  Final Polarization:   {c_results['polarization'][-1]:.4f}")
    print(f"  Initial Asymmetry:    {c_results['asymmetry'][0]:.4f}")
    print(f"  Final Asymmetry:      {c_results['asymmetry'][-1]:.4f}")

    # 3. Generate and Save Comparison Plots
    print(f"\n[3/3] Generating visualization -> {report_output}...")
    plot_simulation_results(
        quantum_res=q_results,
        classical_res=c_results,
        output_path=report_output,
    )
    print("Done! Visualization successfully generated.")
    print("=" * 70)

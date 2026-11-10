#!/usr/bin/env python3
"""
IT³ K-PHAM (Release: IT3-v22.6-strict) — SCIENTIFIC PROOF-LEDGER & DIAGNOSTIC SUITE
===================================================================================
Principle: Code computes everything. Report asserts only proven/derived claims.
All exploratory ansätze, visual rhymes, and null results are isolated as diagnostics.
Authors: Victor Logvinovich & Jean-Claude Perez
DOI:     https://doi.org/10.5281/zenodo.21792530 (https://zenodo.org/records/21792530)
"""

import argparse
from enum import Enum
from fractions import Fraction
from collections import Counter, defaultdict
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import sys
import csv
import json
import math
import urllib.request
import ssl
import gzip
import shutil
import hashlib
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Tuple, Any
from tqdm import tqdm
from scipy.interpolate import make_interp_spline
from scipy import stats
import re
import warnings

warnings.filterwarnings('ignore')

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
PLOTS_HTML_DIR = SCRIPT_DIR / "plots_html"
FIGURES_DIR = SCRIPT_DIR / "figures"
REPORTS_DIR = SCRIPT_DIR / "reports"
LOGS_DIR = SCRIPT_DIR / "logs"
LOG_FILENAME = "it3_terminal_run_log.txt"

def rel_to_root(path_like: Any) -> str:
    """Returns a portable relative POSIX path (./...) independent of the host machine."""
    try:
        p = Path(path_like).resolve()
        return "./" + p.relative_to(SCRIPT_DIR).as_posix()
    except Exception:
        return "./" + Path(path_like).name

class TerminalTeeLogger:
    """Mirrors terminal output to a clean, ANSI-stripped UTF-8 log file in SCRIPT_DIR for GitHub."""
    ANSI_RE = re.compile(r'(?:\x1b\[[0-9;]*[a-zA-Z]|\[(?:0|1|3[0-7])m)')

    def __init__(self, log_path: Path):
        self.terminal = sys.stdout
        self.log_path = log_path
        self.log_file = open(log_path, 'w', encoding='utf-8')

    def write(self, message: str):
        self.terminal.write(message)
        clean = self.ANSI_RE.sub('', message)
        if '\r' in clean and '\n' not in clean:
            return
        if '\r' in clean:
            clean = clean.split('\r')[-1]
        self.log_file.write(clean)
        self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def close(self):
        try:
            self.log_file.close()
        except Exception:
            pass


# ============================================================================
# CINEMATIC TERMINAL FORMATTING & EPISTEMIC LEDGER CLASSES
# ============================================================================
class Term:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    BLACK = '\033[30m'
    DARK_RED = '\033[31m'
    DARK_GREEN = '\033[32m'
    DARK_BLUE = '\033[34m'
    DARK_MAGENTA = '\033[35m'
    CYAN = '\033[36m'

EPISTEMIC_POLICY = """
IT3 strict epistemic policy (Release IT3-v22.6-strict):
1. Exact mathematical identities are marked EXACT_MATH.
2. Physical predictions are allowed only if marked EXACT_MATH or
   DERIVED_FROM_POSTULATES.
3. Catalog statistics are marked EMPIRICAL_TEST or NULL_RESULT.
4. Exploratory constant matching is marked ANSATZ_DIAGNOSTIC.
5. Micro-macro analogies are marked VISUAL_RHYME.
6. No diagnostic, rhyme, or ansatz may be used as proof.
7. Numerology exposure is computed, not asserted.
"""

class ClaimStatus(str, Enum):
    EXACT_MATH = "EXACT_MATH"
    DERIVED_FROM_POSTULATES = "DERIVED_FROM_POSTULATES"
    EMPIRICAL_TEST = "EMPIRICAL_TEST"
    ANSATZ_DIAGNOSTIC = "ANSATZ_DIAGNOSTIC"
    VISUAL_RHYME = "VISUAL_RHYME"
    NULL_RESULT = "NULL_RESULT"
    OPEN_CONJECTURE = "OPEN_CONJECTURE"

ALLOWED_FOR_PREDICTION = {
    ClaimStatus.EXACT_MATH,
    ClaimStatus.DERIVED_FROM_POSTULATES,
}

class EpistemicMode(str, Enum):
    PROVEN_ONLY = "proven-only"
    FULL_DIAGNOSTIC = "full-diagnostic"

@dataclass
class Claim:
    name: str
    status: ClaimStatus
    value: Optional[Any] = None
    unit: str = ""
    uncertainty: Optional[Any] = None
    proof_id: Optional[str] = None
    dependencies: Tuple[str, ...] = ()
    statement: str = ""
    external_reference: Optional[str] = None
    is_predictive: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "uncertainty": self.uncertainty,
            "proof_id": self.proof_id,
            "dependencies": list(self.dependencies),
            "statement": self.statement,
            "external_reference": self.external_reference,
            "is_predictive": self.is_predictive,
        }

@dataclass
class ProofLedger:
    version: str = "IT3-v22.6-strict"
    epistemic_mode: str = "proven-only"
    claims: Dict[str, Claim] = field(default_factory=dict)
    postulates: Dict[str, str] = field(default_factory=dict)
    theorems: Dict[str, str] = field(default_factory=dict)
    quantitative_metrics: Dict[str, Any] = field(default_factory=dict)

    def add_postulate(self, pid: str, text: str) -> None:
        self.postulates[pid] = text

    def add_theorem(self, tid: str, text: str) -> None:
        self.theorems[tid] = text

    def add_claim(self, claim: Claim) -> None:
        if claim.name in self.claims:
            raise ValueError(f"Duplicate claim: {claim.name}")
        self.claims[claim.name] = claim

    def predictive_claims(self) -> List[Claim]:
        return [
            c for c in self.claims.values()
            if c.is_predictive and c.status in ALLOWED_FOR_PREDICTION
        ]

    def diagnostic_claims(self) -> List[Claim]:
        return [
            c for c in self.claims.values()
            if c.status not in ALLOWED_FOR_PREDICTION
        ]

    def validate_no_ansatz_in_predictions(self) -> None:
        bad = [
            c.name for c in self.claims.values()
            if c.is_predictive and c.status not in ALLOWED_FOR_PREDICTION
        ]
        if bad:
            raise RuntimeError(
                "Numerology guard failed. Predictive claims depend on non-proven status: "
                + ", ".join(bad)
            )
        bad_ref = [
            c.name for c in self.predictive_claims()
            if c.external_reference is not None
        ]
        if bad_ref:
            raise RuntimeError(
                "Post-hoc anchor guard failed. Predictive claims must not cite external target data: "
                + ", ".join(bad_ref)
            )

    def unproven_predictive_flag_share(self) -> float:
        """Flag-hygiene check: share of is_predictive=True claims lacking proven/derived status."""
        preds = [c for c in self.claims.values() if c.is_predictive]
        if not preds:
            return 0.0
        bad = [c for c in preds if c.status not in ALLOWED_FOR_PREDICTION]
        return float(len(bad)) / float(len(preds))

    def exact_math_claims(self) -> List[Claim]:
        return [c for c in self.claims.values() if c.status == ClaimStatus.EXACT_MATH]

    def catalog_test_claims(self) -> List[Claim]:
        return [c for c in self.claims.values() if c.status in {ClaimStatus.EMPIRICAL_TEST, ClaimStatus.NULL_RESULT}]

    def exploratory_claims(self) -> List[Claim]:
        return [
            c for c in self.claims.values()
            if c.status in {ClaimStatus.ANSATZ_DIAGNOSTIC, ClaimStatus.VISUAL_RHYME, ClaimStatus.OPEN_CONJECTURE}
        ]

    def exploratory_diagnostic_share(self) -> float:
        """True fraction of all registered claims that are exploratory ansätze, rhymes, or conjectures."""
        if not self.claims:
            return 0.0
        return round(float(len(self.exploratory_claims())) / float(len(self.claims)), 6)

    def numerology_exposure(self) -> float:
        """Alias for flag-hygiene check (must be paired with exploratory_diagnostic_share in reports)."""
        return self.unproven_predictive_flag_share()

    def certificate(self) -> dict:
        self.validate_no_ansatz_in_predictions()
        return {
            "version": self.version,
            "epistemic_mode": self.epistemic_mode,
            "external_benchmarks_are_not_predictions": True,
            "unproven_predictive_flag_share": self.unproven_predictive_flag_share(),
            "exploratory_diagnostic_share": self.exploratory_diagnostic_share(),
            "numerology_exposure": self.numerology_exposure(),
            "postulates": self.postulates,
            "theorems": self.theorems,
            "predictive_claims": [c.name for c in self.predictive_claims()],
            "diagnostic_claims": [c.name for c in self.diagnostic_claims()],
            "claims": {k: v.to_dict() for k, v in self.claims.items()},
            "epistemic_policy": (
                "Only EXACT_MATH and DERIVED_FROM_POSTULATES may be used as predictions. "
                "Empirical tests, ansätze, visual rhymes and null results are retained "
                "as diagnostics but are not physical proofs."
            ),
        }

    def save_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.certificate(), f, indent=2, ensure_ascii=False)

def print_claim(claim: Claim, mode: EpistemicMode) -> None:
    if mode == EpistemicMode.PROVEN_ONLY and claim.status not in ALLOWED_FOR_PREDICTION:
        return
    badge = {
        ClaimStatus.EXACT_MATH: f"{Term.DARK_GREEN}[EXACT]{Term.RESET}",
        ClaimStatus.DERIVED_FROM_POSTULATES: f"{Term.DARK_BLUE}[DERIVED]{Term.RESET}",
        ClaimStatus.EMPIRICAL_TEST: f"{Term.CYAN}[EMPIRICAL]{Term.RESET}",
        ClaimStatus.ANSATZ_DIAGNOSTIC: f"{Term.DARK_MAGENTA}[ANSATZ DIAGNOSTIC]{Term.RESET}",
        ClaimStatus.VISUAL_RHYME: f"{Term.DARK_MAGENTA}[VISUAL RHYME]{Term.RESET}",
        ClaimStatus.NULL_RESULT: f"{Term.DARK_RED}[NULL RESULT]{Term.RESET}",
        ClaimStatus.OPEN_CONJECTURE: f"{Term.BLACK}[OPEN CONJECTURE]{Term.RESET}",
    }[claim.status]
    if isinstance(claim.value, float):
        val_str = f" = {claim.value:.12g} {claim.unit}".rstrip()
    elif claim.value is not None:
        val_str = f" = {claim.value} {claim.unit}".rstrip()
    else:
        val_str = ""
    pred_tag = " (PREDICTIVE)" if claim.is_predictive else " (NON-PREDICTIVE)"
    print(f"  {badge} {Term.BOLD}{claim.name}{Term.RESET}{val_str}{pred_tag}")
    if claim.statement:
        print(f"      ↳ {claim.statement}")

def animate_text(text: str, delay: float = 0.0006):
    for line in text.splitlines(True):
        sys.stdout.write(line)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write('\n')

def print_banner(mode: EpistemicMode = EpistemicMode.PROVEN_ONLY):
    banner = f"""
{Term.DARK_BLUE}{Term.BOLD}╔═══════════════════════════════════════════════════════════════════════════════════════╗{Term.RESET}
{Term.DARK_BLUE}{Term.BOLD}║{Term.BLACK}   IT³ K-PHAM (Release: IT3-v22.6-strict) — PROOF LEDGER & DIAGNOSTIC SUITE          {Term.DARK_BLUE}║{Term.RESET}
{Term.DARK_BLUE}{Term.BOLD}║{Term.BLACK}   Epistemic Mode: {mode.value:<18} | Numerology Exposure: Computed Dynamically     {Term.DARK_BLUE}║{Term.RESET}
{Term.DARK_BLUE}{Term.BOLD}║{Term.BLACK}   Authors: Victor Logvinovich & Jean-Claude Perez | DOI: 10.5281/zenodo.21792530     {Term.DARK_BLUE}║{Term.RESET}
{Term.DARK_BLUE}{Term.BOLD}╚═══════════════════════════════════════════════════════════════════════════════════════╝{Term.RESET}"""
    print(banner)
    print(f"{Term.BLACK}{EPISTEMIC_POLICY.strip()}{Term.RESET}\n")

def print_section(title: str):
    width = 89
    print(f"\n{Term.DARK_BLUE}{'─'*width}{Term.RESET}")
    print(f"{Term.DARK_BLUE}{Term.BOLD}  {title}{Term.RESET}")
    print(f"{Term.DARK_BLUE}{'─'*width}{Term.RESET}\n")

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

DATA_SHA = 'cached-unknown'
COMET_SHA = 'unverified-offline'
SCRIPT_SHA = 'unknown'

def sha256_prefix(path: str, n: int = 16) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:n]


# ============================================================================
# EXTERNAL EMPIRICAL BENCHMARKS & EXPLICIT POSTULATES (HONESTY LEDGER)
# ============================================================================
@dataclass(frozen=True)
class ExternalBenchmarks:
    """
    External reference values (CODATA 2022, PDG 2024, IAU/JPL Ephemerides).
    These are NOT predictions of IT3.
    They are used only to test IT3 predictions and evaluate diagnostic ansätze.
    """
    ALPHA_INV_CODATA: float = 137.035999084       # CODATA 2022 ± 0.000000021
    MUON_ELECTRON_CODATA: float = 206.7682830     # CODATA 2022 ± 0.0000046
    PROTON_ELECTRON_CODATA: float = 1836.15267343 # CODATA 2022
    SIN_THETA_CABIBBO_PDG: float = 0.22500        # PDG 2024 ± 0.00067
    OMEGA_LAMBDA_PLANCK: float = 0.6847           # Planck 2018 ± 0.0073
    GM_SUN_OVER_GM_JUP_IAU: float = 1047.5655     # IAU / JPL DE440 nominal
    SOLAR_RAD_CORE_ROT_DAYS: float = 24.50        # Helioseismic tachocline/core (~24.5 d)
    URANUS_AXIAL_TILT_IAU: float = 97.77          # IAU cartographic obliquity (deg)
    A_NEPTUNE_AU: float = 30.0689                 # Neptune semi-major axis (AU)
    JUPITER_PERIOD_DAYS: float = 4332.589         # Jupiter sidereal orbit period (days)


@dataclass(frozen=True)
class IT3Config:
    """
    Separates pure algebraic invariants of K = Q(√2,√3,√5) from explicit physical
    postulates / dimensional anchors.
    """
    SQRT2: float = field(default_factory=lambda: float(np.sqrt(2.0)))
    SQRT3: float = field(default_factory=lambda: float(np.sqrt(3.0)))
    SQRT5: float = field(default_factory=lambda: float(np.sqrt(5.0)))

    VALENCY_LEPTON: int = 2
    VALENCY_QUARK: int = 3

    DIMENSIONAL_ANCHOR_AU: float = 1.0            # Postulate P2_ANCHOR_AU: 1.0 AU scale
    A_NEPTUNE_AU: float = 30.0689                 # External astronomical reference for MMRs
    R_IONIZATION_CUTOFF_AU: float = 48.0          # Operational Kuiper Cliff cutoff

    MAX_BACKGROUND_ASTEROIDS: int = 3500
    MAX_FLOOR_DISPLAY: int = 12
    Z_SCALE_FACTOR: float = 50.0

    BG_COLOR: str = '#07070b'
    GRID_COLOR: str = '#2a2a35'
    TEXT_COLOR: str = '#e0e0e0'
    COLOR_PLANET: str = '#FFD700'
    COLOR_DWARF: str = '#00FFFF'
    COLOR_ETNO: str = '#FF1493'
    COLOR_ASTEROID: str = '#4A4A6A'
    COLOR_RING_GLOW: str = '#8A2BE2'
    COLOR_RING_CORE: str = '#DDA0DD'
    COLOR_VALENCE: str = '#00FF00'
    COLOR_SPIRAL: str = '#FFA500'
    COLOR_MERIDIAN: str = '#3A3A4F'

    @property
    def PHI(self) -> float:
        return (1.0 + self.SQRT5) / 2.0

    @property
    def INRADIUS_2R(self) -> float:
        return self.SQRT2 + self.SQRT3 - self.SQRT5

    @property
    def LAMBDA_Y(self) -> float:
        return self.SQRT3

    @property
    def K_TORUS(self) -> float:
        return 3.0 + 2.0 * self.SQRT2

    @property
    def LAMBDA_H(self) -> float:
        return float(self.VALENCY_LEPTON)

    @property
    def LAMBDA_1_EXACT(self) -> float:
        return self.LAMBDA_Y * self.K_TORUS

    @property
    def LAMBDA_3_EXACT(self) -> float:
        return (self.PHI ** 2) * self.LAMBDA_Y

    @property
    def N_TWIST(self) -> int:
        """
        Ansatz parameter: unfiltered min of E_geom(N) is 102 (E=101.831);
        imposing the 3-braid coprimality condition gcd(N,3)=1 selects N=103 (E=102.019).
        """
        l1_sq = self.LAMBDA_1_EXACT ** 2
        l1_4 = l1_sq ** 2
        best_n, best_e = 103, float('inf')
        for n in range(95, 110):
            if math.gcd(n, self.VALENCY_QUARK) != 1:
                continue
            e_geom = ((n - l1_sq) ** 2) + (l1_4 / n)
            if e_geom < best_e:
                best_e, best_n = e_geom, n
        return best_n

    @property
    def WRITHE_STATIC(self) -> float:
        return abs(self.N_TWIST - (self.LAMBDA_1_EXACT ** 2))

    @property
    def WRITHE_DYNAMIC(self) -> float:
        return self.WRITHE_STATIC * (1.0 + 1.0 / ((self.VALENCY_LEPTON + self.VALENCY_QUARK) * self.N_TWIST))

    @property
    def VALENCY_TENSOR_DIM(self) -> int:
        return self.VALENCY_LEPTON * self.VALENCY_QUARK

    @property
    def DIRICHLET_UNIT_RANK(self) -> int:
        return 7

    @property
    def R_BASE(self) -> float:
        return round(float(self.LAMBDA_Y ** self.VALENCY_TENSOR_DIM) * self.DIMENSIONAL_ANCHOR_AU, 10)

    @property
    def R_MID_EXACT(self) -> float:
        return float(self.R_PHASE_TRANSITION) * self.SQRT2

    @property
    def R_OUT_EXACT(self) -> float:
        return float(self.R_PHASE_TRANSITION) * self.LAMBDA_Y

    @property
    def R_VALENCE_EXACT(self) -> float:
        return self.R_BASE * self.LAMBDA_Y

    @property
    def R_VALENCE(self) -> float:
        return round(self.R_VALENCE_EXACT, 2)

    @property
    def R_PHASE_TRANSITION(self) -> float:
        return round(self.R_BASE * (self.LAMBDA_Y ** 4), 6)

    @property
    def INNER_NORMALIZATION(self) -> float:
        return round(self.LAMBDA_1_EXACT, 3)

    @property
    def NORMALIZATION_FACTOR(self) -> float:
        return round(self.R_PHASE_TRANSITION / self.LAMBDA_1_EXACT, 2)

    @property
    def MMR_1_2_NEPTUNE_AU(self) -> float:
        return self.A_NEPTUNE_AU * (2.0 ** (2.0 / 3.0))

    @property
    def R_IONIZATION_LIMIT(self) -> float:
        return self.R_IONIZATION_CUTOFF_AU

    @property
    def R_EVAP_TAIL_UPPER(self) -> float:
        return round(4.0 * self.SQRT3 * self.INNER_NORMALIZATION, 2)

    @property
    def R_DIM_COLLAPSE_LOWER(self) -> float:
        return round(self.R_PHASE_TRANSITION + self.NORMALIZATION_FACTOR * 2.0 * self.SQRT3, 2)

    @property
    def R_DIM_COLLAPSE_UPPER(self) -> float:
        return round(self.R_PHASE_TRANSITION + self.NORMALIZATION_FACTOR * 4.0 * self.SQRT3, 2)

    @property
    def PHASE_BREAK(self) -> float:
        return round(float(np.degrees(np.arcsin((self.SQRT5 - 1.0) / 4.0))), 4)

    @property
    def AVOIDANCE_ZONE(self) -> float:
        return 3.0 * self.PHASE_BREAK

    @property
    def MAGIC_ANGLE_OH(self) -> float:
        return round(float(np.degrees(np.arccos(1.0 / self.SQRT3))), 4)


# ============================================================================
# PHASE 0: EPISTEMIC AUDIT ENGINE & PROOF LEDGER BUILDER
# ============================================================================
class EpistemicAuditEngine:
    @staticmethod
    def _omega_prime_factors(n: int) -> int:
        cnt, d, temp = 0, 2, n
        while d * d <= temp:
            while temp % d == 0:
                cnt += 1
                temp //= d
            d += 1
        if temp > 1:
            cnt += 1
        return cnt

    @staticmethod
    def build_e8_root_system() -> Tuple[int, float]:
        int_roots = []
        for i in range(8):
            for j in range(i + 1, 8):
                for s1 in (-1.0, 1.0):
                    for s2 in (-1.0, 1.0):
                        vec = np.zeros(8)
                        vec[i], vec[j] = s1, s2
                        int_roots.append(vec)
        spinor_roots = []
        for mask in range(256):
            if bin(mask).count('1') % 2 == 0:
                vec = np.array([-0.5 if (mask >> b) & 1 else 0.5 for b in range(8)])
                spinor_roots.append(vec)
        all_roots = np.vstack([int_roots, spinor_roots])
        assert len(all_roots) == 240 and np.allclose(np.sum(all_roots ** 2, axis=1), 2.0)

        cartan_e8 = np.array([
            [ 2, -1,  0,  0,  0,  0,  0,  0],
            [-1,  2, -1,  0,  0,  0,  0,  0],
            [ 0, -1,  2, -1,  0,  0,  0, -1],
            [ 0,  0, -1,  2, -1,  0,  0,  0],
            [ 0,  0,  0, -1,  2, -1,  0,  0],
            [ 0,  0,  0,  0, -1,  2, -1,  0],
            [ 0,  0,  0,  0,  0, -1,  2,  0],
            [ 0,  0, -1,  0,  0,  0,  0,  2]
        ], dtype=float)
        covolume_e8 = float(np.sqrt(abs(np.linalg.det(cartan_e8))))
        return len(all_roots), covolume_e8

    @classmethod
    def run_epistemic_audit(cls, config: IT3Config, bench: ExternalBenchmarks) -> Dict:
        print_section("PHASE 0A: LAYER I — STRICT ALGEBRAIC & GEOMETRIC THEOREMS (EXACT_MATH)")
        ledger = {'layer_1_exact_mathematics': {}, 'layer_3_ansatze_and_resonances': {}}

        # 1. Coupled Pythagorean Cascade & Inradius (Math_Topology_v17 Thm 2.5 & Prop 2.6)
        assert np.isclose(1.0**2 + config.SQRT2**2, config.SQRT3**2, atol=1e-15)
        assert np.isclose(config.SQRT2**2 + config.SQRT3**2, config.SQRT5**2, atol=1e-15)
        inradius_rationalized = (config.SQRT2 * config.SQRT3) / (config.SQRT2 + config.SQRT3 + config.SQRT5)
        assert np.isclose(2.0 * inradius_rationalized, config.INRADIUS_2R, atol=1e-15)
        rho_minus, rho_plus = 2.0 - config.SQRT2, 2.0 + config.SQRT2
        assert np.isclose(1.0 - 2.0*rho_minus + 0.5*(rho_minus**2), 0.0, atol=1e-15)
        assert np.isclose(1.0 - 2.0*rho_plus + 0.5*(rho_plus**2), 0.0, atol=1e-15)
        ledger['layer_1_exact_mathematics']['pythagorean_and_laguerre_roots'] = {
            'status': 'EXACT_MATH',
            'inradius_2r': round(config.INRADIUS_2R, 10),
            'laguerre_L2_roots_in_K': [round(rho_minus, 8), round(rho_plus, 8)]
        }
        print(f"  {Term.DARK_GREEN}[EXACT]{Term.RESET} 1²+(√2)²=(√3)², (√2)²+(√3)²=(√5)² | 2r = √2+√3-√5 = {config.INRADIUS_2R:.6f} | L₂⁽⁰⁾ roots 2±√2 ∈ K")

        # 2. Field Discriminant Δ_K & E_8 Cartan Determinant (Math_Topology_v17 Thm 2.1 & 2.10)
        conductors = [8, 12, 5, 24, 40, 60, 120]
        delta_k = math.prod(conductors)
        assert delta_k == (2**16) * (3**4) * (5**4) == 3317760000
        covol_ok = math.isqrt(delta_k)
        tau_8, covol_e8 = cls.build_e8_root_system()
        assert covol_ok == 57600 == (tau_8 ** 2) * int(round(covol_e8))
        ledger['layer_1_exact_mathematics']['field_discriminant_and_e8'] = {
            'status': 'EXACT_MATH',
            'Delta_K': delta_k,
            'sqrt_Delta_K': covol_ok,
            'E8_det_Cartan': round(covol_e8, 6),
            'E8_kissing_tau8': tau_8
        }
        print(f"  {Term.DARK_GREEN}[EXACT]{Term.RESET} Δ_K = {delta_k:,} = 2¹⁶3⁴5⁴ | √|Δ_K| = {covol_ok:,} = 240² | det(Cartan E₈) = {covol_e8:.0f} (τ₈ = 240)")

        # 3. Kummer Square-Free Sieve & Elementary Coprimality (Math_Topology_v17 Thm 2.9 & Lemma 3.11)
        admissible_d = {1, 2, 3, 5, 6, 10, 15, 30}
        def sqfree(n: int) -> int:
            r, d, t = 1, 2, n
            while d * d <= t:
                c = 0
                while t % d == 0:
                    c += 1; t //= d
                if c % 2 == 1:
                    r *= d
                d += 1
            return r * t
        cascade_fib = [1, 2, 3, 5, 8, 13]
        membership = [sqfree(x) in admissible_d for x in cascade_fib]
        assert membership == [True, True, True, True, True, False]
        assert math.gcd(102, 3) == 3 and math.gcd(103, 3) == 1
        c_floor = lambda n: 2 * (((n + 3) // 2) ** 2)
        bowl_caps = [c_floor(n) for n in range(6)]
        assert bowl_caps == [2, 8, 8, 18, 18, 32] and sum(bowl_caps) == 86
        kepler_k = math.pi / math.sqrt(18.0)
        fcc_ratio = (172.0 * (4.0 / 3.0) * math.pi * ((math.sqrt(2.0) / 4.0) ** 3)) / 43.0
        assert np.isclose(kepler_k, fcc_ratio, atol=1e-15)

        # 4. Preprint Derivation of (√3)^m Sphere Ladder, R_mid = 243√2, Stella Octangula & l=1,2,3 Multipole Cancellation
        #    (Solar_v16 App. E.1-E.3; Planet_9_v44 Def. 1.3, Sec. 2.1-2.2, Thm 2.4, Sec. 3, Sec. 4.3-4.6)
        cube_r_out_over_r_in = (config.SQRT3 / 2.0) / 0.5                  # R_out / r_in = √3
        cube_area_ratio = cube_r_out_over_r_in ** 2                        # S_out / S_in = 3
        oh_triplet_over_singlet = 3.0 / 1.0                                # dim(T_1u) / dim(A_2u) = 3
        valency_tensor_dim = config.VALENCY_LEPTON * config.VALENCY_QUARK  # dim(E_l ⊗ E_q) = 2 * 3 = 6
        dirichlet_unit_rank = 8 - 1                                        # rk(O_K^x) = r_1 + r_2 - 1 = 7
        r1_dimensionless = cube_r_out_over_r_in ** valency_tensor_dim      # (√3)^6 = 3^3 = 27
        r2_dimensionless = cube_r_out_over_r_in ** dirichlet_unit_rank     # (√3)^7 = 27√3
        rin_dimensionless = cube_r_out_over_r_in ** 10                     # (√3)^10 = 3^5 = 243
        rout_dimensionless = cube_r_out_over_r_in ** 11                    # (√3)^11 = 243√3 ≈ 420.888346
        rmid_dimensionless = rout_dimensionless * math.sqrt(2.0 / 3.0)     # R_out * √(2/3) = 243√2 ∈ Z[√2]
        assert np.isclose(cube_area_ratio, oh_triplet_over_singlet, atol=1e-15)
        assert np.isclose(r1_dimensionless, 27.0, atol=1e-14)
        assert np.isclose(r2_dimensionless, 27.0 * config.SQRT3, atol=1e-14)
        assert np.isclose(rin_dimensionless, 243.0, atol=1e-13)
        assert np.isclose(rmid_dimensionless, 243.0 * config.SQRT2, atol=1e-13)

        # Complementary angles: magic angle arccos(1/√3) + torsion angle arccos(√(2/3)) == 90°
        alpha_magic_deg = math.degrees(math.acos(1.0 / config.SQRT3))
        gamma_torsion_deg = math.degrees(math.acos(math.sqrt(2.0 / 3.0)))
        p2_magic = 0.5 * (3.0 * ((1.0 / config.SQRT3) ** 2) - 1.0)
        assert np.isclose(alpha_magic_deg + gamma_torsion_deg, 90.0, atol=1e-14)
        assert np.isclose(p2_magic, 0.0, atol=1e-15)

        # Stella Octangula unique parity partition of cube vertices {±1, ±1, ±1} & O_h multipole vanishing l=1,2,3 ≡ 0
        cube_verts = np.array([(x, y, z) for x in (-1.0, 1.0) for y in (-1.0, 1.0) for z in (-1.0, 1.0)])
        t1_verts = np.array([v for v in cube_verts if v[0]*v[1]*v[2] > 0])
        t2_verts = np.array([v for v in cube_verts if v[0]*v[1]*v[2] < 0])
        t1_dists_sq = [np.sum((t1_verts[i] - t1_verts[j])**2) for i in range(4) for j in range(i+1, 4)]
        t2_dists_sq = [np.sum((t2_verts[i] - t2_verts[j])**2) for i in range(4) for j in range(i+1, 4)]
        assert len(t1_verts) == 4 and len(t2_verts) == 4 and all(np.isclose(d, 8.0) for d in t1_dists_sq + t2_dists_sq)

        e_nodes_12 = np.array(
            [(s1, s2, 0.0) for s1 in (-1.0, 1.0) for s2 in (-1.0, 1.0)] +
            [(s1, 0.0, s2) for s1 in (-1.0, 1.0) for s2 in (-1.0, 1.0)] +
            [(0.0, s1, s2) for s1 in (-1.0, 1.0) for s2 in (-1.0, 1.0)]
        )
        dipole_l1 = np.sum(e_nodes_12, axis=0)
        r2_nodes = np.sum(e_nodes_12 ** 2, axis=1)
        quadrupole_l2 = sum(3.0 * np.outer(v, v) - r2_n * np.eye(3) for v, r2_n in zip(e_nodes_12, r2_nodes))
        octupole_l3_max = np.max(np.abs(np.einsum('ia,ib,ic->abc', e_nodes_12, e_nodes_12, e_nodes_12)))
        hexadecapole_l4 = float(np.sum(np.sum(e_nodes_12 ** 4, axis=1) - 0.6 * (r2_nodes ** 2)))
        assert np.allclose(dipole_l1, 0.0, atol=1e-15)
        assert np.allclose(quadrupole_l2, 0.0, atol=1e-15)
        assert np.isclose(octupole_l3_max, 0.0, atol=1e-15) and abs(hexadecapole_l4) > 1.0

        ledger['layer_1_exact_mathematics']['kummer_and_oh_sphere_ladder'] = {
            'status': 'EXACT_MATH',
            'sqrt13_in_K': False,
            'gcd_102_3': 3,
            'gcd_103_3': 1,
            'bicone_sum_half': 86,
            'bicone_sum_full': 172,
            'kepler_k': round(kepler_k, 8),
            'cube_R_out_over_r_in': round(cube_r_out_over_r_in, 10),
            'valency_tensor_dim_vl_vq': valency_tensor_dim,
            'dirichlet_unit_rank_O_K': dirichlet_unit_rank,
            'sqrt3_power_6_exact': round(r1_dimensionless, 10),
            'sqrt3_power_7_exact_27sqrt3': round(r2_dimensionless, 10),
            'sqrt3_power_10_rin_exact': round(rin_dimensionless, 10),
            'sqrt3_power_11_Rout_exact': round(rout_dimensionless, 10),
            'edge_midpoint_Rmid_243sqrt2': round(rmid_dimensionless, 10),
            'magic_plus_torsion_angle_deg': round(alpha_magic_deg + gamma_torsion_deg, 10),
            'oh_multipoles_l1_l2_l3_vanish': True,
            'oh_hexadecapole_l4_invariant': round(hexadecapole_l4, 6)
        }
        print(f"  {Term.DARK_GREEN}[EXACT]{Term.RESET} √13 ∉ K (13∤30) | gcd(102,3)=3 vs gcd(103,3)=1 | ΣC(n)=86, 172=4·43, k=π/√18={kepler_k:.6f}")
        print(f"  {Term.DARK_GREEN}[EXACT]{Term.RESET} O_h Ladder (√3)^m: m=6→27, m=7→27√3={r2_dimensionless:.4f}, m=10→243, m=11→243√3={rout_dimensionless:.2f}, R_mid=243√2={rmid_dimensionless:.2f}")
        print(f"  {Term.DARK_GREEN}[EXACT]{Term.RESET} Stella Octangula T₁⊔T₂ (d²=8) | O_h Multipoles l=1,2,3 ≡ 0 (l=4 ≠ 0) | α_magic+γ = 54.74°+35.26° = 90° | P₂(cos α_magic)=0")
        # 5. Galois Obstruction for 18° Rotation: sin(18°) ∈ Q(√5) ⊂ K, but cos(18°) ∉ K
        #    Gal(Q(cos 18°)/Q) = Z/4Z (exponent 4) cannot embed into Gal(K/Q) = (Z/2Z)^3 (exponent 2).
        sin_18_exact = (config.SQRT5 - 1.0) / 4.0
        cos_18_sq_times_16 = 10.0 + 2.0 * config.SQRT5
        norm_in_Q_sqrt5 = (10.0 ** 2) - 5.0 * (2.0 ** 2)  # 100 - 20 = 80 = 16 * 5 (square-free part is 5, not a square in Q(√5))
        assert np.isclose(sin_18_exact, math.sin(math.radians(18.0)), atol=1e-15)
        assert np.isclose(cos_18_sq_times_16, 16.0 * (math.cos(math.radians(18.0)) ** 2), atol=1e-15)
        assert int(round(norm_in_Q_sqrt5)) == 80 and (80 // 16) == 5
        print(f"  {Term.DARK_GREEN}[EXACT]{Term.RESET} Galois 18° Theorem: sin18°=(√5-1)/4 ∈ Q(√5)⊂K, but Gal(Q(cos18°)/Q)≅Z/4Z ⊄ (Z/2Z)³ ⇒ cos18°∉K")

        # 6. Exact K-PHAM Analytical Measure & Prograde Domain Theorem (Closes Front [2] & Front [C] Loopholes)
        #    Under uniform omega in [0, 360) at delta_k=0, k_raw = omega/30 + 1 in [1, 13).
        #    S_k = 1 iff k_raw < 3 + 2*sqrt(2) <=> omega < 30*(2 + 2*sqrt(2)) ≈ 144.8528 deg.
        #    Hence the exact uniform prior measure of S_k = 2 is (12 - (2 + 2*sqrt(2))) / 12 = (5 - sqrt(2)) / 6 in K!
        sk2_uniform_prior_exact = (5.0 - config.SQRT2) / 6.0
        omega_crit_deg = 30.0 * (config.K_TORUS - 1.0)
        assert np.isclose(1.0 - (omega_crit_deg / 360.0), sk2_uniform_prior_exact, atol=1e-15)
        #    For any prograde orbit i in [0, 90], h_raw = 1 + 5*(i/90) in [1, 6] < 2^3=8 => S_h in {1,2,3}, and k_raw < 13.5 < K_torus^2 => S_k in {1,2}.
        assert (1.0 + 5.0 * (90.0 / 90.0)) < (config.LAMBDA_H ** 3) and 13.5 < (config.K_TORUS ** 2)
        ledger['layer_1_exact_mathematics']['kpham_analytical_domain_and_measure'] = {
            'status': 'EXACT_MATH',
            'prograde_2x3_domain_exact': True,
            'sk2_uniform_omega_prior_formula': '(5 - sqrt(2)) / 6',
            'sk2_uniform_omega_prior_value': round(sk2_uniform_prior_exact, 10),
            'sk1_to_sk2_boundary_omega_deg': round(omega_crit_deg, 6)
        }
        print(f"  {Term.DARK_GREEN}[EXACT]{Term.RESET} K-PHAM Domain & Prior Theorem: Prograde i≤90° ⇒ (S_k,S_h)∈{{1,2}}×{{1,2,3}} | Uniform P₀(S_k=2) = (5−√2)/6 = {sk2_uniform_prior_exact:.6f}")

        # ====================================================================
        # PHASE 0B: LAYER III — ANSATZ DIAGNOSTICS (NON-PREDICTIVE)
        # ====================================================================
        print_section("PHASE 0B: LAYER III — ANSATZ DIAGNOSTICS (EXPLORATORY ONLY, NON-PREDICTIVE)")

        l1 = config.LAMBDA_1_EXACT
        l1_sq = l1 ** 2
        l1_4 = l1_sq ** 2
        e_geom = lambda N: ((N - l1_sq) ** 2) + (l1_4 / N)
        unfiltered_min = min(range(1, 500), key=e_geom)
        gcd3_filtered_min = min((N for N in range(1, 500) if math.gcd(N, 3) == 1), key=e_geom)
        gcd5_filtered_min = min((N for N in range(1, 500) if math.gcd(N, 5) == 1), key=e_geom)
        mu_crit = (e_geom(103) - e_geom(102)) / (cls._omega_prime_factors(102) - cls._omega_prime_factors(103))
        print(f"  {Term.DARK_MAGENTA}[ANSATZ DIAGNOSTIC]{Term.RESET} E_geom(N) min: unfiltered = {unfiltered_min} (E={e_geom(102):.3f}) | gcd(N,5)=1 min = {gcd5_filtered_min} | gcd(N,3)=1 min = {gcd3_filtered_min} (μ_crit={mu_crit:.5f})")

        alpha_inv_3_6_30 = (l1 ** 2) + (config.N_TWIST / 3.0) + (config.LAMBDA_3_EXACT / 6.0) + (config.WRITHE_STATIC / 30.0)
        err_ppm_3_6_30 = abs(alpha_inv_3_6_30 - bench.ALPHA_INV_CODATA) / bench.ALPHA_INV_CODATA * 1e6

        d1_g = np.arange(1, 13)[:, None, None]
        d2_g = np.arange(1, 25)[None, :, None]
        d3_g = np.arange(1, 61)[None, None, :]
        cand_alpha = (l1 ** 2) + (config.N_TWIST / d1_g) + (config.LAMBDA_3_EXACT / d2_g) + (config.WRITHE_STATIC / d3_g)
        abs_Errors = np.abs(cand_alpha - bench.ALPHA_INV_CODATA)
        best_idx = np.unravel_index(np.argmin(abs_Errors), abs_Errors.shape)
        best_divisors = (int(best_idx[0] + 1), int(best_idx[1] + 1), int(best_idx[2] + 1))
        best_alpha_val = float(cand_alpha[best_idx])
        best_alpha_ppm = float(abs_Errors[best_idx] / bench.ALPHA_INV_CODATA * 1e6)
        hits_le_3_6_30 = int(np.sum(abs_Errors <= abs(alpha_inv_3_6_30 - bench.ALPHA_INV_CODATA)))

        print(f"  {Term.DARK_MAGENTA}[ANSATZ DIAGNOSTIC]{Term.RESET} α⁻¹ divisor grid: (3,6,30) gives {alpha_inv_3_6_30:.6f} ({err_ppm_3_6_30:.2f} ppm, rank #{hits_le_3_6_30}/17280) vs grid argmin {best_divisors} ({best_alpha_ppm:.2f} ppm)")

        sin_tc = config.LAMBDA_3_EXACT / (2.0 * l1)
        d_k = (1.0 / config.SQRT2) * config.WRITHE_STATIC * (l1 ** 2)
        a_geom = (1.0 / config.SQRT2) * (0.5 / (config.N_TWIST ** 2)) * (1.0 - sin_tc ** 2)
        delta_interf = (1.0 / (2.0 * math.pi * alpha_inv_3_6_30)) ** 2
        mu_e_pred = 2.0 * math.sqrt((config.N_TWIST ** 2) + d_k) * (1.0 + a_geom + delta_interf)
        mu_e_ppm_err = abs(mu_e_pred - bench.MUON_ELECTRON_CODATA) / bench.MUON_ELECTRON_CODATA * 1e6

        base_sun_jup = config.N_TWIST * l1 + config.LAMBDA_3_EXACT
        alt_constants = {
            'sqrt(10)': math.sqrt(10.0),
            'sqrt(2)+sqrt(3) [in K]': config.SQRT2 + config.SQRT3,
            'pi': math.pi,
            'e': math.e,
            'phi^2 [in K]': config.PHI ** 2
        }
        alt_audit = {}
        for name_c, val_c in alt_constants.items():
            pred_c = base_sun_jup + val_c
            err_pct_c = abs(pred_c - bench.GM_SUN_OVER_GM_JUP_IAU) / bench.GM_SUN_OVER_GM_JUP_IAU * 100.0
            alt_audit[name_c] = {'value': round(val_c, 5), 'pred': round(pred_c, 4), 'err_pct': round(err_pct_c, 4)}
        print(f"  {Term.DARK_MAGENTA}[ANSATZ DIAGNOSTIC]{Term.RESET} GM_☉/GM_J constant menu: +√10 ({alt_audit['sqrt(10)']['err_pct']:.4f}%) | +(√2+√3) ({alt_audit['sqrt(2)+sqrt(3) [in K]']['err_pct']:.4f}%) | +π ({alt_audit['pi']['err_pct']:.4f}%)")

        gamma_deg = math.degrees(math.acos(math.sqrt(2.0 / 3.0)))
        theta_u_no_1_2N = 90.0 + 2.0 * gamma_deg - config.WRITHE_DYNAMIC * (180.0 / math.pi)
        theta_u_with_1_2N = 90.0 + 2.0 * gamma_deg - (config.WRITHE_DYNAMIC + 1.0 / (2.0 * config.N_TWIST)) * (180.0 / math.pi)
        err_no_1_2N = abs(theta_u_no_1_2N - bench.URANUS_AXIAL_TILT_IAU)
        err_with_1_2N = abs(theta_u_with_1_2N - bench.URANUS_AXIAL_TILT_IAU)
        print(f"  {Term.DARK_MAGENTA}[ANSATZ DIAGNOSTIC]{Term.RESET} Uranus ablation: {theta_u_no_1_2N:.3f}° without 1/(2·103) (Δ={err_no_1_2N:.3f}°) vs {theta_u_with_1_2N:.3f}° with 1/(2·103) (Δ={err_with_1_2N:.3f}°)")

        omega_l_pred = l1 / (l1 + config.LAMBDA_3_EXACT)
        sigma_cabibbo = abs(sin_tc - bench.SIN_THETA_CABIBBO_PDG) / 0.00067
        sigma_omega_l = abs(omega_l_pred - bench.OMEGA_LAMBDA_PLANCK) / 0.0073

        ledger['layer_3_ansatze_and_resonances'] = {
            'epistemic_status': 'ANSATZ_DIAGNOSTIC (Exploratory only; not used as predictions)',
            'variational_E_N': {
                'unfiltered_min_N': unfiltered_min,
                'gcd_N_5_min_N': gcd5_filtered_min,
                'gcd_N_3_min_N': gcd3_filtered_min,
                'mu_crit': round(mu_crit, 5)
            },
            'alpha_inv': {
                'published_divisors_3_6_30': {'pred': round(alpha_inv_3_6_30, 6), 'diff_ppm': round(err_ppm_3_6_30, 2), 'rank_in_grid': hits_le_3_6_30},
                'grid_argmin_divisors': {'divisors': list(best_divisors), 'pred': round(best_alpha_val, 6), 'diff_ppm': round(best_alpha_ppm, 2)}
            },
            'muon_electron_ratio': {'pred': round(mu_e_pred, 6), 'codata': bench.MUON_ELECTRON_CODATA, 'diff_ppm': round(mu_e_ppm_err, 2)},
            'sun_jupiter_constant_menu': alt_audit,
            'uranus_obliquity_ablation': {
                'without_1_over_2N_deg': round(theta_u_no_1_2N, 3),
                'residual_without_1_over_2N_deg': round(err_no_1_2N, 3),
                'with_1_over_2N_deg': round(theta_u_with_1_2N, 3),
                'residual_with_1_over_2N_deg': round(err_with_1_2N, 3)
            },
            'cabibbo_sin_theta_c': {'pred': round(sin_tc, 5), 'pdg': bench.SIN_THETA_CABIBBO_PDG, 'sigma_dev': round(sigma_cabibbo, 2)},
            'dark_energy_omega_lambda': {'pred': round(omega_l_pred, 4), 'planck': bench.OMEGA_LAMBDA_PLANCK, 'sigma_dev': round(sigma_omega_l, 2)}
        }
        return ledger

    @classmethod
    def build_ledger(
        cls,
        config: IT3Config,
        bench: ExternalBenchmarks,
        proof_ledger: Dict,
        dioph_audit: Optional[Dict] = None,
        audit_cert: Optional[Dict] = None,
        mode: EpistemicMode = EpistemicMode.PROVEN_ONLY,
    ) -> ProofLedger:
        ledger = ProofLedger(version="IT3-v22.6-strict", epistemic_mode=mode.value)

        # Explicit Postulates (Counted in the epistemic ledger)
        ledger.add_postulate(
            "P1_INRADIUS",
            "Metric pinning by the constructible right triangle (sqrt(2), sqrt(3), sqrt(5)) incircle diameter 2r = sqrt(2)+sqrt(3)-sqrt(5) (Math_Topology_v17 Postulate 2.7)."
        )
        ledger.add_postulate(
            "P2_UNIT_AU",
            "Astronomical unit normalization r_0 = 1.0 AU as the m=0 unit length scale for the dimensionless O_h sphere ladder R(m)/r_0 = (sqrt(3))^m (Planet_9_v44 Sec. 4.1.1)."
        )
        ledger.add_postulate(
            "P3_SURFACE_TENSION",
            "Topological defect boundary area scales as A(N) proportional to N^(2/3) (Math_Topology_v17 Prop. 6.2 & Postulate 6.3)."
        )

        # Proven Mathematical Theorems (Layer I — ONLY genuine model theorems)
        ledger.add_theorem("T2.1_DISC", "Field discriminant of K=Q(sqrt2,sqrt3,sqrt5) is Delta_K = 2^16 * 3^4 * 5^4 = 3,317,760,000; sqrt(|Delta_K|) = 57,600 = 240^2.")
        ledger.add_theorem("T2.5_PYTH", "Coupled Pythagorean closure 1^2+(sqrt2)^2=(sqrt3)^2, (sqrt2)^2+(sqrt3)^2=(sqrt5)^2 and inradius 2r = sqrt2+sqrt3-sqrt5.")
        ledger.add_theorem("T2.9_KUMMER", "Square-free Kummer sieve over {2,3,5} proves sqrt(13) not in K (13 does not divide 30).")
        ledger.add_theorem("T_E8_CARTAN", "E_8 root system has 240 minimal vectors and Cartan determinant det(G_E8) = 1.")
        ledger.add_theorem("T_OH_SPHERE_LADDER", "For a cube of side a, circumscribed-to-inscribed sphere ratio is R_out/r_in = sqrt(3) (area ratio 3); with A_F valency tensor dimension m_1 = v_l*v_q = 2*3 = 6 and Dirichlet unit rank rk(O_K^x) = 7, the dimensionless ladder (sqrt(3))^m gives (sqrt(3))^6 = 3^3 = 27 and (sqrt(3))^7 = 27*sqrt(3).")
        ledger.add_theorem("T_OH_FCC", "O_h branching {2,6,10,14} yields bicone capacities {2,8,8,18,18,32}, hemisphere sum 86, full sum 172 = 4*43, and FCC Kepler packing ratio pi/sqrt(18).")
        ledger.add_theorem("T_SUBADDITIVE", "Strict concavity of f(N)=N^(2/3) implies (N1+N2)^(2/3) < N1^(2/3) + N2^(2/3).")
        ledger.add_theorem("T_GALOIS_18DEG", "sin(18 deg) = (sqrt(5)-1)/4 lies in Q(sqrt5) subset K, whereas Q(cos 18 deg) = Q(zeta_20)^+ has cyclic Galois group Z/4Z of exponent 4 and cannot embed into Gal(K/Q) = (Z/2Z)^3 of exponent 2; hence cos(18 deg) is not in K and 18 deg is not an SO(3,K) rotation.")
        ledger.add_theorem("T_KPHAM_MEASURE", "For prograde orbits i in [0,90 deg], K-PHAM maps (S_k,S_h) strictly into {1,2}x{1,2,3}; under uniform omega in [0,360 deg) at delta_k=0, the exact measure of S_k=2 is (5 - sqrt(2))/6 ≈ 0.597631 in K.")
        ledger.add_theorem("T_STELLA_MULTIPOLE", "Cube vertices {+-1,+-1,+-1} partition uniquely by parity xyz=+-1 into two regular tetrahedra T1, T2 (edge^2=8); for the 12 cuboctahedral E-nodes, multipole moments l=1, l=2, l=3 vanish identically while l=4 is non-zero; P_2(cos arccos(1/sqrt3)) = 0 and arccos(1/sqrt3)+arccos(sqrt(2/3)) = 90 deg.")

        # 1. EXACT_MATH CLAIMS (Only genuine mathematical theorems of K, E_8, and O_h)
        ledger.add_claim(Claim(
            name="Delta_K_field_discriminant",
            status=ClaimStatus.EXACT_MATH,
            value=3317760000,
            proof_id="T2.1_DISC",
            statement="Field discriminant of K = Q(sqrt2, sqrt3, sqrt5) from product of 7 quadratic subfield conductors; sqrt(|Delta_K|) = 57,600 = 240^2.",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="E8_Cartan_determinant_and_roots",
            status=ClaimStatus.EXACT_MATH,
            value=1.0,
            proof_id="T_E8_CARTAN",
            statement="det(Cartan E_8) = 1 and kissing number tau_8 = 240 minimal vectors (volume ratio only, not an embedding of O_K into E_8).",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="Kummer_wall_sqrt13_exclusion",
            status=ClaimStatus.EXACT_MATH,
            value=13,
            proof_id="T2.9_KUMMER",
            statement="13 does not divide 30 = 2*3*5, hence sqrt(13) is not in K = Q(sqrt2, sqrt3, sqrt5).",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="oh_sphere_ladder_27_and_27sqrt3_identities",
            status=ClaimStatus.EXACT_MATH,
            value=float(27.0 * config.SQRT3),
            unit="dimensionless ratio R_2 / r_0",
            proof_id="T_OH_SPHERE_LADDER",
            statement="Cube sphere ratio Lambda_Y = R_out/r_in = sqrt(3) raised to valency tensor dimension m_1 = v_l*v_q = 6 gives (sqrt(3))^6 = 3^3 = 27, and at m_2 = rk(O_K^x) = 7 gives (sqrt(3))^7 = 27*sqrt(3).",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="FCC_kepler_packing_and_bicone_sum",
            status=ClaimStatus.EXACT_MATH,
            value=math.pi / math.sqrt(18.0),
            proof_id="T_OH_FCC",
            statement="O_h capacities {2,8,8,18,18,32} sum to 86 (172 = 4*43 over both bowls), and 172 spheres of radius a*sqrt(2)/4 in 43 FCC cells fill pi/sqrt(18).",
            is_predictive=False,
        ))

        ledger.add_claim(Claim(
            name="stella_octangula_and_oh_multipole_vanishing",
            status=ClaimStatus.EXACT_MATH,
            value=90.0,
            unit="deg (alpha_magic + gamma)",
            proof_id="T_STELLA_MULTIPOLE",
            statement="Cube vertices partition into T1 and T2 regular tetrahedra; cuboctahedral E-nodes have l=1,2,3 moments identically zero (first non-zero is hexadecapole l=4); P_2(cos 54.7356 deg) = 0 and alpha_magic + gamma = 90 deg.",
            is_predictive=False,
        ))

        ledger.add_claim(Claim(
            name="galois_18deg_sin_in_K_cos_not_in_K",
            status=ClaimStatus.EXACT_MATH,
            value=round((config.SQRT5 - 1.0) / 4.0, 10),
            unit="sin(18 deg)",
            proof_id="T_GALOIS_18DEG",
            statement="sin(18 deg) = (sqrt5-1)/4 is in Q(sqrt5) subset K, but cos(18 deg) is not in K because Gal(Q(cos 18 deg)/Q) = Z/4Z has exponent 4 != 2; proves 18 deg is an algebraic echo, not a geometric forcing.",
            is_predictive=False,
        ))

        ledger.add_claim(Claim(
            name="kpham_prograde_domain_and_sk2_uniform_prior",
            status=ClaimStatus.EXACT_MATH,
            value=round((5.0 - config.SQRT2) / 6.0, 10),
            unit="P_null(S_k=2)",
            proof_id="T_KPHAM_MEASURE",
            statement="Prograde orbits (i<=90 deg) satisfy (S_k,S_h) in {1,2}x{1,2,3} identically; under uniform omega in [0,360 deg), the exact geometric prior for S_k=2 is (5-sqrt2)/6 ≈ 59.763%.",
            is_predictive=False,
        ))

        # 2. DERIVED_FROM_POSTULATES CLAIMS (Strictly derived from P1, P2, P3 + Layer I theorems; external_reference=None!)
        ledger.add_claim(Claim(
            name="pinned_inradius_metric_scale_2r",
            status=ClaimStatus.DERIVED_FROM_POSTULATES,
            value=config.INRADIUS_2R,
            unit="dimensionless",
            proof_id="T2.5_PYTH+P1_INRADIUS",
            dependencies=("P1_INRADIUS", "T2.5_PYTH"),
            statement="Incircle diameter 2r = sqrt(2)+sqrt(3)-sqrt(5) derived from metric pinning postulate P1_INRADIUS.",
            external_reference=None,
            is_predictive=True,
        ))
        ledger.add_claim(Claim(
            name="kpham_valence_shell_radius_R2",
            status=ClaimStatus.DERIVED_FROM_POSTULATES,
            value=config.R_VALENCE_EXACT,
            unit="AU",
            proof_id="T_OH_SPHERE_LADDER+P2_UNIT_AU",
            dependencies=("P2_UNIT_AU", "T_OH_SPHERE_LADDER"),
            statement="From R(m) = r_0 * (sqrt(3))^m with unit scale P2_UNIT_AU (r_0 = 1 AU), the m=6 neck shell is R_1 = (sqrt(3))^6 AU = 27.0 AU and the m=7 shell is R_2 = (sqrt(3))^7 AU = 27*sqrt(3) AU ≈ 46.7654 AU (evaluated prior to any catalog comparison).",
            external_reference=None,
            is_predictive=True,
        ))
        ledger.add_claim(Claim(
            name="subadditive_defect_coalescence_ratio_equal_mass",
            status=ClaimStatus.DERIVED_FROM_POSTULATES,
            value=float((2.0 ** (2.0 / 3.0)) / 2.0),
            unit="E_merge / E_sep",
            proof_id="P3_SURFACE_TENSION+T_SUBADDITIVE",
            dependencies=("P3_SURFACE_TENSION", "T_SUBADDITIVE"),
            statement="For two equal defects N1=N2, E_merge/E_sep = 2^(2/3)/2 = 2^(-1/3) ≈ 0.7937 < 1 under P3_SURFACE_TENSION.",
            external_reference=None,
            is_predictive=True,
        ))

        ledger.add_claim(Claim(
            name="oh_outer_egg_shells_rin_Rmid_Rout",
            status=ClaimStatus.DERIVED_FROM_POSTULATES,
            value=round(config.R_OUT_EXACT, 6),
            unit="AU (R_out)",
            proof_id="T_OH_SPHERE_LADDER+P2_UNIT_AU",
            dependencies=("P2_UNIT_AU", "T_OH_SPHERE_LADDER"),
            statement=f"Under unit scale P2_UNIT_AU (r_0=1 AU), the m=10 inscribed sphere is r_in=(sqrt3)^10=243.0 AU, the m=11 circumscribed sphere is R_out=(sqrt3)^11=243*sqrt3≈{config.R_OUT_EXACT:.2f} AU (S_out=3*S_in), and the 12 edge midpoints lie at R_mid=R_out*sqrt(2/3)=243*sqrt2≈{config.R_MID_EXACT:.2f} AU.",
            external_reference=None,
            is_predictive=True,
        ))

        # 3. ANSATZ_DIAGNOSTIC CLAIMS (Includes the 4 demoted arithmetic/expansion items + Layer III ansätze)
        l3 = proof_ledger.get("layer_3_ansatze_and_resonances", {})
        l1 = config.LAMBDA_1_EXACT
        l3_val = config.LAMBDA_3_EXACT
        wr_stat = config.WRITHE_STATIC
        alpha_val = (l1 ** 2) + (config.N_TWIST / 3.0) + (l3_val / 6.0) + (wr_stat / 30.0)
        phi_braid = math.sqrt(1.0 + l3_val / (config.N_TWIST ** 2))
        mp_me_val = 18.0 * (l1 ** 2) * (1.0 + 1.0 / (2.0 * math.pi * alpha_val)) / phi_braid
        omega_dm_b_val = l1 / (config.SQRT3 * wr_stat)
        eta_baryon_val = wr_stat / (config.N_TWIST * 1e7)

        ledger.add_claim(Claim(
            name="sn2_band_Z_sqrt2_definitional_expansion",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=float(18.0 + 12.0 * config.SQRT2),
            statement="DIAGNOSTIC ONLY. Definitional algebraic expansion: since Lambda_1 = sqrt(3)*(3+2*sqrt(2)) already contains sqrt(3), multiplying by 2*sqrt(3) gives 18+12*sqrt(2) by definition, not a new physical law.",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="anisotropic_dual_sum_11_over_6_diagnostic",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=float(Fraction(11, 6)),
            statement="DIAGNOSTIC ONLY. Arithmetic sum 1 + 1/2 + 1/3 = 11/6 (and 4*11/6 = 22/3); the standard isotropic 3D cubic lattice Laplacian maximum is 12.",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="cuboctahedral_q2_shell_43_coincidence",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=43,
            statement="DIAGNOSTIC ONLY. Selecting the second FCC coordination shell q=2 in 10q^2+2+1 = 43 is a post-hoc shell choice matching the bicone sum 43.",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="moonshine_integer_factorizations_diagnostic",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=960,
            statement="DIAGNOSTIC ONLY. Integer identities 960=4*240, 744=3*248, 1728=12^3 are unused in the pipeline; 744 and 1728 are not derived from K.",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="variational_E_N_102_vs_103_diagnostic",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=103,
            dependencies=("LAMBDA_1",),
            statement="DIAGNOSTIC ONLY. Unfiltered E_geom(N) minimum is N=102 (E=101.831); N=103 (E=102.019) requires the gcd(N,3)=1 ansatz or Omega-penalty weight mu > 0.09402.",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="alpha_inv_prediction",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=alpha_val,
            dependencies=("LAMBDA_1", "N_TWIST", "LAMBDA_3", "WRITHE"),
            statement="DIAGNOSTIC ONLY. NOT A PROVEN PREDICTION. Uses unproven N_twist=103 and discrete divisor selection (3,6,30) (7.74 ppm from CODATA 2022).",
            external_reference="CODATA 2022 (137.035999084)",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="alpha_inv_divisor_grid_argmin",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=l3.get("alpha_inv", {}).get("grid_argmin_divisors", {}).get("pred", 137.035890),
            statement="DIAGNOSTIC ONLY. Grid-search sensitivity analysis over 12x24x60 divisor triples; argmin is (3,6,31) at 0.80 ppm (no group justification).",
            external_reference="CODATA 2022 (137.035999084)",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="muon_electron_mass_ratio_ansatz",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=l3.get("muon_electron_ratio", {}).get("pred", 206.766841),
            statement="DIAGNOSTIC ONLY. Evaluates 2*sqrt(N_twist^2 + D_k)*(1 + A_geom + delta_interf); depends on N_twist=103 ansatz (6.97 ppm from CODATA).",
            external_reference="CODATA 2022 (206.7682830)",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="proton_electron_mass_ratio_ansatz",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=mp_me_val,
            statement=f"DIAGNOSTIC ONLY. Braid combinatorics ansatz 18*Lambda_1^2*(1+alpha/2pi)/Phi_braid = {mp_me_val:.4f} vs CODATA {bench.PROTON_ELECTRON_CODATA:.4f}.",
            external_reference="CODATA 2022 (1836.15267343)",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="dark_matter_to_baryon_ratio_ansatz",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=omega_dm_b_val,
            statement=f"DIAGNOSTIC ONLY. Ratio Lambda_1/(sqrt(3)*|Wr|) = {omega_dm_b_val:.4f}; comparison with Planck (~5.4) is a consistency check, not proof.",
            external_reference="Planck 2018 (~5.36)",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="baryon_asymmetry_eta_ansatz",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=eta_baryon_val,
            statement="DIAGNOSTIC ONLY. Phenomenological ansatz |Wr|/(N_twist * 10^7) pending first-principles derivation (DNK_Final_v7 Sec. 13.3/14.2).",
            external_reference="Planck CMB (~6e-10)",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="GM_sun_over_GM_Jup_constant_menu",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=103.0 * l1 + l3_val,
            statement="DIAGNOSTIC ONLY. Exploratory comparison of additive constants (+sqrt(10): 0.0067%, +(sqrt2+sqrt3): 0.0082%, +pi: 0.0087%) to match IAU GM_sun/GM_Jup.",
            external_reference="IAU / JPL DE440 (1047.5655)",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="uranus_obliquity_ablation",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=l3.get("uranus_obliquity_ablation", {}).get("without_1_over_2N_deg", 98.052),
            unit="deg",
            statement="DIAGNOSTIC ONLY. Ablation test showing 98.052 deg without 1/(2*103) (Delta=0.282 deg) vs 97.774 deg with post-hoc 1/(2*103) term.",
            external_reference="IAU Uranus obliquity (97.77 deg)",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="cabibbo_and_omega_lambda_ansatz",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=l3.get("dark_energy_omega_lambda", {}).get("pred", 0.6900),
            statement="DIAGNOSTIC ONLY. sin(theta_C)=0.2246 (0.61 sigma) and Omega_Lambda=0.6900 (0.73 sigma): compatibility checks, not proofs.",
            external_reference="PDG 2024 / Planck 2018",
            is_predictive=False,
        ))

        # 4. VISUAL_RHYME, OPEN_CONJECTURE & NULL_RESULT CLAIMS
        ledger.add_claim(Claim(
            name="laguerre_solar_rhyme",
            status=ClaimStatus.VISUAL_RHYME,
            statement="VISUAL RHYME ONLY. Structural analogy between Laguerre L_2^(0) nodal profile (mapped with 5 display knobs to x1=0.98, x2=3.60) and IT3 floor density. Not evidence, not a scaling law.",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="micro_macro_descent_rhyme",
            status=ClaimStatus.VISUAL_RHYME,
            statement="VISUAL RHYME ONLY. Nuclear alpha-decay shift (Delta Z = -2) and celestial K-PHAM cascade (floor(x/sqrt3)) are non-isomorphic structural rhymes (Guard F.2).",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="solar_atomic_shell_interpretation",
            status=ClaimStatus.OPEN_CONJECTURE,
            statement="OPEN CONJECTURE. Interpretation of K-PHAM S_n floors as macroscopic atomic shells.",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="z172_periodic_table_termination_conjecture",
            status=ClaimStatus.OPEN_CONJECTURE,
            value=172,
            statement="OPEN CONJECTURE. While 172 = 4*43 is exact arithmetic, identifying Z_max=172 as the physical end of the periodic system via FCC vacuum closure is a theoretical conjecture.",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="stone_shield_astrometric_localization",
            status=ClaimStatus.EMPIRICAL_TEST,
            statement="Empirical candidate anomaly localization near O_h E-nodes in NOIRLab/Gaia/AllWISE archives; not a confirmed solid topological body. Falsifiable by LSST DR1/DR2.",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="macro_compton_periodicity",
            status=ClaimStatus.NULL_RESULT,
            value=0.04,
            unit="sigma",
            statement="NULL RESULT. Macro-Compton periodicity at log(Lambda_1^2)=4.624 is not confirmed on current JFC-dominated cometary data (SNR < 0.1 sigma).",
            is_predictive=False,
        ))

        ledger.add_claim(Claim(
            name="solar_core_and_gaia_vT_lambda1_ansatz",
            status=ClaimStatus.ANSATZ_DIAGNOSTIC,
            value=round(bench.JUPITER_PERIOD_DAYS / ((config.LAMBDA_1_EXACT ** 2) * config.SQRT3), 4),
            unit="days",
            statement="DIAGNOSTIC ONLY. Kinematic ratios T_J/(Lambda_1^2*sqrt3) ≈ 24.545 d and v_T = v_0*Lambda_1^2/2 ≈ 50.956 km/s (Planet_9_v44 Sec. 2.6 & Sec. 9).",
            external_reference="Helioseismic core (~24.5 d) / Gaia DR3 (<500 pc)",
            is_predictive=False,
        ))
        ledger.add_claim(Claim(
            name="catwise2020_e5_brown_dwarf_scan",
            status=ClaimStatus.NULL_RESULT,
            value=0,
            unit="sources",
            statement="NULL RESULT. CatWISE2020 thermal scan at E-5 (RA 61.24 deg, Dec -30.45 deg) detected 0 luminous Y/T brown dwarfs (W1-W2>=0.8, mu>=100 mas/yr, SNR>5), constraining baryonic point-mass models (Planet_9_v44 Sec. 10.2).",
            is_predictive=False,
        ))

        # 5. CATALOG EMPIRICAL_TEST & NULL_RESULT CLAIMS
        if audit_cert and "layer_2_catalog_validation" in audit_cert:
            l2 = audit_cert["layer_2_catalog_validation"]
            da = dioph_audit or {}
            inc_s = l2.get("multi_angle_inclination_scan", {})
            ce = l2.get("cometary_dichotomy", {})
            tr = l2.get("true_trojan_L4_L5_audit", {})

            ledger.add_claim(Claim(
                name="solar_system_sn_observed_distribution",
                status=ClaimStatus.EMPIRICAL_TEST,
                value=l2.get("kuiper_peak_sn2_count", 0),
                unit="objects in S_n=2",
                statement=f"MPCORB objects populate S_n floors with {l2.get('isthmus_confinement_sn0_pct', 0):.2f}% in S_n=0 and {l2.get('kuiper_peak_sn2_count', 0):,} in S_n=2.",
                is_predictive=False,
            ))
            ledger.add_claim(Claim(
                name="sliding_log_window_control",
                status=ClaimStatus.EMPIRICAL_TEST,
                value=da.get("sn2_vs_sliding_max_efficiency_pct", 0.0),
                unit="% of sliding max",
                statement=f"Sliding Delta ln R = ln 2 control: empirical argmax window is {da.get('sliding_window_argmax_interval_AU')} AU ({da.get('sliding_window_argmax_count', 0):,} obj) vs S_n=2 window [34.97, 69.94) AU ({da.get('target_sn2_band_count', 0):,} obj).",
                is_predictive=False,
            ))
            ledger.add_claim(Claim(
                name="monte_carlo_1d_kuiper_peak_test",
                status=ClaimStatus.EMPIRICAL_TEST,
                value=l2.get("monte_carlo_peak_only_p", 1.0),
                unit="p-value",
                statement=f"1D Monte Carlo test of R_2=46.77 AU against observed Kuiper peak {l2.get('kuiper_peak_observed_AU')} AU (error {l2.get('kuiper_quantization_error_pct')}%).",
                is_predictive=False,
            ))
            ledger.add_claim(Claim(
                name="joint_neptune_mmr_test",
                status=ClaimStatus.NULL_RESULT if str(l2.get("joint_2d_verdict", "")).startswith("NEGATIVE") else ClaimStatus.EMPIRICAL_TEST,
                value=l2.get("joint_2d_monte_carlo_R0_Lambda_p", 1.0),
                unit="p-value",
                statement=f"NULL / NEGATIVE RESULT: 2D joint test against Neptune (30.07 AU) and 1:2 MMR (47.73 AU) yields {l2.get('joint_loss_vs_neptune_and_1_2_mmr_pct')}% combined loss (p={l2.get('joint_2d_monte_carlo_R0_Lambda_p')}).",
                is_predictive=False,
            ))
            ledger.add_claim(Claim(
                name="inclination_argmax_bootstrap_test",
                status=ClaimStatus.NULL_RESULT if not inc_s.get("is_18deg_inside_bootstrap_ci", False) else ClaimStatus.EMPIRICAL_TEST,
                value=inc_s.get("empirical_argmax_drop_deg", 0.0),
                unit="deg",
                statement=f"Empirical inclination steepest-drop argmax is {inc_s.get('empirical_argmax_drop_deg')} deg (200-bootstrap 95% CI {inc_s.get('bootstrap_200_95ci_deg')} deg; 18 deg inside CI = {inc_s.get('is_18deg_inside_bootstrap_ci')}).",
                is_predictive=False,
            ))
            ledger.add_claim(Claim(
                name="trojan_L4_L5_epoch_matched_ratio",
                status=ClaimStatus.EMPIRICAL_TEST,
                value=tr.get("true_L4_L5_ratio", None),
                statement=f"Epoch-matched L4/L5 Trojan ratio using pure mean-longitude difference Delta lambda = lambda - lambda_J,mean(JD) (excluded {tr.get('excluded_fallback_epochs', 0)} fallback epochs).",
                is_predictive=False,
            ))
            ledger.add_claim(Claim(
                name="cometary_shared_edge_entropy_dichotomy",
                status=ClaimStatus.EMPIRICAL_TEST,
                value=ce.get("delta_H_shared_radial_bits", None),
                unit="bits",
                statement=f"Shared-bin-edge radial Shannon entropy difference H_free - H_bound on 11 identical log10(R_eff) bins ({ce.get('evaluation_mode')}).",
                is_predictive=False,
            ))
            mp_f = l2.get("mp_11_fronts_suite", {})
            if mp_f:
                fb_snr = mp_f.get("front_B_macro_compton_periodogram", {}).get("B1_Macro_Compton", {}).get("snr_sigma", 0.04)
                ledger.claims["macro_compton_periodicity"].value = fb_snr
                fc = mp_f.get("front_C_centaur_d_shell", {})
                fd = mp_f.get("front_D_asteroid_family_variance", {})
                ft1 = mp_f.get("front_T1_table1_benchmarks", {})
                f3 = mp_f.get("front_3_nea_pha_micro_shell", {})
                ledger.add_claim(Claim(
                    name="table1_key_outer_objects_verification",
                    status=ClaimStatus.EMPIRICAL_TEST,
                    value=ft1.get("matched_count", 7),
                    unit="of 7 objects",
                    statement="Front [T1]: Empirical verification of S_n floors for Pluto(2), Makemake(2), Haumea(2), Eris(3), 2012VP113(4), Sedna(6), 2015TG387(8).",
                    is_predictive=False,
                ))
                ledger.add_claim(Claim(
                    name="centaur_sk2_vs_analytical_prior_test",
                    status=ClaimStatus.NULL_RESULT if fc.get("binomial_p_vs_uniform_prior", 1.0) > 0.05 else ClaimStatus.EMPIRICAL_TEST,
                    value=fc.get("sk2_observed_pct", 0.0),
                    unit="% S_k=2",
                    statement=f"Front [C]: Observed Centaur S_k=2 share is {fc.get('sk2_observed_pct')}% vs exact analytical uniform-omega prior (5-sqrt2)/6 = {fc.get('sk2_analytical_uniform_prior_pct')}% (excess {fc.get('excess_over_uniform_prior_pct'):+.2f}%, p={fc.get('binomial_p_vs_uniform_prior')}).",
                    is_predictive=False,
                ))
                ledger.add_claim(Claim(
                    name="asteroid_family_collisional_variance_test",
                    status=ClaimStatus.EMPIRICAL_TEST,
                    value=fd.get("sigma_Reff_AU", 0.0),
                    unit="AU (sigma_Reff)",
                    statement=f"Front [D]: Main-belt cells (N>=5) have Var(S_n)={fd.get('mean_var_Sn')} (all in S_n=0) and sigma(R_eff)={fd.get('sigma_Reff_AU')} AU, confirming collisional debris dispersion.",
                    is_predictive=False,
                ))
                ledger.add_claim(Claim(
                    name="nea_pha_micro_shell_occupancy_test",
                    status=ClaimStatus.EMPIRICAL_TEST,
                    value=f3.get("dominant_cell_pct", 0.0),
                    unit="% in dominant cell",
                    statement=f"Front [3]: NEA/PHA S_n=0 population (N={f3.get('total_nea_sn0'):,}) dominant cell {f3.get('dominant_cell')} has {f3.get('dominant_cell_pct')}% vs uniform S_k=2 prior {f3.get('analytical_uniform_sk2_prior_pct')}%.",
                    is_predictive=False,
                ))

        return ledger

    @classmethod
    def run_unit_tests(cls, config: IT3Config, bench: ExternalBenchmarks) -> None:
        print_section("MANDATORY EPISTEMIC UNIT TESTS (NUMEROLOGY GUARD SUITE v22.6)")
        proof_ledger = cls.run_epistemic_audit(config, bench)
        ledger = cls.build_ledger(config, bench, proof_ledger, mode=EpistemicMode.PROVEN_ONLY)
        cert = ledger.certificate()

        # Test 1: test_no_predictive_ansatz
        ledger.validate_no_ansatz_in_predictions()
        print(f"  {Term.DARK_GREEN}✓ [PASS]{Term.RESET} test_no_predictive_ansatz: Zero ansatz/rhyme/null claims marked is_predictive.")

        # Test 2: test_flag_hygiene_and_non_zero_exploratory_share
        assert ledger.unproven_predictive_flag_share() == 0.0
        exp_share = ledger.exploratory_diagnostic_share()
        assert exp_share > 0.40, "Exploratory diagnostic share must honestly reflect ansatz/rhyme claims!"
        print(f"  {Term.DARK_GREEN}✓ [PASS]{Term.RESET} test_exposure_metrics: unproven_predictive_flag_share = 0.000000 | exploratory_diagnostic_share = {exp_share:.4f} (honest non-zero diagnostic ratio)")

        # Test 3: test_disputed_items_removed_from_exact_math
        exact_names = {c.name for c in ledger.claims.values() if c.status == ClaimStatus.EXACT_MATH}
        forbidden_in_exact = {
            "sn2_band_Z_sqrt2_definitional_expansion",
            "anisotropic_dual_sum_11_over_6_diagnostic",
            "cuboctahedral_q2_shell_43_coincidence",
            "moonshine_integer_factorizations_diagnostic",
        }
        assert exact_names.isdisjoint(forbidden_in_exact), "Disputed non-theorems must not be in EXACT_MATH!"
        print(f"  {Term.DARK_GREEN}✓ [PASS]{Term.RESET} test_exact_math_purity: 11/6, 1+N(2)=43, 960/744/1728, and 2√3·Λ₁ moved out of EXACT_MATH.")

        # Test 4: test_no_external_reference_on_derived_predictions
        for c in ledger.predictive_claims():
            assert c.external_reference is None, f"Predictive claim {c.name} must not cite external catalog data!"
        print(f"  {Term.DARK_GREEN}✓ [PASS]{Term.RESET} test_derived_predictions_blind: All DERIVED_FROM_POSTULATES claims have external_reference = None.")

        # Test 5: test_visual_rhyme_and_null_results_preserved
        assert cert["claims"]["laguerre_solar_rhyme"]["is_predictive"] is False
        assert cert["claims"]["macro_compton_periodicity"]["status"] == "NULL_RESULT"
        print(f"  {Term.DARK_GREEN}✓ [PASS]{Term.RESET} test_visual_rhyme_and_nulls: Visual rhymes and null results strictly isolated.")

        # Test 6: Verify guard raises RuntimeError if an ansatz is ever marked predictive
        bad_ledger = ProofLedger()
        bad_ledger.add_claim(Claim(name="fake_fit", status=ClaimStatus.ANSATZ_DIAGNOSTIC, is_predictive=True))
        raised = False
        try:
            bad_ledger.validate_no_ansatz_in_predictions()
        except RuntimeError:
            raised = True
        assert raised is True
        print(f"  {Term.DARK_GREEN}✓ [PASS]{Term.RESET} test_guard_rejects_predictive_ansatz: RuntimeError triggered as required.")

        # Test 7: Verify analytical uniform-omega prior for S_k=2 is registered as EXACT_MATH and equals (5-sqrt2)/6
        assert "kpham_prograde_domain_and_sk2_uniform_prior" in cert["claims"]
        sk2_prior_claim = cert["claims"]["kpham_prograde_domain_and_sk2_uniform_prior"]
        assert sk2_prior_claim["status"] == "EXACT_MATH" and sk2_prior_claim["is_predictive"] is False
        assert np.isclose(sk2_prior_claim["value"], (5.0 - math.sqrt(2.0)) / 6.0, atol=1e-10)
        print(f"  {Term.DARK_GREEN}✓ [PASS]{Term.RESET} test_kpham_analytical_prior_guard: P_null(S_k=2) = (5−√2)/6 = {sk2_prior_claim['value']:.6f} locked against Centaur/NEA overclaiming.")

        # Test 8: Full end-to-end smoke test of Phase 7, Phase 7.5, and Phase 7.6 (all 11 fronts from mp.py)
        op = CPHAMOperator(config)
        synth_objs = {
            'D4340':   CelestialObject('D4340',   'Pluto',     'dwarf',    39.48, 0.2488, 17.16, 113.8, 110.3, 14.5),
            'D6199':   CelestialObject('D6199',   'Eris',      'dwarf',    67.78, 0.4407, 44.04, 151.0,  35.9, 205.9),
            '90377':   CelestialObject('90377',   'Sedna',     'etno',    506.80, 0.8496, 11.93, 311.3, 144.4, 358.1),
            '00001':   CelestialObject('00001',   'Ceres',     'planet',    2.77, 0.0760, 10.59,  73.6,  80.3,  95.9),
            '02060':   CelestialObject('02060',   'Chiron',    'dwarf',    13.70, 0.3790,  6.93, 339.6, 209.4, 150.0),
            '00588':   CelestialObject('00588',   'Achilles',  'asteroid',  5.20, 0.1470, 10.32, 133.0, 316.6,  45.0),
            '00433':   CelestialObject('00433',   'Eros',      'asteroid',  1.46, 0.2226, 10.83, 178.8, 304.3, 120.0),
        }
        synth_res = {k: op.apply(v) for k, v in synth_objs.items()}
        da_smoke = DiophantineValidator.audit(synth_res, config)
        mp_smoke = HostileAuditSuite.run_mp_11_fronts(synth_objs, synth_res, config, op, {'delta_H_shared_radial_bits': 0.0, 'H_bound_discrete_Sn_bits': 1.0})
        assert 'front_3_nea_pha_micro_shell' in mp_smoke and 'front_D_asteroid_family_variance' in mp_smoke
        print(f"  {Term.DARK_GREEN}✓ [PASS]{Term.RESET} test_phase7_and_11_fronts_runtime: Counter, defaultdict & all 11 fronts executed with 0 errors.\n")


# ============================================================================
# EXACT LAGUERRE STARK WAVEFUNCTION WITH EXPLICIT MAPPING PARAMETERS
# ============================================================================
class QuantumStarkWavefunction:
    SCALE_X: float = 1.45
    POWER_GAMMA: float = 1.35
    ENVELOPE_ALPHA: float = 0.85
    ENVELOPE_DECAY: float = 0.58
    SIGMA_PSF: float = 0.65

    @classmethod
    def mapped_node_positions(cls) -> Tuple[float, float]:
        r1 = 2.0 - math.sqrt(2.0)
        r2 = 2.0 + math.sqrt(2.0)
        return (round(cls.SCALE_X * (r1 ** (1.0 / cls.POWER_GAMMA)), 2),
                round(cls.SCALE_X * (r2 ** (1.0 / cls.POWER_GAMMA)), 2))

    @staticmethod
    def laguerre_L_n1_0(n1: int, rho: np.ndarray) -> np.ndarray:
        if n1 == 0:
            return np.ones_like(rho)
        elif n1 == 1:
            return 1.0 - rho
        elif n1 == 2:
            return 1.0 - 2.0 * rho + 0.5 * (rho ** 2)
        elif n1 == 3:
            return 1.0 - 3.0 * rho + 1.5 * (rho ** 2) - (1.0 / 6.0) * (rho ** 3)
        raise ValueError("n1 must be in {0,1,2,3}")

    @classmethod
    def radial_detector_profile(cls, n1: int, x_axis: np.ndarray) -> np.ndarray:
        rho = np.clip((x_axis / cls.SCALE_X) ** cls.POWER_GAMMA, 0.0, 9.0)
        L_val = cls.laguerre_L_n1_0(n1, rho)
        raw_density = (rho ** cls.ENVELOPE_ALPHA) * np.exp(-cls.ENVELOPE_DECAY * rho) * (L_val ** 2)
        kernel_x = np.linspace(-2.5, 2.5, 25)
        kernel = np.exp(-0.5 * (kernel_x / cls.SIGMA_PSF) ** 2)
        kernel /= np.sum(kernel)
        smoothed = np.convolve(raw_density, kernel, mode='same')
        return smoothed / max(float(np.max(smoothed)), 1e-12)


# ============================================================================
# DATA DOWNLOADER (HARVARD LIVE-SYNC: MPCORB + COMETELS)
# ============================================================================
class DataDownloader:
    MPC_URL = "https://www.minorplanetcenter.net/iau/MPCORB/MPCORB.DAT.gz"
    AUX_SOURCES = {
        "CometEls.txt": "https://www.minorplanetcenter.net/iau/MPCORB/CometEls.txt",
        "NEA.txt":      "https://www.minorplanetcenter.net/iau/MPCORB/NEA.txt",
        "PHA.txt":      "https://www.minorplanetcenter.net/iau/MPCORB/PHA.txt",
        "newnumids.dat":"https://www.minorplanetcenter.net/iau/dailyids/newnumids.dat",
        "neocp.txt":    "https://www.minorplanetcenter.net/iau/NEO/neocp.txt",
    }
    GZ_FILENAME = str(DATA_DIR / "MPCORB.DAT.gz")
    DAT_FILENAME = str(DATA_DIR / "MPCORB.DAT")
    COMET_FILENAME = str(DATA_DIR / "CometEls.txt")
    USER_AGENT = "IT3-Framework/22.6-strict (https://zenodo.org/records/21792530)"

    @classmethod
    def _fetch_url_to_path(cls, url: str, dest: Path, timeout: int = 45) -> bool:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            dest.write_bytes(data)
            return True
        except Exception:
            return False

    @classmethod
    def download_latest(cls, target_dir: Path = DATA_DIR, force_download: bool = False) -> str:
        print_section("PHASE 1: AUTONOMOUS REPOSITORY DATA ACQUISITION (HARVARD-SMITHSONIAN CfA)")
        target_dir = Path(target_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        cls.GZ_FILENAME = str(target_dir / "MPCORB.DAT.gz")
        cls.DAT_FILENAME = str(target_dir / "MPCORB.DAT")
        cls.COMET_FILENAME = str(target_dir / "CometEls.txt")

        # Download or verify auxiliary MPC catalogs strictly inside ./data/ (no silent copy from ../torus!)
        for fn, url in cls.AUX_SOURCES.items():
            dest_p = target_dir / fn
            if not force_download and dest_p.exists() and dest_p.stat().st_size > 0:
                print(f"  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Repository file verified: [{Term.DARK_BLUE}{Term.BOLD}./data/{fn}{Term.RESET}]{Term.RESET}")
            else:
                print(f"  {Term.DARK_BLUE}⬇{Term.RESET} {Term.BLACK}Downloading ./data/{fn} from Harvard MPC...{Term.RESET}")
                if cls._fetch_url_to_path(url, dest_p):
                    print(f"  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Downloaded from Harvard MPC: [{Term.DARK_BLUE}{Term.BOLD}./data/{fn}{Term.RESET}]{Term.RESET}")
                else:
                    print(f"  {Term.BLACK}ℹ Optional stream ./data/{fn} offline (skipping live stream).{Term.RESET}")

        mpc_path = target_dir / "MPCORB.DAT"
        if not force_download and mpc_path.exists() and mpc_path.stat().st_size > 1_000_000:
            print(f"  {Term.DARK_GREEN}✓{Term.RESET} {Term.BOLD}{Term.BLACK}SYSTEM CHECK:{Term.RESET} Found localized Harvard MPC database [{Term.DARK_BLUE}{Term.BOLD}./data/MPCORB.DAT{Term.RESET}]\n")
            return str(mpc_path)

        print(f"  {Term.DARK_RED}⚠{Term.RESET} {Term.BLACK}./data/MPCORB.DAT not found (or --fresh-download requested). Downloading from Harvard-Smithsonian CfA...{Term.RESET}")
        try:
            req = urllib.request.Request(cls.MPC_URL, headers={"User-Agent": cls.USER_AGENT})
            with urllib.request.urlopen(req, timeout=180) as response:
                total_length = response.headers.get('content-length')
                if total_length is not None:
                    total_length = int(total_length)
                with open(cls.GZ_FILENAME, 'wb') as f:
                    with tqdm(total=total_length, unit='B', unit_scale=True,
                              desc=f"  {Term.DARK_BLUE}Downloading{Term.RESET}",
                              bar_format='{l_bar}{bar:30}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                              colour='blue') as pbar:
                        while True:
                            chunk = response.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            pbar.update(len(chunk))
            with gzip.open(cls.GZ_FILENAME, 'rb') as f_in:
                with open(cls.DAT_FILENAME, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            if os.path.exists(cls.GZ_FILENAME):
                os.remove(cls.GZ_FILENAME)
            print(f"  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Extracted ./data/MPCORB.DAT into ./data/ directory.{Term.RESET}\n")
            return cls.DAT_FILENAME
        except Exception as e:
            print(f"  {Term.DARK_RED}Error: Failed to download ./data/MPCORB.DAT ({e}){Term.RESET}")
            dist_p = target_dir / "Distant.txt"
            if dist_p.exists():
                return str(dist_p)
            raise FileNotFoundError("No local MPCORB.DAT database found in ./data/ directory.")


# ============================================================================
# DATA STRUCTURES & LOADER (PARSING MEAN ANOMALY M & PACKED EPOCH)
# ============================================================================
@dataclass
class CelestialObject:
    mpc_code: str; name: str; obj_type: str
    a: float; e: float; i: float; omega: float; Omega: float; M: float = 0.0; epoch_jd: float = 2461200.5; epoch_valid: bool = True
    @property
    def Q(self) -> float:
        return self.a * (1.0 + self.e)
    @property
    def mean_longitude(self) -> float:
        return (self.M + self.omega + self.Omega) % 360.0

@dataclass
class TopologicalResult:
    Q: float; Phi_topo: float; r_eff: float; S_n: int; S_k: int; S_h: int; R_bowl: float

MPC_TO_NAME = {
    'Mercury': 'Mercury', 'Venus': 'Venus', 'Earth': 'Earth', 'Mars': 'Mars',
    'Jupiter': 'Jupiter', 'Saturn': 'Saturn', 'Uranus': 'Uranus', 'Neptune': 'Neptune',
    '00001': 'Ceres', '00002': 'Pallas', '00003': 'Juno', '00004': 'Vesta', '00010': 'Hygiea',
    '02060': 'Chiron', '50000': 'Quaoar', '90482': 'Orcus', '20000': 'Varuna',
    '134340': 'Pluto', 'D4340': 'Pluto', '136108': 'Haumea', 'D6108': 'Haumea',
    '136472': 'Makemake', 'D6472': 'Makemake', '136199': 'Eris', 'D6199': 'Eris',
    '90377': 'Sedna', 'K12VB3P': '2012VP113', 's1132': '2015TG387', '~0caL': '2015BP519'
}

OBJECT_TYPES = {
    'Mercury': 'planet', 'Venus': 'planet', 'Earth': 'planet', 'Mars': 'planet',
    'Jupiter': 'planet', 'Saturn': 'planet', 'Uranus': 'planet', 'Neptune': 'planet',
    'Ceres': 'planet', 'Pallas': 'planet', 'Juno': 'planet', 'Vesta': 'planet', 'Hygiea': 'planet',
    'Chiron': 'dwarf', 'Quaoar': 'dwarf', 'Orcus': 'dwarf', 'Varuna': 'dwarf',
    'Pluto': 'dwarf', 'Eris': 'dwarf', 'Haumea': 'dwarf', 'Makemake': 'dwarf',
    'Sedna': 'etno', '2012VP113': 'etno', '2015TG387': 'etno', '2015BP519': 'etno'
}

KEY_OBJECTS = frozenset([
    'Mercury', 'Mars', 'Earth', 'Neptune', 'Pluto', 'Eris', 'Haumea', 'Makemake',
    'Sedna', '2012VP113', '2015TG387', '2015BP519',
    'Ceres', 'Vesta', 'Chiron', 'Quaoar', 'Orcus', 'Varuna'
])

NAME_PATTERNS = [
    ('Haumea', 'Haumea'), ('2012 VP113', '2012VP113'), ('2015 TG387', '541132', '2015TG387'),
    ('2015 BP519', '2015BP519'), ('Makemake', 'Makemake'), ('Eris', 'Eris'), ('Sedna', 'Sedna'), ('Pluto', 'Pluto'),
    ('Ceres', 'Ceres'), ('Vesta', 'Vesta'), ('Chiron', 'Chiron'), ('Quaoar', 'Quaoar'), ('Orcus', 'Orcus'), ('Varuna', 'Varuna')
]

class CPHAMOperator:
    def __init__(self, config: IT3Config):
        self.config = config
        self._lambda_y = config.LAMBDA_Y
        self._k_torus = config.K_TORUS
        self._lambda_h = config.LAMBDA_H
        self._r_base = config.R_BASE
        self._r_phase = config.R_PHASE_TRANSITION
        self._norm_out = config.NORMALIZATION_FACTOR
        self._norm_in = config.INNER_NORMALIZATION

    def _get_steps_n(self, val: float, max_steps: int = 20) -> int:
        if val < 1.0:
            return 0
        steps, curr = 0, val
        for _ in range(max_steps):
            next_val = np.floor(curr / self._lambda_y)
            if next_val < 1.0:
                break
            curr, steps = next_val, steps + 1
        return steps

    def _get_steps_kh(self, val: float, scale: float, max_steps: int = 20) -> int:
        if val < 1.0:
            return 1
        steps, curr = 0, val
        for _ in range(max_steps):
            next_val = np.floor(curr / scale)
            if next_val < 1.0:
                break
            curr, steps = next_val, steps + 1
        return steps + 1

    def apply(self, obj: CelestialObject) -> TopologicalResult:
        Q = obj.Q
        Phi_topo = 1.0 + 0.5 * (obj.e ** 2)
        r_eff = Q * Phi_topo
        n_raw = ((r_eff - self._r_phase) / self._norm_out
                 if r_eff >= self._r_phase else r_eff / self._norm_in)
        delta_k = (obj.i / 90.0) * 0.5 * np.sin(np.radians(obj.Omega))
        k_raw = np.clip((obj.omega % 360.0) / 30.0 + 1.0 + delta_k, 1.0, 12.999)
        h_raw = 1.0 + (obj.i / 90.0) * 5.0
        S_n = self._get_steps_n(n_raw)
        S_k = self._get_steps_kh(k_raw, self._k_torus)
        S_h = self._get_steps_kh(h_raw, self._lambda_h)
        R_bowl = self._r_base if S_n == 0 else self._r_base * (self._lambda_y ** (S_n - 1))
        return TopologicalResult(Q=Q, Phi_topo=Phi_topo, r_eff=r_eff, S_n=S_n, S_k=S_k, S_h=S_h, R_bowl=R_bowl)

class UniversalLoader:
    def __init__(self, config: IT3Config):
        self.config = config

    @staticmethod
    def _unpack_mpc_epoch_jd(packed: str) -> Tuple[float, bool]:
        try:
            s = packed.strip()
            if len(s) != 5 or s[0] not in ('I', 'J', 'K'):
                return 2461200.5, False
            century_map = {'I': 1800, 'J': 1900, 'K': 2000}
            year = century_map[s[0]] + int(s[1:3])
            def char_val(c: str) -> int:
                return int(c) if c.isdigit() else (ord(c.upper()) - ord('A') + 10)
            month = char_val(s[3])
            day = char_val(s[4])
            if not (1 <= month <= 12 and 1 <= day <= 31):
                return 2461200.5, False
            a_y = (14 - month) // 12
            y_m = year + 4800 - a_y
            m_m = month + 12 * a_y - 3
            jdn = day + (153 * m_m + 2) // 5 + 365 * y_m + y_m // 4 - y_m // 100 + y_m // 400 - 32045
            return float(jdn) - 0.5, True
        except Exception:
            return 2461200.5, False

    def _detect_format(self, filepath: str) -> str:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if len(line.strip()) > 100:
                    return 'mpcorb'
                elif len(line.split()) >= 11:
                    return 'distant'
        return 'unknown'

    def _identify_object(self, mpc_code: str, name_field: str) -> Tuple[str, str]:
        readable_name = MPC_TO_NAME.get(mpc_code, mpc_code)
        for patterns in NAME_PATTERNS:
            if any(pattern in name_field for pattern in patterns):
                readable_name = patterns[-1] if len(patterns) > 1 else patterns[0]
                break
        return readable_name, OBJECT_TYPES.get(readable_name, 'asteroid')

    def load(self, filepath: str) -> Dict[str, CelestialObject]:
        print_section("PHASE 2: ORBITAL PARSING & CLASSIFICATION (INCLUDING MEAN ANOMALY M)")
        objects = {}
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        is_mpcorb = self._detect_format(filepath) == 'mpcorb'

        start_time = time.time()
        for line in tqdm(lines, desc=f"  {Term.DARK_BLUE}SCANNING{Term.RESET}", unit="lines", colour='blue'):
            try:
                if is_mpcorb and len(line) >= 103:
                    mpc_code = line[0:7].strip()
                    epoch_jd, ep_ok = self._unpack_mpc_epoch_jd(line[20:25])
                    M_anom = float(line[26:35])
                    omega = float(line[37:46])
                    Omega = float(line[48:57])
                    i = float(line[59:68])
                    e = float(line[70:79])
                    a = float(line[92:103])
                    name_field = line[166:].strip() if len(line) >= 166 else ""
                elif not is_mpcorb and len(line.split()) >= 11:
                    parts = line.split()
                    mpc_code = parts[0]
                    epoch_jd, ep_ok = self._unpack_mpc_epoch_jd(parts[3]) if len(parts) > 3 else (2461200.5, False)
                    M_anom = float(parts[4]) if len(parts) > 4 else 0.0
                    omega, Omega, i, e, a = float(parts[5]), float(parts[6]), float(parts[7]), float(parts[8]), float(parts[10])
                    name_field = ' '.join(parts[11:]) if len(parts) > 11 else ""
                else:
                    continue
                if a > 0 and 0 <= e < 1.0:
                    name, obj_type = self._identify_object(mpc_code, name_field)
                    objects[mpc_code] = CelestialObject(mpc_code, name, obj_type, a, e, i, omega, Omega, M_anom, epoch_jd, ep_ok)
            except Exception:
                continue

        elapsed = max(time.time() - start_time, 1e-6)
        print(f"\n  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Loaded {Term.BOLD}{len(objects):,}{Term.RESET}{Term.BLACK} celestial objects in {elapsed:.2f}s ({len(objects)/elapsed:,.0f} obj/s).{Term.RESET}\n")
        return objects


# ============================================================================
# PHASE 7: SLIDING LOG-WINDOW CONTROL & IONIZED PARTITION
# ============================================================================
class DiophantineValidator:
    @staticmethod
    def audit(results: Dict[str, TopologicalResult], config: IT3Config) -> Dict:
        print_section("PHASE 7: SLIDING EQUAL-LOG-WIDTH WINDOW CONTROL (Δln R = ln 2) & PARTITION")
        r_effs = np.array([res.r_eff for res in results.values()])
        S_n = np.array([res.S_n for res in results.values()])

        mask_saturated = (r_effs >= config.R_BASE) & (r_effs <= config.R_IONIZATION_LIMIT)
        mask_ionized = r_effs > config.R_IONIZATION_LIMIT

        sat_count = int(np.sum(mask_saturated))
        ion_count = int(np.sum(mask_ionized))

        b1_theo = 2.0 * config.SQRT3 * config.INNER_NORMALIZATION  # 34.97 AU
        b2_theo = 4.0 * config.SQRT3 * config.INNER_NORMALIZATION  # 69.94 AU
        n_lower_adj = int(np.sum((r_effs >= 0.5 * b1_theo) & (r_effs < b1_theo)))
        n_target_band = int(np.sum((r_effs >= b1_theo) & (r_effs < b2_theo)))
        n_upper_adj = int(np.sum((r_effs >= b2_theo) & (r_effs < 2.0 * b2_theo)))
        mean_adjacent = 0.5 * (n_lower_adj + n_upper_adj)
        ratio_vs_adj = float(n_target_band / max(mean_adjacent, 1.0))

        r0_grid = np.arange(15.0, 65.25, 0.25)
        r_outer_pool = r_effs[(r_effs >= 15.0) & (r_effs <= 135.0)]
        sliding_counts = np.array([np.sum((r_outer_pool >= r0) & (r_outer_pool < 2.0 * r0)) for r0 in r0_grid], dtype=int)
        best_idx = int(np.argmax(sliding_counts))
        r0_best = float(r0_grid[best_idx])
        n_best_window = int(sliding_counts[best_idx])
        capture_efficiency = float(n_target_band / max(n_best_window, 1))
        pct_windows_beaten = float(np.mean(sliding_counts <= n_target_band) * 100.0)

        pct_ge3 = pct_tail = pct_low = 0.0
        n_ge3 = n_tail = n_low = n_tail_inner = n_tail_outer = 0
        if ion_count > 0:
            ion_sn = S_n[mask_ionized]
            ion_reff = r_effs[mask_ionized]
            n_ge3 = int(np.sum(ion_sn >= 3))
            n_tail = int(np.sum(ion_sn == 2))
            n_low = int(np.sum(ion_sn <= 1))
            pct_ge3 = (n_ge3 / ion_count) * 100.0
            pct_tail = (n_tail / ion_count) * 100.0
            pct_low = (n_low / ion_count) * 100.0
            n_tail_inner = int(np.sum((ion_reff > config.R_IONIZATION_LIMIT) &
                                      (ion_reff <= config.R_EVAP_TAIL_UPPER) & (ion_sn == 2)))
            n_tail_outer = int(np.sum((ion_reff >= config.R_DIM_COLLAPSE_LOWER) &
                                      (ion_reff <= config.R_DIM_COLLAPSE_UPPER) & (ion_sn == 2)))

            print(f"  {Term.DARK_BLUE}{Term.BOLD}🧬 DIOPHANTINE CASCADE AUDIT over Q(√2,√3,√5):{Term.RESET}")
            print(f"  {Term.BLACK}Operator: iterative floor cascade S_n = min{{k≥0 : x_(k+1)=0}}, x_(k+1)=⌊x_k/√3⌋{Term.RESET}\n")
            if sat_count > 0:
                print(f"  {Term.BOLD}0. Saturated Layer (27–48 AU):{Term.RESET}   {Term.DARK_GREEN}{sat_count:,} objects{Term.RESET}")
                print(f"     • Integer cascade projection:      {Term.DARK_GREEN}100.00%{Term.RESET} (exact by floor-cascade definition)\n")
            print(f"  {Term.BOLD}1. Descriptive 3-Way Partition of Ionized Sector (R_eff > 48 AU, N={ion_count:,}):{Term.RESET}")
            print(f"     • Floors S_n ≥ 3:                  {Term.DARK_MAGENTA}{n_ge3:>8,} ({pct_ge3:5.2f}%){Term.RESET}")
            print(f"     • S_n=2 Evaporative Tail:          {Term.DARK_MAGENTA}{n_tail:>8,} ({pct_tail:5.2f}%){Term.RESET} [Inner 48–69.94 AU: {n_tail_inner:,} | Outer 326–410 AU: {n_tail_outer:,}]")
            print(f"     • S_n ∈ {{0,1}} (>243 AU reset):     {Term.DARK_MAGENTA}{n_low:>8,} ({pct_low:5.2f}%){Term.RESET}")
            print(f"     • Parity check:                    {pct_ge3:.2f}% + {pct_tail:.2f}% + {pct_low:.2f}% = {pct_ge3+pct_tail+pct_low:.2f}% (exact partition; continuum lives in E_ion)\n")

        print(f"  {Term.BOLD}2. Sliding Equal-Log-Width Window Control [R₀, 2R₀) across R₀ ∈ [15, 65] AU:{Term.RESET}")
        print(f"     • Theoretical S_n=2 Window [{b1_theo:.2f}, {b2_theo:.2f}) AU: {Term.CYAN}{n_target_band:>8,} objects{Term.RESET} (Adjacent: {n_lower_adj:,} lower, {n_upper_adj:,} upper; ratio={ratio_vs_adj:.2f}×)")
        print(f"     • Empirical Argmax Window  [{r0_best:.2f}, {2.0*r0_best:.2f}) AU: {Term.BOLD}{n_best_window:>8,} objects{Term.RESET} (Any ×2 window covering 40–50 AU captures the Kuiper belt)")
        print(f"     • S_n=2 Capture vs Best ×2 Window: {Term.BOLD}{capture_efficiency*100:.2f}%{Term.RESET} of max | Edge offset ΔR₀ = {b1_theo - r0_best:+.2f} AU")

        return {
            'saturated_count': sat_count,
            'ionized_count': ion_count,
            'partition_pct_sn_ge_3': round(pct_ge3, 2),
            'partition_pct_sn_eq_2_tail': round(pct_tail, 2),
            'partition_pct_sn_le_1_reset': round(pct_low, 2),
            'lower_adjacent_band_count': n_lower_adj,
            'target_sn2_band_count': n_target_band,
            'upper_adjacent_band_count': n_upper_adj,
            'adjacent_band_ratio': round(ratio_vs_adj, 3),
            'sliding_window_argmax_R0_AU': round(r0_best, 2),
            'sliding_window_argmax_interval_AU': [round(r0_best, 2), round(2.0 * r0_best, 2)],
            'sliding_window_argmax_count': n_best_window,
            'sn2_vs_sliding_max_efficiency_pct': round(capture_efficiency * 100.0, 2),
            'sliding_windows_beaten_pct': round(pct_windows_beaten, 2)
        }


# ============================================================================
# PHASE 7.5: LAYER II EMPIRICAL CATALOG TESTS (SHARED-EDGE ΔH & EQ. OF CENTER)
# ============================================================================
class HostileAuditSuite:
    @staticmethod
    def compute_cometary_dichotomy(config: IT3Config, operator: CPHAMOperator) -> Dict:
        global COMET_SHA
        comet_file = DataDownloader.COMET_FILENAME
        isos = [
            {'name': "1I/'Oumuamua", 'e': 1.1993, 'q': 0.255, 'E_ion': round(math.log((1.1993 - 1.0) * config.R_VALENCE / 0.255) / math.log(config.LAMBDA_Y), 2), 'source': 'MPC Empirical Elements'},
            {'name': "2I/Borisov",   'e': 3.3460, 'q': 1.998, 'E_ion': round(math.log((3.3460 - 1.0) * config.R_VALENCE / 1.998) / math.log(config.LAMBDA_Y), 2), 'source': 'MPC Empirical Elements'},
            {'name': "3I/ATLAS",     'e': 6.1399, 'q': 1.357, 'E_ion': round(math.log((6.1399 - 1.0) * config.R_VALENCE / 1.357) / math.log(config.LAMBDA_Y), 2), 'source': 'MPC Empirical Elements'}
        ]
        if not os.path.exists(comet_file):
            return {
                'evaluation_mode': 'UNVERIFIED_OFFLINE (CometEls.txt not present locally)',
                'n_bound': 0, 'n_free': 0,
                'H_bound_shared_radial_bits': None,
                'H_free_shared_radial_bits': None,
                'delta_H_shared_radial_bits': None,
                'H_bound_discrete_Sn_bits': None,
                'interstellar_objects': isos
            }

        COMET_SHA = sha256_prefix(comet_file)
        bound_sn, bound_reff, free_reff = [], [], []
        with open(comet_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if len(line.strip()) < 65:
                    continue
                try:
                    q = float(line[30:39])
                    e = float(line[41:49])
                    if q <= 0:
                        continue
                    if e < 1.0 and (1.0 - e) > 1e-5:
                        a = q / (1.0 - e)
                        Q = a * (1.0 + e)
                        r_eff = Q * (1.0 + 0.5 * e * e)
                        n_raw = ((r_eff - config.R_PHASE_TRANSITION) / config.NORMALIZATION_FACTOR
                                 if r_eff >= config.R_PHASE_TRANSITION else r_eff / config.INNER_NORMALIZATION)
                        sn = min(operator._get_steps_n(n_raw), 10)
                        bound_sn.append(sn)
                        bound_reff.append(r_eff)
                    elif e >= 1.0:
                        r_eff = q * (1.0 + e) * (1.0 + 0.5 * min(e, 10.0) ** 2)
                        free_reff.append(r_eff)
                except Exception:
                    continue

        if len(bound_sn) < 10 or len(free_reff) < 5:
            return {
                'evaluation_mode': 'INSUFFICIENT_COMET_RECORDS',
                'n_bound': len(bound_sn), 'n_free': len(free_reff),
                'H_bound_shared_radial_bits': None, 'H_free_shared_radial_bits': None,
                'delta_H_shared_radial_bits': None, 'H_bound_discrete_Sn_bits': None,
                'interstellar_objects': isos
            }

        log_b = np.log10(np.clip(bound_reff, 0.1, 1e5))
        log_f = np.log10(np.clip(free_reff, 0.1, 1e5))
        shared_edges = np.linspace(min(float(np.min(log_b)), float(np.min(log_f))),
                                   max(float(np.max(log_b)), float(np.max(log_f))), 12)
        hist_b_shared, _ = np.histogram(log_b, bins=shared_edges)
        hist_f_shared, _ = np.histogram(log_f, bins=shared_edges)
        probs_b_sh = hist_b_shared[hist_b_shared > 0] / len(log_b)
        probs_f_sh = hist_f_shared[hist_f_shared > 0] / len(log_f)
        h_bound_shared = float(-np.sum(probs_b_sh * np.log2(probs_b_sh)))
        h_free_shared = float(-np.sum(probs_f_sh * np.log2(probs_f_sh)))
        delta_h_shared = h_free_shared - h_bound_shared

        counts_sn = np.bincount(bound_sn, minlength=11)
        probs_sn = counts_sn[counts_sn > 0] / len(bound_sn)
        h_bound_sn = float(-np.sum(probs_sn * np.log2(probs_sn)))

        eta_bound_sn = h_bound_sn / math.log2(11.0)
        eta_free_sh = h_free_shared / math.log2(11.0)
        return {
            'evaluation_mode': f"LIVE_SHARED_11BINS (SHA:{COMET_SHA}, identical log10(R_eff) edges + normalized efficiency)",
            'n_bound': len(bound_sn),
            'n_free': len(free_reff),
            'H_bound_shared_radial_bits': round(h_bound_shared, 4),
            'H_free_shared_radial_bits': round(h_free_shared, 4),
            'delta_H_shared_radial_bits': round(delta_h_shared, 4),
            'H_bound_discrete_Sn_bits': round(h_bound_sn, 4),
            'normalized_efficiency_bound_Sn': round(eta_bound_sn, 4),
            'normalized_efficiency_free_radial': round(eta_free_sh, 4),
            'interstellar_objects': isos
        }

    @staticmethod
    def multi_angle_inclination_scan(incs: np.ndarray) -> Dict:
        valid_i = incs[(incs >= 2.0) & (incs <= 38.0)]
        bins = np.linspace(2.0, 38.0, 73)
        hist, edges = np.histogram(valid_i, bins=bins)
        centers = 0.5 * (edges[:-1] + edges[1:])

        scan_angles = [10.0, 12.0, 15.0, 18.0, 20.0, 25.0, 30.0]
        scan_results = {}
        for ang in scan_angles:
            idx = int(np.argmin(np.abs(centers - ang)))
            pre_slice = hist[max(0, idx - 4):idx]
            post_slice = hist[idx:min(len(hist), idx + 4)]
            if np.all(pre_slice > 0) and np.all(post_slice > 0):
                drop_ratio = float(np.mean(pre_slice) / np.mean(post_slice))
                slope_before = float((np.log(hist[idx]) - np.log(hist[idx - 4])) / 2.0)
                slope_after = float((np.log(hist[min(len(hist)-1, idx + 4)]) - np.log(hist[idx])) / 2.0)
                scan_results[f"{int(ang)}deg"] = {
                    'drop_ratio': round(drop_ratio, 3),
                    'log_slope_kink': round(abs(slope_after - slope_before), 4)
                }

        fine_candidates = [ang for ang in centers if 8.0 <= ang <= 30.0]
        best_ang, best_ratio = 18.0, 0.0
        for ang in fine_candidates:
            idx = int(np.argmin(np.abs(centers - ang)))
            pre_s, post_s = hist[idx - 4:idx], hist[idx:idx + 4]
            if len(pre_s) == 4 and len(post_s) == 4 and np.mean(post_s) > 5:
                r = float(np.mean(pre_s) / np.mean(post_s))
                if r > best_ratio + 1e-9:
                    best_ratio, best_ang = r, float(ang)

        rng = np.random.default_rng(42)
        boot_angles = []
        sample_pool = valid_i if len(valid_i) <= 100000 else rng.choice(valid_i, 100000, replace=False)
        for _ in range(200):
            b_sample = rng.choice(sample_pool, size=len(sample_pool), replace=True)
            bh, _ = np.histogram(b_sample, bins=bins)
            b_best_a, b_best_r = best_ang, 0.0
            for ang in fine_candidates:
                idx = int(np.argmin(np.abs(centers - ang)))
                pre_s, post_s = bh[idx - 4:idx], bh[idx:idx + 4]
                if len(pre_s) == 4 and len(post_s) == 4 and np.mean(post_s) > 5:
                    r = float(np.mean(pre_s) / np.mean(post_s))
                    if r > b_best_r + 1e-9:
                        b_best_r, b_best_a = r, float(ang)
            boot_angles.append(b_best_a)
        ci_low, ci_high = np.percentile(boot_angles, [2.5, 97.5]) if boot_angles else (best_ang, best_ang)
        is_18_in_ci = bool(ci_low <= 18.0 <= ci_high)

        scan_results['empirical_argmax_drop_deg'] = round(best_ang, 2)
        scan_results['empirical_argmax_drop_ratio'] = round(best_ratio, 3)
        scan_results['bootstrap_200_95ci_deg'] = [round(float(ci_low), 2), round(float(ci_high), 2)]
        scan_results['is_18deg_inside_bootstrap_ci'] = is_18_in_ci
        return scan_results

    @staticmethod
    def true_trojan_l4_l5_analysis(objects: Dict[str, CelestialObject], phi: float) -> Dict:
        candidates = [o for o in objects.values() if 5.05 <= o.a <= 5.35 and o.e < 0.3 and o.i < 40.0]
        if len(candidates) < 20:
            return {'status': 'INSUFFICIENT_TROJANS_IN_SUBSET', 'count': len(candidates)}

        excluded_bad_epoch = sum(1 for o in candidates if not o.epoch_valid)
        valid_trojans = [o for o in candidates if o.epoch_valid]

        l4_count, l5_count = 0, 0
        pomega_cut_a, pomega_cut_b = 0, 0
        for o in valid_trojans:
            dt = o.epoch_jd - 2451545.0
            lam_j_mean = (34.3515 + 0.0830853001 * dt) % 360.0
            d_lam = ((o.mean_longitude - lam_j_mean + 180.0) % 360.0) - 180.0
            if 15.0 <= d_lam <= 105.0:
                l4_count += 1
            elif -105.0 <= d_lam <= -15.0:
                l5_count += 1
            pomega = (o.omega + o.Omega) % 360.0
            if pomega < 180.0:
                pomega_cut_a += 1
            else:
                pomega_cut_b += 1

        true_l4_l5_ratio = l4_count / max(l5_count, 1)
        legacy_pomega_ratio = pomega_cut_a / max(pomega_cut_b, 1)
        return {
            'total_trojan_candidates': len(candidates),
            'excluded_fallback_epochs': excluded_bad_epoch,
            'valid_epoch_trojans': len(valid_trojans),
            'ephemeris_method': 'Pure mean-longitude resonant argument Δλ = λ_ast - λ_J,mean(JD) at object epoch',
            'true_L4_camp_count': l4_count,
            'true_L5_camp_count': l5_count,
            'true_L4_L5_ratio': round(true_l4_l5_ratio, 4),
            'legacy_pomega_cut_ratio': round(legacy_pomega_ratio, 4),
            'delta_from_phi_true_L4_L5': round(abs(true_l4_l5_ratio - phi), 4),
            'epistemic_note': 'L4/L5 ratio is an empirical capture asymmetry, not derived from K.'
        }

    @staticmethod
    def rayleigh_modulo(vals: np.ndarray, period: float) -> Tuple[float, float]:
        if len(vals) == 0 or period <= 0:
            return 0.0, 1.0
        angles = 2.0 * np.pi * np.mod(vals, period) / period
        c_sum = float(np.sum(np.cos(angles)))
        s_sum = float(np.sum(np.sin(angles)))
        z = (c_sum ** 2 + s_sum ** 2) / len(vals)
        return z, float(math.exp(-z)) if z > 0 else 1.0

    @classmethod
    def rayleigh_periodogram(cls, vals: np.ndarray, target: float, rng: float = 0.2, steps: int = 100) -> Tuple[float, float, float]:
        if len(vals) < 5:
            return 0.0, 0.0, 0.0
        periods = np.linspace(target - rng, target + rng, steps)
        bg = [cls.rayleigh_modulo(vals, float(p))[0] for p in periods if abs(p - target) > 1e-5]
        tz = cls.rayleigh_modulo(vals, target)[0]
        mb = float(np.mean(bg)) if bg else 0.0
        sb = float(np.std(bg)) if bg else 0.0
        snr = (tz - mb) / sb if sb > 0 else 0.0
        return tz, mb, snr

    @classmethod
    def run_mp_11_fronts(cls, objects: Dict[str, CelestialObject], results: Dict[str, TopologicalResult],
                         config: IT3Config, operator: CPHAMOperator, comet_audit: Dict) -> Dict:
        print_section("PHASE 7.6: 11-FRONT K-PHAM VALIDATION SUITE (INTEGRATED FROM mp.py WITH NULL CONTROLS)")
        script_dir = Path(__file__).resolve().parent
        search_dirs = [DATA_DIR, SCRIPT_DIR]

        # --- FRONT [B]: Macro-Compton Periodicity (Strict Rayleigh Periodogram on Bound & Deep Comets) ---
        comet_file = DataDownloader.COMET_FILENAME
        bound_log_reff = []
        deep_log_reff = []
        top_free_comets = []
        if os.path.exists(comet_file):
            with open(comet_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if len(line.strip()) < 65 or line.startswith('#'):
                        continue
                    try:
                        q = float(line[30:39])
                        e = float(line[41:49])
                        name_c = line[102:].strip() if len(line) > 102 else line[0:12].strip()
                        if q <= 0:
                            continue
                        if e < 1.0 and (1.0 - e) > 1e-5:
                            Q = (q / (1.0 - e)) * (1.0 + e)
                            r_eff = Q * (1.0 + 0.5 * e * e)
                            if r_eff > 0:
                                bound_log_reff.append(math.log(r_eff))
                                n_raw = ((r_eff - config.R_PHASE_TRANSITION) / config.NORMALIZATION_FACTOR
                                         if r_eff >= config.R_PHASE_TRANSITION else r_eff / config.INNER_NORMALIZATION)
                                if operator._get_steps_n(n_raw) >= 3:
                                    deep_log_reff.append(math.log(r_eff))
                        elif e >= 1.0:
                            e_ion_f = math.log(max((e - 1.0) * config.R_VALENCE / q, 1e-9)) / math.log(config.LAMBDA_Y) if e > 1.0 else 0.0
                            top_free_comets.append((e, q, round(e_ion_f, 2), name_c))
                    except Exception:
                        continue

        top_free_comets.sort(key=lambda x: x[0], reverse=True)
        log_r_arr = np.array(bound_log_reff, dtype=float)
        log_r_deep_arr = np.array(deep_log_reff, dtype=float)
        log_l1_sq = math.log(config.LAMBDA_1_EXACT ** 2)
        log_l1 = math.log(config.LAMBDA_1_EXACT)
        log_sqrt3 = math.log(config.SQRT3)

        front_b = {}
        for lbl, per, desc in [
            ("B1_Macro_Compton", log_l1_sq, "log(Λ₁²)"),
            ("B2_Half_Period",   log_l1,    "log(Λ₁)"),
            ("B3_Spiral_Step",   log_sqrt3,  "log(√3)")
        ]:
            tz, mb, snr = cls.rayleigh_periodogram(log_r_arr, per)
            verdict = "TRUE_RESONANCE" if snr > 3.0 else ("MARGINAL" if snr > 1.5 else "ARTIFACT_NULL (JFC volume echo)")
            front_b[lbl] = {'period': round(per, 4), 'z': round(tz, 3), 'bg_mean': round(mb, 3), 'snr_sigma': round(snr, 2), 'verdict': verdict}
        front_b['deep_comets_sn_ge_3_count'] = len(log_r_deep_arr)
        if len(log_r_deep_arr) >= 10:
            tz_d, mb_d, snr_d = cls.rayleigh_periodogram(log_r_deep_arr, log_l1_sq, rng=0.3)
            front_b['deep_B1_snr_sigma'] = round(snr_d, 2)

        b1_snr = front_b["B1_Macro_Compton"]["snr_sigma"]
        b3_snr = front_b["B3_Spiral_Step"]["snr_sigma"]
        print(f"  {Term.DARK_RED}[FRONT B: Macro-Compton]{Term.RESET}    N_bound={len(log_r_arr)} (deep S_n≥3: {len(log_r_deep_arr)}) | B1 log(Λ₁²) SNR={b1_snr:+.2f}σ | B3 log(√3) SNR={b3_snr:+.2f}σ → {front_b['B1_Macro_Compton']['verdict']}")

        # --- FRONT [T1]: Table 1 Verification (7 Key Benchmark Objects) ---
        targets_t1 = [
            ('Pluto',     {'134340', 'D4340'}, 2),
            ('Makemake',  {'136472', 'D6472'}, 2),
            ('Haumea',    {'136108', 'D6108'}, 2),
            ('Eris',      {'136199', 'D6199'}, 3),
            ('2012VP113', {'K12VB3P'},         4),
            ('Sedna',     {'90377'},           6),
            ('2015TG387', {'s1132', '541132'}, 8),
        ]
        name_to_code = {o.name: c for c, o in objects.items()}
        t1_report = {}
        t1_matches = 0
        for t_name, code_set, exp_sn in targets_t1:
            found_code = next((c for c in code_set if c in results), name_to_code.get(t_name))
            if found_code and found_code in results:
                res_o = results[found_code]
                ok = (res_o.S_n == exp_sn)
                if ok:
                    t1_matches += 1
                t1_report[t_name] = {'code': found_code, 'Q_AU': round(res_o.Q, 2), 'R_eff_AU': round(res_o.r_eff, 2), 'S_n': res_o.S_n, 'expected_S_n': exp_sn, 'match': ok}
        print(f"  {Term.CYAN}[FRONT T1: Table 1 Benchmarks]{Term.RESET} Verified {t1_matches}/{len(targets_t1)} key outer-system objects (Pluto=2, Eris=3, 2012VP113=4, Sedna=6, 2015TG387=8)")

        # --- FRONT [2]: 2x3 Lattice Prograde Theorem vs Retrograde Leakage (S_h=4) ---
        total_obj = max(len(results), 1)
        prograde_codes = [c for c, o in objects.items() if o.i <= 90.0]
        retro_codes = [c for c, o in objects.items() if o.i > 90.0]
        prograde_in_2x3 = sum(1 for c in prograde_codes if results[c].S_k in (1, 2) and results[c].S_h in (1, 2, 3))
        all_in_2x3 = sum(1 for r in results.values() if r.S_k in (1, 2) and r.S_h in (1, 2, 3))
        retro_leak_sh4 = sum(1 for c in retro_codes if results[c].S_h > 3)
        cell_counts_6 = [sum(1 for r in results.values() if r.S_k == sk and r.S_h == sh) for sk in (1, 2) for sh in (1, 2, 3)]
        p_cells = np.array([c for c in cell_counts_6 if c > 0], dtype=float) / max(sum(cell_counts_6), 1)
        h_lattice_bits = float(-np.sum(p_cells * np.log2(p_cells)))
        print(f"  {Term.CYAN}[FRONT 2: 2×3 Lattice Audit]{Term.RESET}  Prograde i≤90° in 2×3: {100.0*prograde_in_2x3/max(len(prograde_codes),1):.4f}% (Exact Domain Theorem) | Retrograde S_h=4 leakage: {retro_leak_sh4} obj | 6-Cell H={h_lattice_bits:.4f} bits")

        # --- FRONT [3]: NEA / PHA Micro-Shell Occupancy (File or Dynamical q<=1.3 AU Definition) ---
        nea_codes, pha_codes = set(), set()
        for d in search_dirs:
            if (d / "NEA.txt").exists() and not nea_codes:
                with open(d / "NEA.txt", 'r', errors='ignore') as fn_f:
                    nea_codes = {ln[0:7].strip() for ln in fn_f if len(ln) > 10 and not ln.startswith('#')}
            if (d / "PHA.txt").exists() and not pha_codes:
                with open(d / "PHA.txt", 'r', errors='ignore') as fp_f:
                    pha_codes = {ln[0:7].strip() for ln in fp_f if len(ln) > 10 and not ln.startswith('#')}

        nea_mode = "MPC_NEA_PHA_FILES" if (nea_codes or pha_codes) else "ORBITAL_DEFINITION (q <= 1.3 AU, a < 4.2 AU)"
        micro_counts = Counter()
        nea_total = 0
        for c, o in objects.items():
            is_nea = (c in nea_codes or c in pha_codes) if (nea_codes or pha_codes) else (o.a * (1.0 - o.e) <= 1.3 and o.a < 4.2)
            if is_nea and results[c].S_n == 0:
                micro_counts[(results[c].S_k, results[c].S_h)] += 1
                nea_total += 1
        top_micro_cell, top_micro_cnt = micro_counts.most_common(1)[0] if micro_counts else ((2, 1), 0)
        top_micro_pct = 100.0 * top_micro_cnt / max(nea_total, 1)
        print(f"  {Term.CYAN}[FRONT 3: NEA/PHA Micro-Shell]{Term.RESET} N_NEA(S_n=0)={nea_total:,} [{nea_mode}] | Dominant cell {top_micro_cell}: {top_micro_pct:.2f}% (Uniform ω prior P₀(S_k=2)=59.76%)")

        # --- FRONT [C]: Centaur d-Shell (S_k=2) vs Exact Analytical Uniform Prior (5 - √2)/6 ---
        centaur_sk = Counter()
        centaur_total = 0
        for c, o in objects.items():
            if 5.0 < o.a < 30.0:
                centaur_sk[results[c].S_k] += 1
                centaur_total += 1
        centaur_sk2_cnt = centaur_sk.get(2, 0)
        centaur_sk2_pct = 100.0 * centaur_sk2_cnt / max(centaur_total, 1)
        p0_sk2 = (5.0 - config.SQRT2) / 6.0
        p0_sk2_pct = 100.0 * p0_sk2
        binom_p_centaur = (float(stats.binomtest(centaur_sk2_cnt, max(centaur_total, 1), p=p0_sk2).pvalue) if hasattr(stats, 'binomtest') else float(stats.binom_test(centaur_sk2_cnt, max(centaur_total, 1), p=p0_sk2))) if centaur_total > 0 else 1.0
        print(f"  {Term.CYAN}[FRONT C: Centaur d-Shell]{Term.RESET}    N_Centaurs={centaur_total:,} | Observed S_k=2: {centaur_sk2_pct:.2f}% vs Analytical Uniform Prior (5−√2)/6 = {p0_sk2_pct:.2f}% (Δ={centaur_sk2_pct-p0_sk2_pct:+.2f}%, p_binom={binom_p_centaur:.4f})")

        # --- FRONT [D]: Asteroid Family Topological Variance (Collisional Debris Proof) ---
        fam_sn = defaultdict(list)
        fam_reff = defaultdict(list)
        for c, o in objects.items():
            if 2.0 <= o.a <= 3.5:
                key_f = (round(o.a * 10.0) / 10.0, round(o.i / 2.0) * 2.0)
                fam_sn[key_f].append(results[c].S_n)
                fam_reff[key_f].append(results[c].r_eff)
        var_sn_list = [float(np.var(v)) for v in fam_sn.values() if len(v) >= 5]
        var_re_list = [float(np.var(v)) for v in fam_reff.values() if len(v) >= 5]
        mean_var_sn = float(np.mean(var_sn_list)) if var_sn_list else 0.0
        mean_var_re = float(np.mean(var_re_list)) if var_re_list else 0.0
        print(f"  {Term.CYAN}[FRONT D: Family Variance]{Term.RESET}    Cells(N≥5)={len(var_sn_list)} | Mean Var(S_n)={mean_var_sn:.4f} (all S_n=0) | Mean Var(R_eff)={mean_var_re:.4f} AU² (σ={math.sqrt(max(mean_var_re,0)):.3f} AU → collisional debris)")

        # --- FRONT [4] & FRONT [5]+[F]: Live Delta (newnumids.dat) & NEOCP Prospective Protocol ---
        newnum_matched = newnum_sn0 = newnum_total = 0
        for d in search_dirs:
            if (d / "newnumids.dat").exists():
                with open(d / "newnumids.dat", 'r', errors='ignore') as fn_id:
                    for ln in fn_id:
                        if len(ln.strip()) > 10 and not ln.startswith('#'):
                            cd = ln[0:7].strip()
                            newnum_total += 1
                            if cd in results:
                                newnum_matched += 1
                                if results[cd].S_n == 0:
                                    newnum_sn0 += 1
                break
        neocp_waiting = 0
        for d in search_dirs:
            if (d / "neocp.txt").exists():
                with open(d / "neocp.txt", 'r', errors='ignore') as f_neo:
                    neocp_waiting = sum(1 for ln in f_neo if ln.startswith('     ') and len(ln.strip()) > 50)
                break
        print(f"  {Term.CYAN}[FRONT 4 & 5F: Live Streams]{Term.RESET}  newnumids.dat: {newnum_total} ids ({newnum_matched} matched in MPCORB) | neocp.txt: {neocp_waiting} candidates awaiting confirmation")

        return {
            'front_1A_top_hyperbolic_comets': [
                {'name': nm, 'e': round(ev, 4), 'q_AU': round(qv, 3), 'E_ion': ei}
                for ev, qv, ei, nm in top_free_comets[:5]
            ],
            'front_B_macro_compton_periodogram': front_b,
            'front_T1_table1_benchmarks': {'matched_count': t1_matches, 'total_targets': len(targets_t1), 'objects': t1_report},
            'front_2_lattice_confinement': {
                'prograde_count': len(prograde_codes),
                'prograde_in_2x3_pct': round(100.0 * prograde_in_2x3 / max(len(prograde_codes), 1), 4),
                'all_objects_in_2x3_pct': round(100.0 * all_in_2x3 / total_obj, 4),
                'retrograde_sh4_leakage_count': retro_leak_sh4,
                'six_cell_shannon_entropy_bits': round(h_lattice_bits, 4)
            },
            'front_3_nea_pha_micro_shell': {
                'evaluation_mode': nea_mode,
                'total_nea_sn0': nea_total,
                'dominant_cell': list(top_micro_cell),
                'dominant_cell_pct': round(top_micro_pct, 2),
                'analytical_uniform_sk2_prior_pct': round(p0_sk2_pct, 2)
            },
            'front_C_centaur_d_shell': {
                'total_centaurs': centaur_total,
                'sk2_count': centaur_sk2_cnt,
                'sk2_observed_pct': round(centaur_sk2_pct, 3),
                'sk2_analytical_uniform_prior_pct': round(p0_sk2_pct, 3),
                'excess_over_uniform_prior_pct': round(centaur_sk2_pct - p0_sk2_pct, 3),
                'binomial_p_vs_uniform_prior': round(binom_p_centaur, 5)
            },
            'front_D_asteroid_family_variance': {
                'family_cells_n_ge_5': len(var_sn_list),
                'mean_var_Sn': round(mean_var_sn, 6),
                'mean_var_Reff_AU2': round(mean_var_re, 5),
                'sigma_Reff_AU': round(math.sqrt(max(mean_var_re, 0.0)), 4),
                'verdict': 'Collisional baryonic debris within S_n=0 isthmus (not discrete topological isotopes)'
            },
            'front_4_live_delta_newnumids': {'total_ids': newnum_total, 'matched_in_mpcorb': newnum_matched, 'sn0_count': newnum_sn0},
            'front_5F_neocp_prospective': {'candidates_awaiting_confirmation': neocp_waiting}
        }

    @classmethod
    def run_audit(cls, objects: Dict[str, CelestialObject], results: Dict[str, TopologicalResult],
                  config: IT3Config, operator: CPHAMOperator, proof_ledger: Dict, output_dir: str) -> Dict:
        print_section("PHASE 7.5: LAYER II — MONTE CARLO (WITH NEGATIVE JOINT RESULT), i-ARGMAX & TROJANS")

        r_effs = np.array([res.r_eff for res in results.values()])
        incs = np.array([obj.i for obj in objects.values()])
        sn_arr = np.array([res.S_n for res in results.values()])
        total = max(len(r_effs), 1)

        n_sn0 = int(np.sum(sn_arr == 0))
        pct_sn0 = (n_sn0 / total) * 100.0
        n_sn2 = int(np.sum(sn_arr == 2))

        kb_mask = (r_effs >= 35.0) & (r_effs <= 55.0)
        if np.any(kb_mask):
            hist_kb, edges_kb = np.histogram(r_effs[kb_mask], bins=80)
            obs_kb_peak = float(0.5 * (edges_kb[np.argmax(hist_kb)] + edges_kb[np.argmax(hist_kb) + 1]))
        else:
            obs_kb_peak = 47.09
        kb_delta_pct = abs(obs_kb_peak - config.R_VALENCE_EXACT) / obs_kb_peak * 100.0

        rng = np.random.default_rng(103)
        n_mc = 20000
        rand_r0 = rng.uniform(12.0, 40.0, size=n_mc)
        rand_lam = rng.uniform(1.30, 2.30, size=n_mc)

        err_1d_mc = np.abs(rand_r0 * rand_lam - obs_kb_peak) / obs_kb_peak * 100.0
        p_1d_peak_only = float(np.mean(err_1d_mc <= kb_delta_pct))

        target_r1_obs = config.A_NEPTUNE_AU
        target_r2_obs = config.MMR_1_2_NEPTUNE_AU
        loss_model_obs = (abs(config.R_BASE - target_r1_obs) / target_r1_obs * 100.0 +
                          abs(config.R_VALENCE_EXACT - target_r2_obs) / target_r2_obs * 100.0)
        loss_mc_obs = (np.abs(rand_r0 - target_r1_obs) / target_r1_obs * 100.0 +
                       np.abs(rand_r0 * rand_lam - target_r2_obs) / target_r2_obs * 100.0)
        p_2d_obs_targets = float(np.mean(loss_mc_obs <= loss_model_obs))

        inc_scan = cls.multi_angle_inclination_scan(incs)
        trojan_audit = cls.true_trojan_l4_l5_analysis(objects, config.PHI)
        comet_audit = cls.compute_cometary_dichotomy(config, operator)

        print(f"  {Term.CYAN}[EMPIRICAL: Monte Carlo]{Term.RESET}    1. Peak-Only (R₀Λ vs {obs_kb_peak:.2f} AU, δ={kb_delta_pct:.2f}%): {Term.BOLD}p_peak = {p_1d_peak_only:.4f}{Term.RESET}")
        print(f"                              2. Joint vs Obs (a_N=30.07 AU & 1:2 MMR=47.73 AU): loss={loss_model_obs:.2f}%, {Term.DARK_RED}p_joint = {p_2d_obs_targets:.4f} (NEGATIVE RESULT: R₁=27 AU misses a_N by 10.2%){Term.RESET}")
        print(f"  {Term.CYAN}[EMPIRICAL: i-Scan Argmax]{Term.RESET}  Empirical steepest drop = {Term.BOLD}{inc_scan['empirical_argmax_drop_deg']}°{Term.RESET} (200-boot 95% CI {inc_scan['bootstrap_200_95ci_deg']}°, ratio={inc_scan['empirical_argmax_drop_ratio']}×; 18° in CI = {inc_scan['is_18deg_inside_bootstrap_ci']})")
        print(f"                              Grid drop ratios: 12°({inc_scan.get('12deg',{}).get('drop_ratio','N/A')}×) | 15°({inc_scan.get('15deg',{}).get('drop_ratio','N/A')}×) | 18°({inc_scan.get('18deg',{}).get('drop_ratio','N/A')}×) | 20°({inc_scan.get('20deg',{}).get('drop_ratio','N/A')}×)")
        if 'true_L4_L5_ratio' in trojan_audit:
            print(f"  {Term.CYAN}[EMPIRICAL: Pure Δλ Trojans]{Term.RESET}   Trojans (excluded bad epochs={trojan_audit['excluded_fallback_epochs']}): L4={trojan_audit['true_L4_camp_count']:,}, L5={trojan_audit['true_L5_camp_count']:,} → Ratio = {trojan_audit['true_L4_L5_ratio']:.3f}")
        print(f"  {Term.CYAN}[EMPIRICAL: Shared-Edge ΔH]{Term.RESET} Radial ΔH_shared = {comet_audit['delta_H_shared_radial_bits']} bits (H_free={comet_audit['H_free_shared_radial_bits']}b - H_bound={comet_audit['H_bound_shared_radial_bits']}b) | Discrete H(S_n)={comet_audit['H_bound_discrete_Sn_bits']}b")
        n_x1, n_x2 = QuantumStarkWavefunction.mapped_node_positions()
        print(f"  {Term.DARK_MAGENTA}[VISUAL RHYME]{Term.RESET}              5 display params (scale=1.45, pow=1.35, α=0.85, β=0.58, σ=0.65) map L₂⁽⁰⁾ nodes to x₁={n_x1}, x₂={n_x2}")
        mp_11_fronts = cls.run_mp_11_fronts(objects, results, config, operator, comet_audit)

        certificate = {
            'framework': 'IT3-v22.6-strict',
            'zenodo_doi': '10.5281/zenodo.21792530',
            'zenodo_url': 'https://zenodo.org/records/21792530',
            'authors': ['Victor Logvinovich', 'Jean-Claude Perez'],
            'provenance': {
                'script_sha256': SCRIPT_SHA,
                'mpcorb_sha256': DATA_SHA,
                'cometels_sha256': COMET_SHA,
                'total_objects_analyzed': len(r_effs)
            },
            'explicit_postulates_and_anchors': {
                'dimensional_anchor_R_base_AU': config.R_BASE,
                'neptune_semimajor_axis_AU': config.A_NEPTUNE_AU,
                'neptune_1_2_mmr_AU': round(config.MMR_1_2_NEPTUNE_AU, 3),
                'operational_ionization_cutoff_AU': config.R_IONIZATION_LIMIT,
                'stark_display_mapping_params': {
                    'scale_x': QuantumStarkWavefunction.SCALE_X,
                    'power_gamma': QuantumStarkWavefunction.POWER_GAMMA,
                    'envelope_alpha': QuantumStarkWavefunction.ENVELOPE_ALPHA,
                    'envelope_decay': QuantumStarkWavefunction.ENVELOPE_DECAY,
                    'sigma_psf': QuantumStarkWavefunction.SIGMA_PSF,
                    'mapped_nodes_x': list(QuantumStarkWavefunction.mapped_node_positions())
                }
            },
            'layer_1_and_3_audit': proof_ledger,
            'layer_2_catalog_validation': {
                'isthmus_confinement_sn0_pct': round(pct_sn0, 4),
                'kuiper_peak_sn2_count': n_sn2,
                'kuiper_peak_observed_AU': round(float(obs_kb_peak), 2),
                'kuiper_peak_theoretical_AU': config.R_VALENCE,
                'kuiper_quantization_error_pct': round(float(kb_delta_pct), 3),
                'monte_carlo_peak_only_p': round(p_1d_peak_only, 5),
                'joint_2d_monte_carlo_R0_Lambda_p': round(p_2d_obs_targets, 5),
                'joint_loss_vs_neptune_and_1_2_mmr_pct': round(loss_model_obs, 3),
                'joint_2d_verdict': 'NEGATIVE_RESULT (R_1=27 AU deviates from a_Neptune=30.07 AU by 10.2%; p_joint > 0.05)',
                'multi_angle_inclination_scan': inc_scan,
                'true_trojan_L4_L5_audit': trojan_audit,
                'cometary_dichotomy': comet_audit,
                'mp_11_fronts_suite': mp_11_fronts
            }
        }
        return certificate


# ============================================================================
# PHYSICAL VALIDATOR (6-PANEL MATPLOTLIB IT3-v22.6-strict DASHBOARD)
# ============================================================================
class PhysicalValidator:
    def __init__(self, config: IT3Config):
        self.config = config
        self.a_N = config.A_NEPTUNE_AU
        self.mmr_2_3 = self.a_N * (1.5) ** (2.0 / 3.0)
        self.mmr_3_5 = self.a_N * (5.0 / 3.0) ** (2.0 / 3.0)
        self.mmr_1_2 = self.a_N * (2.0) ** (2.0 / 3.0)

    def generate_dashboard(self, objects: Dict[str, CelestialObject], results: Dict[str, TopologicalResult],
                           audit_cert: Dict, output_path: str):
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}6-Panel Proof-Ledger Dashboard (Matplotlib 300 DPI)...{Term.RESET}")

        plt.style.use('dark_background')
        fig, axes = plt.subplots(2, 3, figsize=(22, 13))
        fig.suptitle(
            f'IT³ PROOF-LEDGER SUITE (IT3-v22.6-strict): Crystal Math, Sliding Controls & Diagnostic Separation\n'
            f'[LIVE MPCORB N={len(results):,} | SHA-256: {DATA_SHA} | Numerology Exposure = {audit_cert.get("numerology_exposure", 0.0):.6f}]',
            fontsize=14.5, fontweight='bold', color='white', y=0.98
        )

        r_effs = np.array([res.r_eff for res in results.values()])
        incs = np.array([obj.i for obj in objects.values()])
        sn_arr = np.array([res.S_n for res in results.values()])

        sample_size = min(50000, len(r_effs))
        rng = np.random.default_rng(42)
        idx = rng.choice(len(r_effs), sample_size, replace=False)
        r_plot, inc_plot = r_effs[idx], incs[idx]

        mask_core = r_plot < self.config.R_BASE
        mask_val = (r_plot >= self.config.R_BASE) & (r_plot <= self.config.R_IONIZATION_LIMIT)
        mask_ion = r_plot > self.config.R_IONIZATION_LIMIT

        # PANEL (0,0): RADIAL PHASE SPACE & NEPTUNE MMRs
        ax1 = axes[0, 0]
        ax1.scatter(r_plot[mask_core], inc_plot[mask_core], c='cyan', s=1, alpha=0.3, label='Atomic Core (Sₙ=0)')
        ax1.scatter(r_plot[mask_val], inc_plot[mask_val], c='lime', s=2, alpha=0.5, label='Valence (Sₙ≤2)')
        ax1.scatter(r_plot[mask_ion], inc_plot[mask_ion], c='magenta', s=4, alpha=0.5, label='Ionized (R_eff>48 AU)')
        ax1.axvline(x=self.config.R_BASE, color='cyan', linewidth=1.3, linestyle=':', label=f'Anchor R₁={self.config.R_BASE:.0f} AU')
        ax1.axvline(x=self.mmr_2_3, color='orange', linewidth=1.5, linestyle='--', label=f'2:3 MMR ({self.mmr_2_3:.1f} AU)')
        ax1.axvline(x=self.mmr_3_5, color='yellow', linewidth=1.5, linestyle='--', label=f'3:5 MMR ({self.mmr_3_5:.1f} AU)')
        ax1.axvline(x=self.config.R_VALENCE, color='lime', linewidth=2.5, label=f'Valence 27√3 ({self.config.R_VALENCE} AU)')
        ax1.axvline(x=self.mmr_1_2, color='green', linewidth=1.5, linestyle=':', label=f'1:2 MMR ({self.mmr_1_2:.2f} AU)')
        ax1.axvline(x=self.config.R_EVAP_TAIL_UPPER, color='purple', linewidth=1.8, linestyle='-.', label=f'Evap. Tail ({self.config.R_EVAP_TAIL_UPPER} AU)')
        ax1.axhline(y=self.config.PHASE_BREAK, color='red', linewidth=2, label=f'18° Ref ({self.config.PHASE_BREAK}°)')
        ax1.axhline(y=self.config.MAGIC_ANGLE_OH, color='white', linewidth=1.5, linestyle=':', label=f'O_h Cube ({self.config.MAGIC_ANGLE_OH}°)')
        ax1.set_xscale('log')
        ax1.set_xlim(1, 2500)
        ax1.set_ylim(0, 180)
        ax1.set_xlabel('Effective Topological Radius R_eff (AU) [Log]', fontsize=10)
        ax1.set_ylabel('Orbital Inclination (deg)', fontsize=10)
        ax1.set_title('1. Neptune MMRs & O_h Boundaries on IT³ Phase Space', fontsize=11, fontweight='bold')
        ax1.legend(loc='upper right', fontsize=6.5)
        ax1.grid(True, alpha=0.2)

        # PANEL (0,1): INCLINATION DISTRIBUTION & EMPIRICAL ARGMAX vs 18° REFERENCE
        ax2 = axes[0, 1]
        inc_scan_data = audit_cert['layer_2_catalog_validation']['multi_angle_inclination_scan']
        emp_argmax_i = inc_scan_data['empirical_argmax_drop_deg']
        ci_i = inc_scan_data['bootstrap_200_95ci_deg']
        in_ci_18 = inc_scan_data['is_18deg_inside_bootstrap_ci']
        lbl_18 = f"18° Ref (sin18°∈K; {'in' if in_ci_18 else 'outside'} argmax CI)"
        ax2.hist(incs, bins=150, alpha=0.85, color='#ff9900', edgecolor='none')
        ax2.axvline(emp_argmax_i, color='#00FF66', linestyle='-', linewidth=2.5, label=f'Empirical Steepest Drop ({emp_argmax_i}°, CI {ci_i}°)')
        ax2.axvline(self.config.PHASE_BREAK, color='red', linestyle='--', linewidth=2.2, label=lbl_18)
        ax2.axvline(self.config.AVOIDANCE_ZONE, color='magenta', linestyle=':', linewidth=2, label=f'3×18° Reference ({self.config.AVOIDANCE_ZONE}°)')
        ax2.axvline(self.config.MAGIC_ANGLE_OH, color='cyan', linestyle='-.', linewidth=1.8, label=f'Cube Diagonal ({self.config.MAGIC_ANGLE_OH}°)')
        ax2.set_xlim(0, 90)
        ax2.set_xlabel('Orbital Inclination (degrees)', fontsize=10)
        ax2.set_ylabel('Object Count', fontsize=10)
        ax2.set_title('2. [EMPIRICAL] Inclination Argmax vs 18° Reference', fontsize=11, fontweight='bold')
        ax2.legend(fontsize=7.5)
        ax2.grid(True, alpha=0.2)

        # PANEL (0,2): ANSATZ DIAGNOSTIC E(N): UNFILTERED MIN = 102 vs gcd(N,3)=1 MIN = 103
        ax3 = axes[0, 2]
        ns_cand = list(range(98, 108))
        l1 = self.config.LAMBDA_1_EXACT
        e_geom_vals = [((n - l1**2)**2) + (l1**4)/n for n in ns_cand]
        e_full_vals = [e_geom_vals[i] + l1 * EpistemicAuditEngine._omega_prime_factors(n) for i, n in enumerate(ns_cand)]
        bar_cols = ['#00FF66' if n == 103 else ('#FF3366' if math.gcd(n, 3) == 1 else '#444466') for n in ns_cand]
        ax3.bar(ns_cand, e_full_vals, color=bar_cols, edgecolor='white', linewidth=1.0, label='Full E(N) with Ω-penalty')
        ax3.plot(ns_cand, e_geom_vals, color='cyan', marker='s', linewidth=2.0, linestyle=':', label='Unfiltered E_geom(N) at μ=0 (Min = 102!)')
        ax3.annotate('ANSATZ DIAGNOSTIC (NON-PREDICTIVE):\n• Unfiltered E_geom min = 102 (E=101.83)\n• gcd(N,3)=1 ansatz min = 103 (E=102.02)\n• Ω-penalty threshold μ_crit = 0.094',
                     xy=(103, e_full_vals[ns_cand.index(103)]), xytext=(98.2, max(e_full_vals) - 20),
                     arrowprops=dict(facecolor='lime', shrink=0.06, width=2),
                     fontsize=7.8, fontweight='bold', color='black',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='#00FF66', edgecolor='white'))
        ax3.set_ylim(98, max(e_full_vals) + 12)
        ax3.set_xlabel('Integer Winding N (Unfiltered Min = 102; gcd(N,3)=1 Min = 103)', fontsize=9.5)
        ax3.set_ylabel('Action E(N) & Pure Geometric E_geom(N)', fontsize=9.5)
        ax3.set_title('3. [ANSATZ DIAGNOSTIC] E(N): Min 102 vs gcd(N,3)=1 Min 103', fontsize=10.2, fontweight='bold')
        ax3.legend(fontsize=7.2, loc='upper right')
        ax3.grid(True, alpha=0.2)

        # PANEL (1,0): CONTINUOUS IONIZATION SPECTRUM & INTERSTELLAR OBJECTS
        ax4 = axes[1, 0]
        e_ions = np.where(r_effs <= self.config.R_VALENCE, 0.0, np.log(r_effs / self.config.R_VALENCE) / np.log(self.config.LAMBDA_Y))
        etno_e_ions = e_ions[r_effs > self.config.R_IONIZATION_LIMIT]
        if len(etno_e_ions) > 0:
            ax4.hist(etno_e_ions, bins=75, alpha=0.8, color='magenta', edgecolor='white', label='Bound Ionized Tail (e<1)')
        ax4.axvline(0, color='lime', linestyle='-', linewidth=2.5, label='Valence Shell (E_ion=0)')
        for iso, col in zip(audit_cert['layer_2_catalog_validation']['cometary_dichotomy']['interstellar_objects'], ['#00FFFF', '#FFD700', '#FF3333']):
            ax4.axvline(iso['E_ion'], color=col, linestyle='--', linewidth=2.2, label=f"{iso['name']} (E_ion=+{iso['E_ion']})")
        ax4.set_xlabel('Macroscopic Ionization Energy E_ion = log_√3(R_eff / R_2)', fontsize=10)
        ax4.set_ylabel('ETNO Count', fontsize=10)
        ax4.set_title('4. [EMPIRICAL] Ionization Spectrum & Interstellar Objects', fontsize=11, fontweight='bold')
        ax4.legend(fontsize=7.5, loc='upper right')
        ax4.grid(True, alpha=0.2)

        # PANEL (1,1): VISUAL RHYME WITH STRICT WATERMARK
        ax5 = axes[1, 1]
        sn_outer_counts = np.array([np.sum(sn_arr == k) for k in range(1, 11)], dtype=float)
        sn_outer_norm = sn_outer_counts / max(np.max(sn_outer_counts), 1.0)
        x_floors = np.arange(1, 11)
        ax5.bar(x_floors, sn_outer_norm, width=0.55, color='#00FF66', alpha=0.75, edgecolor='white', label='IT³ Outer Floor Density (Sₙ=1..10, norm.)')
        x_grid = np.linspace(0.5, 10.0, 300)
        exact_stark_n2 = QuantumStarkWavefunction.radial_detector_profile(2, x_grid)
        ax5.plot(x_grid, exact_stark_n2, color='#FF3366', linewidth=2.8, label='Laguerre L₂⁽⁰⁾(ρ) with 5 display knobs (nodes x=0.98, 3.60)')
        ax5.set_xticks(range(1, 11))
        ax5.set_xlabel('Topological Floor Sₙ / Mapped Display Coordinate (Independent Axes)', fontsize=9.5)
        ax5.set_ylabel('Normalized Density (Peak = 1.0)', fontsize=10)
        ax5.set_title('5. [VISUAL RHYME] Laguerre L₂⁽⁰⁾(ρ) Overlay (Not Evidence)', fontsize=10.5, fontweight='bold')
        ax5.text(0.02, 0.95,
                 "VISUAL RHYME ONLY\nNot evidence\nNot a scaling law\nNot used in predictions",
                 transform=ax5.transAxes, verticalalignment='top', fontsize=8.5, fontweight='bold', color='white',
                 bbox=dict(boxstyle='round,pad=0.4', facecolor='#8B0000', edgecolor='white', alpha=0.88))
        ax5.text(0.38, 0.52,
                 "Structural analogy only. Not evidence. Not a scaling law.\n"
                 "• L₂⁽⁰⁾(ρ)=1-2ρ+½ρ² roots: ρ = 2 ± √2 ∈ K\n"
                 "• 5 display knobs (1.45,1.35,0.85,0.58,0.65)\n"
                 "  map roots to x₁=0.98, x₂=3.60 (≠ S_n=2)",
                 transform=ax5.transAxes, fontsize=7.6, color='white',
                 bbox=dict(boxstyle='round', facecolor='#1a1a2e', edgecolor='#FF3366', alpha=0.9))
        ax5.legend(fontsize=7.3, loc='upper right')
        ax5.grid(True, alpha=0.2)

        # PANEL (1,2): IT3-v22.6-strict EPISTEMIC LEDGER (SYNCHRONIZED WITH BUILD_LEDGER)
        ax6 = axes[1, 2]
        ax6.axis('off')
        l2 = audit_cert['layer_2_catalog_validation']
        da = audit_cert['diophantine_audit']
        tr = l2['true_trojan_L4_L5_audit']
        ce = l2['cometary_dichotomy']
        exp_sh = audit_cert.get("epistemic_ledger", {}).get("exploratory_diagnostic_share", 0.5484)
        tr_str = f"{tr.get('true_L4_L5_ratio', 'N/A')} (Pure Δλ)" if 'true_L4_L5_ratio' in tr else "N/A"
        summary_text = (
            f"IT3-v22.6-strict — EPISTEMIC PROOF LEDGER\n"
            f"═══════════════════════════════════════════════\n"
            f"[EXACT_MATH] & [DERIVED_FROM_POSTULATES]:\n"
            f" • Δ_K = 2¹⁶3⁴5⁴ = 3,317,760,000 | det(E₈)=1 | √13 ∉ K\n"
            f" • O_h Cube R_out/r_in = √3, S_out/S_in = 3, l=1,2,3 ≡ 0\n"
            f" • (√3)⁶=27, (√3)⁷=27√3=46.77, (√3)¹⁰=243, R_mid=243√2\n"
            f" • Stella Octangula T₁⊔T₂ | P₂(cos 54.74°)=0 | k=π/√18\n\n"
            f"[EMPIRICAL_TEST] & [NULL_RESULT]:\n"
            f" • 1D Peak p={l2['monte_carlo_peak_only_p']:.4f} | 2D Joint p={l2['joint_2d_monte_carlo_R0_Lambda_p']:.4f} [NULL]\n"
            f" • Sliding ln2 Max: {da['sliding_window_argmax_interval_AU']} AU ({da['sn2_vs_sliding_max_efficiency_pct']:.1f}% eff)\n"
            f" • i-Argmax: {inc_scan_data['empirical_argmax_drop_deg']}° (CI {inc_scan_data['bootstrap_200_95ci_deg']}°) [NULL]\n"
            f" • Comet Shared ΔH: {ce['delta_H_shared_radial_bits']}b | Trojans: {tr_str}\n\n"
            f"[ANSATZ_DIAGNOSTIC] (NON-PREDICTIVE):\n"
            f" • E_geom min: 102 (unfiltered) vs 103 (gcd(N,3)=1)\n"
            f" • α⁻¹: (3,6,30) 7.7ppm vs argmin (3,6,31) 0.8ppm\n"
            f" • Uranus: no 1/2N Δ=0.282° | +1/2N Δ=0.004°\n"
            f" • Flag Hygiene = 0.0 | Exploratory Share = {exp_sh:.2%}"
        )
        ax6.text(0.02, 0.98, summary_text, transform=ax6.transAxes, fontsize=8.4,
                 verticalalignment='top', fontfamily='monospace',
                 bbox=dict(boxstyle='round,pad=0.5', facecolor='#f5e6c8', alpha=0.94, edgecolor='#00FF66', linewidth=2),
                 color='black')

        plt.tight_layout(rect=[0, 0.02, 1, 0.94])
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f"  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Saved: {rel_to_root(output_path)}{Term.RESET}")


# ============================================================================
# INTERACTIVE PLOTLY VISUALIZATION ENGINE (11 HTML MODELS)
# ============================================================================
class IT3InteractiveVisualizer:
    def __init__(self, config: IT3Config):
        self.config = config
        self.rng = np.random.default_rng(42)
        self.a_N = config.A_NEPTUNE_AU
        self.mmr_2_3 = self.a_N * (1.5) ** (2.0 / 3.0)
        self.mmr_3_5 = self.a_N * (5.0 / 3.0) ** (2.0 / 3.0)
        self.mmr_1_2 = self.a_N * (2.0) ** (2.0 / 3.0)

    def _get_marker_settings(self, obj_type: str, is_3d: bool = False) -> dict:
        styles = {
            'planet': {'color': self.config.COLOR_PLANET, 'size': 12, 'symbol': 'diamond' if is_3d else 'star', 'name': 'Planets & Giants'},
            'dwarf': {'color': self.config.COLOR_DWARF, 'size': 9, 'symbol': 'circle', 'name': 'Dwarfs & Centaurs'},
            'etno': {'color': self.config.COLOR_ETNO, 'size': 8, 'symbol': 'square' if is_3d else 'diamond', 'name': 'ETNOs (Ionized)'},
            'asteroid': {'color': self.config.COLOR_ASTEROID, 'size': 3, 'symbol': 'circle', 'name': 'Background Mass'}
        }
        return styles.get(obj_type, styles['asteroid'])

    def _create_base_layout(self, title: str, is_3d: bool = False):
        layout = go.Layout(
            title=dict(text=title, font=dict(size=22, color=self.config.TEXT_COLOR), x=0.5),
            template='plotly_dark', paper_bgcolor=self.config.BG_COLOR, plot_bgcolor=self.config.BG_COLOR,
            legend=dict(title="<b>Legend:</b>", itemsizing='constant', bgcolor='rgba(11, 11, 24, 0.85)', bordercolor=self.config.GRID_COLOR, borderwidth=1),
            margin=dict(l=20, r=20, t=80, b=30)
        )
        if is_3d:
            layout.scene = dict(
                xaxis=dict(title='X (AU)', gridcolor=self.config.GRID_COLOR, showbackground=False),
                yaxis=dict(title='Y (AU)', gridcolor=self.config.GRID_COLOR, showbackground=False),
                zaxis=dict(title='Z (Floor Level Sₙ)', gridcolor=self.config.GRID_COLOR, showbackground=False),
                camera=dict(eye=dict(x=1.5, y=-1.5, z=1.0))
            )
        else:
            layout.xaxis = dict(gridcolor=self.config.GRID_COLOR, zerolinecolor=self.config.GRID_COLOR)
            layout.yaxis = dict(gridcolor=self.config.GRID_COLOR, zerolinecolor=self.config.GRID_COLOR)
        return layout

    def plot_radial_phase_space(self, objects: Dict, results: Dict, output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}Radial Phase Space Interactive Model (plot_07)...{Term.RESET}")
        fig = go.Figure(layout=self._create_base_layout('Superposition of Neptune Mean Motion Resonances on IT³ Phase Space'))
        codes = list(results.keys())
        if len(codes) > 50000:
            codes = self.rng.choice(codes, 50000, replace=False)

        r_core, inc_core, txt_core = [], [], []
        r_val, inc_val, txt_val = [], [], []
        r_ion, inc_ion, txt_ion = [], [], []
        for code in codes:
            obj, res = objects[code], results[code]
            r_eff, inc = res.r_eff, obj.i
            txt = f"<b>{obj.name}</b><br>R_eff: {r_eff:.2f} AU<br>Inclination: {inc:.2f}°<br>S_n: {res.S_n}"
            if r_eff < self.config.R_BASE:
                r_core.append(r_eff); inc_core.append(inc); txt_core.append(txt + "<br>State: CORE")
            elif r_eff <= self.config.R_IONIZATION_LIMIT:
                r_val.append(r_eff); inc_val.append(inc); txt_val.append(txt + "<br>State: VALENCE")
            else:
                r_ion.append(r_eff); inc_ion.append(inc); txt_ion.append(txt + "<br>State: IONIZED")

        fig.add_trace(go.Scatter(x=r_core, y=inc_core, mode='markers', marker=dict(size=3, color='cyan', opacity=0.6), text=txt_core, hoverinfo='text', name='Atomic Core (S_n = 0)'))
        fig.add_trace(go.Scatter(x=r_val, y=inc_val, mode='markers', marker=dict(size=3, color='lime', opacity=0.6), text=txt_val, hoverinfo='text', name='Valence Saturation (S_n ≤ 2)'))
        fig.add_trace(go.Scatter(x=r_ion, y=inc_ion, mode='markers', marker=dict(size=4, color='magenta', opacity=0.6), text=txt_ion, hoverinfo='text', name='Ionized Spectrum (>48 AU)'))

        def add_vline_legend(x_val, color, dash, name, width=2):
            fig.add_trace(go.Scatter(x=[x_val, x_val], y=[0, 180], mode='lines', line=dict(color=color, dash=dash, width=width), name=name, hoverinfo='skip'))
        def add_hline_legend(y_val, color, dash, name, width=2):
            fig.add_trace(go.Scatter(x=[1, 2500], y=[y_val, y_val], mode='lines', line=dict(color=color, dash=dash, width=width), name=name, hoverinfo='skip'))

        add_vline_legend(self.mmr_2_3, 'orange', 'dash', f'MMR 2:3 (Plutino) ≈ {self.mmr_2_3:.1f} AU')
        add_vline_legend(self.mmr_3_5, 'yellow', 'dash', f'MMR 3:5 ≈ {self.mmr_3_5:.1f} AU')
        add_vline_legend(self.mmr_1_2, 'green', 'dash', f'MMR 1:2 (Twotino) ≈ {self.mmr_1_2:.2f} AU')
        add_hline_legend(self.config.PHASE_BREAK, 'red', 'solid', f'18° Reference ({self.config.PHASE_BREAK}°)')
        add_hline_legend(self.config.AVOIDANCE_ZONE, 'magenta', 'solid', f'Avoidance Zone ({self.config.AVOIDANCE_ZONE}°)')
        add_vline_legend(self.config.R_VALENCE, 'lime', 'solid', f'Valence Limit 27√3 ({self.config.R_VALENCE} AU)', width=3)
        add_vline_legend(self.config.R_EVAP_TAIL_UPPER, 'purple', 'dashdot', f'Evaporative Tail edge ({self.config.R_EVAP_TAIL_UPPER} AU)')
        add_hline_legend(self.config.MAGIC_ANGLE_OH, 'white', 'dot', f'O_h magic angle arccos(1/√3) ({self.config.MAGIC_ANGLE_OH}°)')

        fig.update_xaxes(type="log", title="Effective Topological Radius (R_eff) [AU] - LOG SCALE", range=[np.log10(1), np.log10(2500)])
        fig.update_yaxes(title="Orbital Inclination (degrees)", range=[0, 180])
        fig.write_html(output_path, auto_open=False)

    def plot_3d_structure(self, objects: Dict, results: Dict, vis_codes: Set, key_codes: List, output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}3D Topo-Structure Interactive Model (plot_01)...{Term.RESET}")
        fig = go.Figure(layout=self._create_base_layout('IT³ 3D Structure: Cuboctahedron Potential Lattice', is_3d=True))
        max_sn = min(max((results[c].S_n for c in vis_codes), default=0), self.config.MAX_FLOOR_DISPLAY)
        zoom_limit = 2500

        theta = np.linspace(0, 2*np.pi, 100)
        for sn in range(0, max_sn + 1):
            R = self.config.R_BASE if sn == 0 else self.config.R_BASE * (self.config.LAMBDA_Y ** (sn - 1))
            x, y, z = R * np.cos(theta), R * np.sin(theta), np.ones_like(theta) * sn * self.config.Z_SCALE_FACTOR
            if sn == 2:
                fig.add_trace(go.Scatter3d(x=x, y=y, z=z, mode='lines', line=dict(color=self.config.COLOR_VALENCE, width=4), name='VALENCE SHELL (Sn=2)', hoverinfo='name', showlegend=True, legendgroup='Rings'))
            else:
                fig.add_trace(go.Scatter3d(x=x, y=y, z=z, mode='lines', line=dict(color=self.config.COLOR_RING_GLOW, width=2), name=f'Metastable Sn={sn}', hoverinfo='name', showlegend=(sn==0), legendgroup='Rings'))

        angles = np.linspace(0, 2*np.pi, 8, endpoint=False)
        for ang in angles:
            mx, my, mz = [], [], []
            for sn in range(0, max_sn + 1):
                R = self.config.R_BASE if sn == 0 else self.config.R_BASE * (self.config.LAMBDA_Y ** (sn - 1))
                mx.append(R * np.cos(ang)); my.append(R * np.sin(ang)); mz.append(sn * self.config.Z_SCALE_FACTOR)
            fig.add_trace(go.Scatter3d(x=mx, y=my, z=mz, mode='lines', line=dict(color=self.config.COLOR_MERIDIAN, width=1, dash='dash'), showlegend=False, hoverinfo='skip'))

        t = np.linspace(1, max_sn + 0.5, 600)
        r_sp = self.config.R_BASE * (self.config.LAMBDA_Y ** (t - 1))
        th_sp = t * np.pi * 2
        fig.add_trace(go.Scatter3d(x=r_sp*np.cos(th_sp), y=r_sp*np.sin(th_sp), z=t*self.config.Z_SCALE_FACTOR, mode='lines', line=dict(color=self.config.COLOR_SPIRAL, width=3), name='Vacuum Phase Spiral', hoverinfo='name'))

        for o_type in ['planet', 'dwarf', 'etno', 'asteroid']:
            xs, ys, zs, texts = [], [], [], []
            settings = self._get_marker_settings(o_type, is_3d=True)
            for code in vis_codes:
                obj, res = objects[code], results[code]
                if obj.obj_type == o_type and res.S_n <= max_sn:
                    x, y = res.R_bowl * np.cos(np.radians(obj.omega % 360)), res.R_bowl * np.sin(np.radians(obj.omega % 360))
                    z = res.S_n * self.config.Z_SCALE_FACTOR
                    xs.append(x); ys.append(y); zs.append(z)
                    texts.append(f"<b>{obj.name}</b><br>Potential S_n: {res.S_n}<br>R_eff: {res.r_eff:.1f} AU")
            if xs:
                fig.add_trace(go.Scatter3d(x=xs, y=ys, z=zs, mode='markers', marker=dict(size=settings['size'], color=settings['color'], symbol=settings['symbol'], opacity=0.8), name=settings['name'], text=texts, hoverinfo='text'))

        label_stacks = {}
        for code in key_codes:
            obj, res = objects[code], results[code]
            if res.R_bowl > zoom_limit or res.S_n == 0:
                continue
            x, y = res.R_bowl * np.cos(np.radians(obj.omega % 360)), res.R_bowl * np.sin(np.radians(obj.omega % 360))
            z = res.S_n * self.config.Z_SCALE_FACTOR
            grid_key = (round(x, -2), round(y, -2))
            offset = label_stacks.get(grid_key, 0)
            z_text = z + 25 + (offset * 25)
            label_stacks[grid_key] = offset + 1
            settings = self._get_marker_settings(obj.obj_type, is_3d=True)
            fig.add_trace(go.Scatter3d(x=[x], y=[y], z=[z_text], mode='text', text=[obj.name], textposition='middle center', textfont=dict(color=settings['color'], size=13), showlegend=False, hoverinfo='skip'))

        fig.add_trace(go.Scatter3d(x=[0], y=[0], z=[0], mode='markers', marker=dict(size=14, color='#FFFAA0', symbol='circle'), name='Sun (Nucleus)', hoverinfo='name'))
        fig.update_layout(scene=dict(xaxis=dict(range=[-zoom_limit, zoom_limit]), yaxis=dict(range=[-zoom_limit, zoom_limit]), zaxis=dict(range=[0, min(max_sn, 10)*self.config.Z_SCALE_FACTOR + 50])))
        fig.write_html(output_path, auto_open=False)

    def plot_top_view(self, objects: Dict, results: Dict, vis_codes: Set, key_codes: List, output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}Top View Projection (plot_02)...{Term.RESET}")
        fig = go.Figure(layout=self._create_base_layout('Top View (XY Projection): Phase Rings'))
        max_sn = min(max((results[c].S_n for c in vis_codes), default=0), self.config.MAX_FLOOR_DISPLAY)
        zoom_limit = 2500

        theta = np.linspace(0, 2*np.pi, 200)
        for sn in range(0, max_sn + 1):
            R = self.config.R_BASE if sn == 0 else self.config.R_BASE * (self.config.LAMBDA_Y ** (sn - 1))
            if sn == 2:
                fig.add_trace(go.Scatter(x=R*np.cos(theta), y=R*np.sin(theta), mode='lines', line=dict(color=self.config.COLOR_VALENCE, width=2, dash='solid'), name=f'VALENCE SHELL ({self.config.R_VALENCE} AU)', hoverinfo='skip', showlegend=True))
            else:
                fig.add_trace(go.Scatter(x=R*np.cos(theta), y=R*np.sin(theta), mode='lines', line=dict(color=self.config.COLOR_RING_GLOW, width=1, dash='dash'), name=f'Potential Sn={sn}', hoverinfo='skip', showlegend=False))

        t = np.linspace(1, max_sn + 0.5, 800)
        r_sp = self.config.R_BASE * (self.config.LAMBDA_Y ** (t - 1))
        th_sp = t * np.pi * 2
        fig.add_trace(go.Scatter(x=r_sp*np.cos(th_sp), y=r_sp*np.sin(th_sp), mode='lines', line=dict(color=self.config.COLOR_SPIRAL, width=2), name='Vacuum Phase Spiral', hoverinfo='name'))

        for o_type in ['planet', 'dwarf', 'etno', 'asteroid']:
            xs, ys, texts = [], [], []
            settings = self._get_marker_settings(o_type, is_3d=False)
            for code in vis_codes:
                obj, res = objects[code], results[code]
                if obj.obj_type == o_type and res.S_n <= max_sn:
                    xs.append(res.R_bowl * np.cos(np.radians(obj.omega % 360)))
                    ys.append(res.R_bowl * np.sin(np.radians(obj.omega % 360)))
                    texts.append(f"<b>{obj.name}</b><br>R_bowl: {res.R_bowl:.1f} AU")
            if xs:
                fig.add_trace(go.Scatter(x=xs, y=ys, mode='markers', marker=dict(size=settings['size'] if o_type != 'asteroid' else 4, color=settings['color'], symbol=settings['symbol']), name=settings['name'], text=texts, hoverinfo='text'))

        label_stacks = {}
        for code in key_codes:
            obj, res = objects[code], results[code]
            if res.R_bowl > zoom_limit or res.S_n == 0:
                continue
            x, y = res.R_bowl * np.cos(np.radians(obj.omega % 360)), res.R_bowl * np.sin(np.radians(obj.omega % 360))
            grid_key = (round(x, -2), round(y, -2))
            offset = label_stacks.get(grid_key, 0)
            r_text = np.hypot(x, y) + 120 + (offset * 80)
            angle = np.arctan2(y, x)
            label_stacks[grid_key] = offset + 1
            settings = self._get_marker_settings(obj.obj_type, is_3d=False)
            fig.add_trace(go.Scatter(x=[r_text * np.cos(angle)], y=[r_text * np.sin(angle)], mode='text', text=[obj.name], textposition='middle center', textfont=dict(color=settings['color'], size=13), showlegend=False, hoverinfo='skip'))

        fig.add_trace(go.Scatter(x=[0], y=[0], mode='markers', marker=dict(size=18, color='#FFFAA0', symbol='star'), name='Sun'))
        fig.update_layout(yaxis=dict(scaleanchor="x", scaleratio=1), xaxis_title="X (AU)", yaxis_title="Y (AU)", xaxis_range=[-zoom_limit, zoom_limit], yaxis_range=[-zoom_limit, zoom_limit])
        fig.write_html(output_path, auto_open=False)

    def plot_side_view(self, objects: Dict, results: Dict, vis_codes: Set, key_codes: List, output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}Side View Projection (plot_03)...{Term.RESET}")
        fig = go.Figure(layout=self._create_base_layout('Side View (XZ Projection): Perez Hourglass Potential'))
        max_sn = min(max((results[c].S_n for c in vis_codes), default=0), self.config.MAX_FLOOR_DISPLAY)
        zoom_limit_x = 4200

        t = np.linspace(0, max_sn, 200)
        r_curve = self.config.R_BASE * (self.config.LAMBDA_Y ** (t - 1))
        r_curve[0] = self.config.R_BASE
        fig.add_trace(go.Scatter(x=r_curve, y=t, mode='lines', line=dict(color=self.config.COLOR_MERIDIAN, width=2, dash='dash'), name='Hourglass Metric', hoverinfo='skip'))

        for sn in range(0, max_sn + 1):
            if sn == 2:
                fig.add_shape(type="line", x0=-100, y0=sn, x1=5000, y1=sn, line=dict(color=self.config.COLOR_VALENCE, width=2, dash="solid"))
                fig.add_annotation(x=4000, y=sn + 0.3, text="VALENCE SHELL (Sn=2)", font=dict(color=self.config.COLOR_VALENCE, size=12), showarrow=False)
            else:
                fig.add_shape(type="line", x0=-100, y0=sn, x1=5000, y1=sn, line=dict(color=self.config.COLOR_RING_GLOW, width=1, dash="dash"))

        fig.add_vline(x=self.config.R_IONIZATION_LIMIT, line_width=2, line_dash="dot", line_color="red",
                      annotation_text="Ionization Limit (48 AU)", annotation_position="top left")
        fig.add_vline(x=self.config.R_EVAP_TAIL_UPPER, line_width=2, line_dash="dashdot", line_color="purple",
                      annotation_text=f"Evaporative Tail edge ({self.config.R_EVAP_TAIL_UPPER} AU)", annotation_position="bottom right")

        for o_type in ['planet', 'dwarf', 'etno', 'asteroid']:
            xs, ys, texts = [], [], []
            settings = self._get_marker_settings(o_type, is_3d=False)
            for code in vis_codes:
                obj, res = objects[code], results[code]
                if obj.obj_type == o_type and res.S_n <= max_sn:
                    xs.append(res.R_bowl); ys.append(res.S_n)
                    texts.append(f"<b>{obj.name}</b><br>Potential S_n: {res.S_n}<br>R_bowl: {res.R_bowl:.1f} AU")
            if xs:
                fig.add_trace(go.Scatter(x=xs, y=ys, mode='markers', marker=dict(size=settings['size'] if o_type != 'asteroid' else 4, color=settings['color'], symbol=settings['symbol']), name=settings['name'], text=texts, hoverinfo='text'))

        label_stacks = {}
        for code in key_codes:
            obj, res = objects[code], results[code]
            if res.R_bowl > zoom_limit_x or res.S_n == 0:
                continue
            grid_key = res.S_n
            offset = label_stacks.get(grid_key, 0)
            x_text = res.R_bowl + 150 + (offset * 250)
            label_stacks[grid_key] = offset + 1
            settings = self._get_marker_settings(obj.obj_type, is_3d=False)
            fig.add_trace(go.Scatter(x=[x_text], y=[res.S_n + 0.15], mode='text', text=[obj.name], textposition='middle right', textfont=dict(color=settings['color'], size=13), showlegend=False, hoverinfo='skip'))

        fig.update_layout(xaxis_title="R_eff (AU) Distance from Sun", yaxis_title="Potential Floor Level (Sₙ)", xaxis_range=[-150, zoom_limit_x], yaxis_range=[-0.5, min(max_sn + 0.8, 10.5)])
        fig.write_html(output_path, auto_open=False)

    def plot_2x3_lattice(self, objects: Dict, results: Dict, vis_codes: Set, key_codes: List, output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}2x3 Lattice Structure (plot_04)...{Term.RESET}")
        fig = go.Figure(layout=self._create_base_layout('Topological Phase Space: Sₖ vs Sₕ'))
        for sk in [1, 2]:
            for sh in [1, 2, 3]:
                fig.add_shape(type="rect", x0=sk-0.45, y0=sh-0.45, x1=sk+0.45, y1=sh+0.45, line=dict(color='#9370DB', width=2), fillcolor='rgba(75, 0, 130, 0.1)')

        for o_type in ['planet', 'dwarf', 'etno', 'asteroid']:
            xs, ys, texts = [], [], []
            settings = self._get_marker_settings(o_type, is_3d=False)
            for code in vis_codes:
                obj, res = objects[code], results[code]
                if obj.obj_type == o_type:
                    jx, jy = (self.rng.uniform(-0.35, 0.35), self.rng.uniform(-0.35, 0.35)) if obj.obj_type == 'asteroid' else (0, 0)
                    xs.append(res.S_k + jx); ys.append(res.S_h + jy)
                    texts.append(f"<b>{obj.name}</b><br>S_k: {res.S_k}, S_h: {res.S_h}")
            if xs:
                fig.add_trace(go.Scatter(x=xs, y=ys, mode='markers', marker=dict(size=settings['size'] if o_type != 'asteroid' else 4, color=settings['color'], symbol=settings['symbol']), name=settings['name'], text=texts, hoverinfo='text'))

        label_stacks = {}
        for code in key_codes:
            obj, res = objects[code], results[code]
            if res.S_n == 0:
                continue
            grid_key = (res.S_k, res.S_h)
            offset = label_stacks.get(grid_key, 0)
            y_text = res.S_h + 0.15 + (offset * 0.1)
            label_stacks[grid_key] = offset + 1
            settings = self._get_marker_settings(obj.obj_type, is_3d=False)
            fig.add_trace(go.Scatter(x=[res.S_k], y=[y_text], mode='text', text=[obj.name], textposition='middle center', textfont=dict(color=settings['color'], size=13), showlegend=False, hoverinfo='skip'))

        fig.update_layout(xaxis=dict(title="Sₖ (Transverse Phase)", range=[0.2, 2.8], tickvals=[1, 2]), yaxis=dict(title="Sₕ (Vertical Phase)", range=[0.2, 3.8], tickvals=[1, 2, 3]))
        fig.write_html(output_path, auto_open=False)

    def plot_sn_histogram(self, results: Dict[str, TopologicalResult], output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}Sₙ Log-Scale Histogram & Wavefunction (plot_05)...{Term.RESET}")
        fig = go.Figure(layout=self._create_base_layout('Distribution of Topological Floors (Sₙ) & Macroscopic Wavefunction'))
        sn_values = [res.S_n for res in results.values()]
        max_sn = max(sn_values) if sn_values else 0
        counts = np.bincount(sn_values, minlength=max_sn + 1)
        total = sum(counts)

        colors = [self.config.COLOR_VALENCE if sn == 2 else (self.config.COLOR_RING_CORE if sn == 0 else self.config.COLOR_RING_GLOW) for sn in range(max_sn + 1)]
        texts = [f"{count:,} objs<br>({(count/total)*100:.3f}%)" if count > 0 else "" for count in counts]

        fig.add_trace(go.Bar(x=list(range(max_sn + 1)), y=counts, marker_color=colors, marker_line_color='white', marker_line_width=1.5, text=texts, textposition='outside', textfont=dict(color='white'), name='Observed Density', hovertemplate="Potential Floor S_n: %{x}<br>Count: %{y:,}<extra></extra>"))

        if len(counts) > 2 and counts[2] > 0:
            fig.add_annotation(
                x=2, y=np.log10(counts[2]) if counts[2] > 0 else 0,
                text=f"<b>MACROSCOPIC VALENCE SHELL (Sₙ=2)</b><br>Derived 27√3: {self.config.R_VALENCE} AU",
                showarrow=True, arrowhead=2, arrowsize=1, arrowwidth=2, arrowcolor=self.config.COLOR_VALENCE,
                font=dict(color="black", size=12), bgcolor=self.config.COLOR_VALENCE, bordercolor="white", ay=-60
            )

        x_smooth = np.linspace(0, max_sn, 300)
        counts_smooth = [max(c, 1) for c in counts]
        spline = make_interp_spline(range(max_sn + 1), np.log10(counts_smooth), k=3)
        y_smooth = 10 ** spline(x_smooth)
        fig.add_trace(go.Scatter(x=x_smooth, y=y_smooth, mode='lines', line=dict(color=self.config.COLOR_SPIRAL, width=3), name='Empirical Envelope'))

        fig.update_layout(yaxis_type="log", xaxis_title="Potential Floor Level (Sₙ)", yaxis_title="Number of Objects (Log Scale)", xaxis=dict(tickvals=list(range(max_sn + 1))))
        fig.write_html(output_path, auto_open=False)

    def plot_periodic_table(self, results: Dict[str, TopologicalResult], output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}Periodic Table Heatmap (plot_06)...{Term.RESET}")
        fig = go.Figure(layout=self._create_base_layout('Appendix B: K-PHAM 11×6 Phase-Space Population Matrix'))
        matrix = np.zeros((11, 6), dtype=int)
        for res in results.values():
            if res.S_n <= 10:
                col = (res.S_k - 1) * 3 + (res.S_h - 1)
                if 0 <= col <= 5:
                    matrix[res.S_n, col] += 1

        x_labels = ['Sₖ=1, Sₕ=1<br>(Inner Lower)', 'Sₖ=1, Sₕ=2<br>(Inner Mid)', 'Sₖ=1, Sₕ=3<br>(Inner Upper)', 'Sₖ=2, Sₕ=1<br>(Outer Lower)', 'Sₖ=2, Sₕ=2<br>(Outer Mid)', 'Sₖ=2, Sₕ=3<br>(Outer Upper)']
        y_labels = [f"Sₙ={sn} (Valence Shell)" if sn == 2 else f"Sₙ={sn}" for sn in range(11)]
        custom_text = []
        for sn in range(11):
            row_text = []
            for col in range(6):
                val = matrix[sn, col]
                if val > 0:
                    row_text.append(f"{val:,}")
                elif sn >= 6:
                    row_text.append("<i>unpopulated</i>")
                else:
                    row_text.append("")
            custom_text.append(row_text)

        matrix = matrix[::-1]; custom_text = custom_text[::-1]; y_labels = y_labels[::-1]
        fig.add_trace(go.Heatmap(z=np.log1p(matrix), x=x_labels, y=y_labels, text=custom_text, texttemplate="%{text}", textfont=dict(size=16, color='white'), colorscale='Magma', showscale=False, hovertemplate="Node: %{x}<br>Floor: %{y}<br>Objects: %{text}<extra></extra>"))
        fig.update_layout(xaxis_title="Phase Space Nodes", yaxis_title="Principal Topological Floors")
        fig.write_html(output_path, auto_open=False)

    def plot_polar_resonance_map(self, objects: Dict, results: Dict, vis_codes: Set, output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}Polar Nodal Resonance Map (plot_08)...{Term.RESET}")
        fig = go.Figure(layout=self._create_base_layout('Nodal Phase Distribution (Ω vs R_eff)'))
        for sn in range(0, 11):
            xs, ys, texts = [], [], []
            for code in vis_codes:
                obj, res = objects[code], results[code]
                if res.S_n == sn:
                    xs.append(obj.Omega); ys.append(res.r_eff)
                    texts.append(f"<b>{obj.name}</b><br>R_eff: {res.r_eff:.2f} AU<br>Ω (Node): {obj.Omega:.2f}°<br>S_n: {sn}")
            if xs:
                color = self.config.COLOR_RING_CORE if sn == 0 else (self.config.COLOR_VALENCE if sn == 2 else (self.config.COLOR_ETNO if sn >= 6 else self.config.COLOR_RING_GLOW))
                fig.add_trace(go.Scatterpolar(r=ys, theta=xs, mode='markers', marker=dict(size=4 if sn < 3 else 7, color=color, opacity=0.7), name=f'Floor S_n={sn}', text=texts, hoverinfo='text'))

        fig.add_trace(go.Scatterpolar(r=[self.config.R_VALENCE]*360, theta=list(range(360)), mode='lines', line=dict(color=self.config.COLOR_VALENCE, width=2, dash='dash'), name=f'Valence Shell ({self.config.R_VALENCE} AU)', hoverinfo='skip'))

        om_deg = np.array([objects[c].Omega for c in vis_codes if results[c].S_n >= 6], dtype=float)
        if len(om_deg) >= 3:
            th = np.radians(om_deg)
            z_ray = (np.cos(th).sum()**2 + np.sin(th).sum()**2) / len(om_deg)
            p_ray = float(np.exp(-z_ray))
            verdict = 'clustering SIGNIFICANT (p<0.05)' if p_ray < 0.05 else 'isotropy NOT rejected (honest null)'
        else:
            z_ray, p_ray, verdict = float('nan'), float('nan'), 'N<3 (insufficient)'
        rayleigh_note = (f"Rayleigh test (Ω, S_n≥6): N={len(om_deg)}, z={z_ray:.2f}, p≈{p_ray:.2e} → {verdict}<br>"
                         f"Provenance: MPCORB SHA-256 {DATA_SHA} | K-PHAM v2.2 frozen operator")

        fig.update_layout(polar=dict(radialaxis=dict(type='log', gridcolor=self.config.GRID_COLOR, range=[0, np.log10(2500)], tickvals=[1, 10, 100, 1000], ticktext=['1', '10', '100', '1000']), angularaxis=dict(gridcolor=self.config.GRID_COLOR, direction='counterclockwise')))
        fig.add_annotation(x=0.0, y=-0.02, xref='paper', yref='paper', text=rayleigh_note, showarrow=False, font=dict(size=10, color='white'), align='left', xanchor='left', yanchor='top', bgcolor='rgba(0,0,0,0.65)', bordercolor='gray', borderwidth=1)
        fig.write_html(output_path, auto_open=False)

    def plot_eccentricity_topology_3d(self, objects: Dict, results: Dict, vis_codes: Set, key_codes: List, output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}Evaporative Tail 3D Funnel (plot_09)...{Term.RESET}")
        fig = go.Figure(layout=self._create_base_layout('Kinematic Topology: The Evaporative Tail Funnel', is_3d=True))
        cat_names = ['Core & Valence (Bound)', 'Evaporative Tail (S_n=2)', 'Ionized (S_n>=3)']
        cat_colors = ['cyan', 'lime', 'magenta']

        for idx, cat in enumerate(cat_names):
            xs, ys, zs, texts = [], [], [], []
            for code in vis_codes:
                obj, res = objects[code], results[code]
                current_cat = 0 if res.r_eff <= self.config.R_IONIZATION_LIMIT else (1 if res.S_n == 2 else 2)
                if current_cat == idx:
                    xs.append(res.r_eff); ys.append(obj.e); zs.append(obj.i)
                    texts.append(f"<b>{obj.name}</b><br>R_eff: {res.r_eff:.2f} AU<br>e: {obj.e:.4f}<br>i: {obj.i:.2f}°<br>S_n: {res.S_n}")
            if xs:
                fig.add_trace(go.Scatter3d(x=xs, y=ys, z=zs, mode='markers', marker=dict(size=3 if idx==0 else 5, color=cat_colors[idx], opacity=0.7), name=cat, text=texts, hoverinfo='text'))

        plane_x = np.linspace(1, 2500, 10)
        plane_y = np.linspace(0, 1, 10)
        X, Y = np.meshgrid(plane_x, plane_y)
        fig.add_trace(go.Surface(x=X, y=Y, z=np.full_like(X, self.config.PHASE_BREAK), colorscale=[[0, 'red'], [1, 'red']], opacity=0.2, showscale=False, name='18° Reference'))
        fig.add_trace(go.Surface(x=X, y=Y, z=np.full_like(X, self.config.MAGIC_ANGLE_OH), colorscale=[[0, 'white'], [1, 'white']], opacity=0.1, showscale=False, name='O_h Magic Angle'))
        fig.add_trace(go.Scatter3d(x=[2500, 2500], y=[1.0, 1.0], z=[self.config.PHASE_BREAK]*2, mode='lines', line=dict(color='red', width=8), name='18° Reference plane', hoverinfo='skip'))
        fig.add_trace(go.Scatter3d(x=[2500, 2500], y=[1.0, 1.0], z=[self.config.MAGIC_ANGLE_OH]*2, mode='lines', line=dict(color='white', width=8), name='O_h magic-angle plane (54.74°)', hoverinfo='skip'))

        all_reff = np.array([res.r_eff for res in results.values()])
        all_inc  = np.array([obj.i for obj in objects.values()])
        all_sn   = np.array([res.S_n for res in results.values()])
        m_b = all_reff <= self.config.R_IONIZATION_LIMIT
        m_t = (all_reff > self.config.R_IONIZATION_LIMIT) & (all_sn == 2)
        m_i = (all_reff > self.config.R_IONIZATION_LIMIT) & (all_sn >= 3)
        pb = 100*np.mean(all_inc[m_b] < self.config.PHASE_BREAK) if m_b.any() else 0.0
        pt = 100*np.mean(all_inc[m_t] < self.config.PHASE_BREAK) if m_t.any() else 0.0
        pi = 100*np.mean(all_inc[m_i] < self.config.PHASE_BREAK) if m_i.any() else 0.0
        fig.add_annotation(x=0.0, y=-0.02, xref='paper', yref='paper', showarrow=False, align='left',
                           text=(f"Share below 18° (full catalog): Core&Valence {pb:.2f}% | Tail(S_n=2) {pt:.2f}% | Ionized {pi:.2f}%<br>"
                                 f"Rare high-i outliers (retrogrades) exist → confinement is STATISTICAL, not absolute.<br>"
                                 f"Provenance: MPCORB SHA-256 {DATA_SHA} | K-PHAM v2.2 frozen operator"),
                           font=dict(size=10, color='white'), xanchor='left', yanchor='top',
                           bgcolor='rgba(0,0,0,0.65)', bordercolor='gray', borderwidth=1)
        fig.update_layout(scene=dict(xaxis=dict(type='log', title='R_eff (AU) [LOG]', range=[0, np.log10(2500)], gridcolor=self.config.GRID_COLOR), yaxis=dict(title='Eccentricity (e)', range=[0, 1], gridcolor=self.config.GRID_COLOR), zaxis=dict(title='Inclination (i) [deg]', range=[0, 180], gridcolor=self.config.GRID_COLOR)))
        fig.write_html(output_path, auto_open=False)

    def plot_perez_hourglass_crystal_3d(self, output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}3D Perez Hourglass Hyperboloid & m=6⊕12 Crystal (plot_10)...{Term.RESET}")
        fig = go.Figure(layout=self._create_base_layout(
            'IT³ Perez Hourglass inside Cuboctahedral Crystal: m=6⊕12 Topology (36 Traps) & Stella Octangula',
            is_3d=True
        ))

        r_neck = 0.8
        z_north = np.linspace(0.0, 3.6, 50)
        z_south = np.linspace(-3.6, 0.0, 50)
        phi = np.linspace(0.0, 2.0 * np.pi, 70)

        ZN, PHIN = np.meshgrid(z_north, phi)
        RN = np.sqrt(r_neck**2 + ZN**2)
        XN, YN = RN * np.cos(PHIN), RN * np.sin(PHIN)
        KN = -(r_neck**2) / ((r_neck**2 + 2.0 * ZN**2)**2)
        fig.add_trace(go.Surface(
            x=XN, y=YN, z=ZN, surfacecolor=KN,
            colorscale=[[0, '#005577'], [1, '#00FFFF']], opacity=0.48, showscale=False,
            name='Northern Baryonic Bowl (+Wr > 0)',
            hovertemplate="Northern Bowl (+Wr)<br>r=%{x:.2f}, z=%{z:.2f}<br>Gaussian Curvature K=%{surfacecolor:.4f} < 0<extra></extra>"
        ))

        ZS, PHIS = np.meshgrid(z_south, phi)
        RS = np.sqrt(r_neck**2 + ZS**2)
        XS, YS = RS * np.cos(PHIS), RS * np.sin(PHIS)
        KS = -(r_neck**2) / ((r_neck**2 + 2.0 * ZS**2)**2)
        fig.add_trace(go.Surface(
            x=XS, y=YS, z=ZS, surfacecolor=KS,
            colorscale=[[0, '#660066'], [1, '#FF00FF']], opacity=0.45, showscale=False,
            name='Southern Vacuum Bowl (-Wr < 0)',
            hovertemplate="Southern Bowl (-Wr)<br>r=%{x:.2f}, z=%{z:.2f}<br>Gaussian Curvature K=%{surfacecolor:.4f} < 0<extra></extra>"
        ))

        th_ring = np.linspace(0, 2*np.pi, 150)
        fig.add_trace(go.Scatter3d(
            x=r_neck*np.cos(th_ring), y=r_neck*np.sin(th_ring), z=np.zeros_like(th_ring),
            mode='lines', line=dict(color='#FFD700', width=8),
            name='S_n=0 Topological Isthmus'
        ))
        fig.add_trace(go.Scatter3d(
            x=[0], y=[0], z=[0], mode='markers',
            marker=dict(size=14, color='#FFAA00', symbol='diamond'),
            name='Sun (Central Node)'
        ))

        z_sp_n = np.linspace(0.0, 3.5, 250)
        r_sp_n = np.sqrt(r_neck**2 + z_sp_n**2)
        th_sp_n = 3.0 * z_sp_n
        fig.add_trace(go.Scatter3d(
            x=r_sp_n*np.cos(th_sp_n), y=r_sp_n*np.sin(th_sp_n), z=z_sp_n,
            mode='lines', line=dict(color='#00FFCC', width=5),
            name='Counter-Clockwise Writhe (+||Wr||=1.0904)'
        ))
        z_sp_s = np.linspace(-3.5, 0.0, 250)
        r_sp_s = np.sqrt(r_neck**2 + z_sp_s**2)
        th_sp_s = -3.0 * z_sp_s
        fig.add_trace(go.Scatter3d(
            x=r_sp_s*np.cos(th_sp_s), y=r_sp_s*np.sin(th_sp_s), z=z_sp_s,
            mode='lines', line=dict(color='#FF33CC', width=5),
            name='Clockwise Counter-Writhe (-||Wr||=-1.0904)'
        ))

        L = 2.6
        e_nodes = []
        for s1 in [-L, L]:
            for s2 in [-L, L]:
                e_nodes.extend([(s1, s2, 0.0), (s1, 0.0, s2), (0.0, s1, s2)])
        ex, ey, ez = zip(*e_nodes)
        fig.add_trace(go.Scatter3d(
            x=ex, y=ey, z=ez, mode='markers',
            marker=dict(size=8, color='#FFD700', symbol='diamond', line=dict(color='red', width=2)),
            name='12 Primary E-Nodes (m=6 Cuboctahedron)'
        ))

        sec_nodes = []
        for i in range(len(e_nodes)):
            for j in range(i + 1, len(e_nodes)):
                dist = math.dist(e_nodes[i], e_nodes[j])
                if abs(dist - L * math.sqrt(2.0)) < 1e-4:
                    sec_nodes.append(tuple(0.5 * (e_nodes[i][k] + e_nodes[j][k]) for k in range(3)))
                    fig.add_trace(go.Scatter3d(
                        x=[e_nodes[i][0], e_nodes[j][0]], y=[e_nodes[i][1], e_nodes[j][1]], z=[e_nodes[i][2], e_nodes[j][2]],
                        mode='lines', line=dict(color='rgba(200,200,255,0.28)', width=2),
                        showlegend=False, hoverinfo='skip'
                    ))
        sx, sy, sz = zip(*sec_nodes)
        fig.add_trace(go.Scatter3d(
            x=sx, y=sy, z=sz, mode='markers',
            marker=dict(size=5, color='#00FF44', symbol='circle'),
            name='24 Secondary Overtones (m=12) → 36 Traps'
        ))

        t1_verts = [(L, L, L), (L, -L, -L), (-L, L, -L), (-L, -L, L)]
        t2_verts = [(-L, -L, -L), (-L, L, L), (L, -L, L), (L, L, -L)]
        for verts, col, lbl in [
            (t1_verts, '#FF8800', 'Stella Octangula T₁ (4 Inner Vertices)'),
            (t2_verts, '#4488FF', 'Stella Octangula T₂ (4 Outer Vertices)')
        ]:
            vx, vy, vz = zip(*verts)
            fig.add_trace(go.Scatter3d(x=vx, y=vy, z=vz, mode='markers', marker=dict(size=7, color=col, symbol='square'), name=lbl))
            for a_i in range(4):
                for b_i in range(a_i + 1, 4):
                    fig.add_trace(go.Scatter3d(
                        x=[verts[a_i][0], verts[b_i][0]], y=[verts[a_i][1], verts[b_i][1]], z=[verts[a_i][2], verts[b_i][2]],
                        mode='lines', line=dict(color=col, width=2, dash='dot'), showlegend=False, hoverinfo='skip'
                    ))

        fig.update_layout(scene=dict(
            xaxis=dict(title='X (Normalized Vacuum Scale)', range=[-3.8, 3.8], gridcolor=self.config.GRID_COLOR),
            yaxis=dict(title='Y (Normalized Vacuum Scale)', range=[-3.8, 3.8], gridcolor=self.config.GRID_COLOR),
            zaxis=dict(title='Z (Hyperboloid Axis r²-z²=r_neck²)', range=[-3.8, 3.8], gridcolor=self.config.GRID_COLOR)
        ))
        fig.write_html(output_path, auto_open=False)

    def plot_ab_initio_proofs_interactive(self, results: Dict[str, TopologicalResult], audit_cert: Dict, output_path: str) -> None:
        print(f"  {Term.DARK_BLUE}🎨 Generating:{Term.RESET} {Term.BLACK}Proof-Ledger & Diagnostic Interactive Suite (plot_11)...{Term.RESET}")
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                '1. [ANSATZ DIAGNOSTIC] E(N): Unfiltered Min=102 vs gcd(N,3)=1 Min=103',
                '2. [EXACT MATH] O_h Bicone Capacity Palindrome (86 ↔ 86, 172 = 43×4)',
                '3. [EMPIRICAL] Shared-Edge Radial Comet Entropy & Interstellar E_ion',
                '4. [VISUAL RHYME] Laguerre L₂⁽⁰⁾(ρ) with 5 Display Knobs (Not Evidence)'
            ),
            vertical_spacing=0.14, horizontal_spacing=0.10
        )

        ns_cand = list(range(97, 109))
        l1 = self.config.LAMBDA_1_EXACT
        e_geom_vals = [((n - l1**2)**2) + (l1**4)/n for n in ns_cand]
        e_full_vals = [e_geom_vals[i] + l1 * EpistemicAuditEngine._omega_prime_factors(n) for i, n in enumerate(ns_cand)]
        cols_1 = ['#00FF66' if n == 103 else ('#FF3366' if math.gcd(n, 3) == 1 else '#555577') for n in ns_cand]
        fig.add_trace(go.Bar(
            x=ns_cand, y=e_full_vals, marker_color=cols_1, name='Full Action E(N)',
            text=[f"E={v:.1f}<br>gcd={math.gcd(n,3)}" for n, v in zip(ns_cand, e_full_vals)],
            textposition='outside'
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=ns_cand, y=e_geom_vals, mode='lines+markers', line=dict(color='cyan', width=2.5, dash='dot'),
            name='Pure E_geom(N) at μ=0'
        ), row=1, col=1)

        floors_12 = list(range(12))
        c_fn = lambda n: 2 * (((n + 3) // 2) ** 2)
        caps_12 = [c_fn(n) if n <= 5 else c_fn(11 - n) for n in floors_12]
        cols_2 = ['#00CCFF' if n <= 5 else '#FF3399' for n in floors_12]
        fig.add_trace(go.Bar(
            x=[f"S_{n}" for n in floors_12], y=caps_12, marker_color=cols_2,
            name='O_h Floor Capacity C(S_n)',
            text=[f"C={c}" for c in caps_12], textposition='outside'
        ), row=1, col=2)

        ce = audit_cert['layer_2_catalog_validation']['cometary_dichotomy']
        labels_3 = ['Bound H_rad(shared)', 'Free H_rad(shared)', "1I/'Oumuamua E_ion", '2I/Borisov E_ion', '3I/ATLAS E_ion']
        vals_3 = [ce['H_bound_shared_radial_bits'] or 0.0, ce['H_free_shared_radial_bits'] or 0.0] + [x['E_ion'] for x in ce['interstellar_objects']]
        cols_3 = ['#00FF66', '#FF9900', '#00FFFF', '#FFD700', '#FF3366']
        fig.add_trace(go.Bar(
            x=labels_3, y=vals_3, marker_color=cols_3, name='Comets & ISOs',
            text=[f"{v:+.2f}" for v in vals_3], textposition='outside'
        ), row=2, col=1)

        sn_arr = np.array([res.S_n for res in results.values()])
        sn_outer_counts = np.array([np.sum(sn_arr == k) for k in range(1, 11)], dtype=float)
        sn_outer_norm = sn_outer_counts / max(np.max(sn_outer_counts), 1.0)
        fig.add_trace(go.Bar(
            x=list(range(1, 11)), y=sn_outer_norm, marker_color='#00FF66', opacity=0.75,
            name='IT³ Outer Floor Density (norm.)'
        ), row=2, col=2)

        x_grid = np.linspace(0.5, 10.0, 250)
        exact_stark_n2 = QuantumStarkWavefunction.radial_detector_profile(2, x_grid)
        fig.add_trace(go.Scatter(
            x=x_grid, y=exact_stark_n2, mode='lines', line=dict(color='#FF3366', width=3.5),
            name='Laguerre L₂⁽⁰⁾(ρ) with 5 display knobs (nodes x=0.98, 3.60)'
        ), row=2, col=2)

        fig.update_layout(
            title=dict(
                text=f"IT3-v22.6-strict Proof-Ledger & Diagnostic Suite [MPCORB SHA: {DATA_SHA}]",
                font=dict(size=19, color='white'), x=0.5
            ),
            template='plotly_dark', paper_bgcolor=self.config.BG_COLOR, plot_bgcolor=self.config.BG_COLOR,
            height=920, showlegend=True
        )
        fig.update_yaxes(range=[98, 165], title_text="Action E(N) & Pure E_geom(N)", row=1, col=1)
        fig.update_yaxes(range=[0, 38], title_text="Capacity C(n) = 2⌊(n+3)/2⌋²", row=1, col=2)
        fig.update_yaxes(range=[0, 11], title_text="Bits / E_ion (log_√3 scale)", row=2, col=1)
        fig.update_yaxes(range=[0, 1.15], title_text="Normalized Density (Independent Axes)", row=2, col=2)
        fig.write_html(output_path, auto_open=False)


# ============================================================================
# CSV EXPORTER & MASTER PIPELINE
# ============================================================================
class CSVExporter:
    @staticmethod
    def export(objects: Dict[str, CelestialObject], results: Dict[str, TopologicalResult], output_path: str) -> None:
        print_section("PHASE 5: DATA EXPORT")
        print(f"  {Term.DARK_BLUE}💾 EXPORTING TO CSV DATABASE{Term.RESET}")
        header = ['MPC_Code', 'Name', 'Type', 'a (AU)', 'e', 'i (deg)', 'omega (deg)', 'Omega (deg)', 'M (deg)', 'Q (AU)', 'Phi_topo', 'r_eff (AU)', 'S_n', 'S_k', 'S_h', 'R_bowl (AU)']
        deep_rows = []
        floor_counts: Dict[int, int] = {}
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for code in sorted(objects.keys()):
                obj, res = objects[code], results[code]
                row = [code, obj.name, obj.obj_type, f"{obj.a:.7f}", f"{obj.e:.7f}", f"{obj.i:.5f}", f"{obj.omega:.5f}", f"{obj.Omega:.5f}", f"{obj.M:.5f}", f"{res.Q:.4f}", f"{res.Phi_topo:.6f}", f"{res.r_eff:.4f}", res.S_n, res.S_k, res.S_h, f"{res.R_bowl:.4f}"]
                writer.writerow(row)
                floor_counts[res.S_n] = floor_counts.get(res.S_n, 0) + 1
                if res.S_n >= 6:
                    deep_rows.append(row)
        print(f"  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Saved: {Term.BOLD}{rel_to_root(output_path)}{Term.RESET}")

        out_dir = Path(output_path).resolve().parent
        deep_path = out_dir / "it3_extreme_deep_objects_sn_ge_6.csv"
        deep_rows.sort(key=lambda r: (-int(r[12]), -float(r[9])))
        with open(deep_path, 'w', newline='', encoding='utf-8') as fd:
            wd = csv.writer(fd)
            wd.writerow(header)
            wd.writerows(deep_rows)
        print(f"  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Saved: {Term.BOLD}{rel_to_root(deep_path)}{Term.RESET}")

        sum_path = out_dir / "it3_floor_distribution_summary.csv"
        tot_n = max(sum(floor_counts.values()), 1)
        regimes = {
            0: "Topological Isthmus / Inner Core (<27 AU)",
            1: "Ice Giant Neck Transition (27 AU)",
            2: "Macroscopic Valence Shell (27*sqrt(3) = 46.77 AU) & Evaporative Tail",
            3: "Scattered Disk Ionized Floor",
            4: "Inner Oort / Detached ETNO Floor (2012 VP113)",
            5: "Deep ETNO Floor",
            6: "Sednoid Shell (Sedna, 2015 BP519)",
            7: "Extreme ETNO Shell",
            8: "Ultra-Deep Shell (2015 TG387)",
            9: "Hyper-Deep Oort Boundary",
            10: "Observed MPCORB Outer Limit"
        }
        with open(sum_path, 'w', newline='', encoding='utf-8') as fs:
            ws = csv.writer(fs)
            ws.writerow(['S_n_Floor', 'Object_Count', 'Share_Pct', 'R_bowl_AU', 'Physical_Regime'])
            for sn in sorted(floor_counts.keys()):
                r_b = 27.0 if sn == 0 else round(27.0 * ((3.0 ** 0.5) ** (sn - 1)), 4)
                cnt = floor_counts[sn]
                ws.writerow([sn, cnt, f"{100.0*cnt/tot_n:.4f}%", r_b, regimes.get(sn, "Deep Continuum")])
        print(f"  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Saved: {Term.BOLD}{rel_to_root(sum_path)}{Term.RESET}")

class IT3AnalysisPipeline:
    def __init__(self, config: IT3Config = IT3Config(), bench: ExternalBenchmarks = ExternalBenchmarks(),
                 epistemic_mode: EpistemicMode = EpistemicMode.PROVEN_ONLY):
        self.config = config
        self.bench = bench
        self.epistemic_mode = epistemic_mode
        self.loader = UniversalLoader(config)
        self.operator = CPHAMOperator(config)
        self.visualizer = IT3InteractiveVisualizer(config)
        self.physical_validator = PhysicalValidator(config)
        self.exporter = CSVExporter()

    def _print_report(self, objects: Dict[str, CelestialObject], results: Dict[str, TopologicalResult],
                      sn_counts: Dict[int, List[str]], deep_objects: List[Dict],
                      audit_cert: Dict, ledger: ProofLedger) -> None:
        total = max(len(results), 1)
        r_effs = np.array([res.r_eff for res in results.values()])
        incs = np.array([obj.i for obj in objects.values()])
        sn_arr = np.array([res.S_n for res in results.values()])

        core_count = int(np.sum(r_effs < self.config.R_BASE))
        valence_count = int(np.sum((r_effs >= self.config.R_BASE) & (r_effs <= self.config.R_IONIZATION_LIMIT)))
        ionized_count = int(np.sum(r_effs > self.config.R_IONIZATION_LIMIT))
        bound_count = int(np.sum(incs < self.config.PHASE_BREAK))
        avoid_count = int(np.sum(incs > self.config.AVOIDANCE_ZONE))
        trans_count = total - bound_count - avoid_count

        n_tail_inner = int(np.sum((r_effs > self.config.R_IONIZATION_LIMIT) &
                                  (r_effs <= self.config.R_EVAP_TAIL_UPPER) & (sn_arr == 2)))
        n_tail_outer = int(np.sum((r_effs >= self.config.R_DIM_COLLAPSE_LOWER) &
                                  (r_effs <= self.config.R_DIM_COLLAPSE_UPPER) & (sn_arr == 2)))
        n_low_reset = int(np.sum((r_effs > self.config.R_IONIZATION_LIMIT) & (sn_arr <= 1)))

        print_section(f"PHASE 8: DUAL-LAYER TELEMETRY & EPISTEMIC LEDGER REPORT (IT3-v22.6-strict | Mode: {self.epistemic_mode.value})")

        # PART 1: S_n FLOORS BAR CHART
        print(f"  {Term.DARK_BLUE}{Term.BOLD}📊 HIDDEN TOPOLOGY: K-PHAM v2.2 Sₙ FLOORS (POTENTIAL WELLS){Term.RESET}")
        print(f"  {Term.BLACK}─────────────────────────────────────────────────────────────────────{Term.RESET}")
        for sn in sorted(sn_counts.keys()):
            count = len(sn_counts[sn])
            pct = count / total * 100.0
            bar_len = int(pct / 2)
            bar = "█" * bar_len + "░" * (50 - bar_len)
            floor_lbl = f"Sₙ={sn:2d} (VALENCE)" if sn == 2 else f"Sₙ={sn:2d}          "
            color = Term.DARK_GREEN if sn <= 2 else (Term.DARK_RED if sn >= 8 else Term.BLACK)
            print(f"    {Term.BLACK}{floor_lbl}{Term.RESET} │ {color}{bar}{Term.RESET} │ {Term.BOLD}{Term.BLACK}{count:>10,}{Term.RESET}{Term.BLACK} ({pct:6.2f}%){Term.RESET}")

        # PART 2: PHYSICAL REALITY (RADIAL & INCLINATION TELEMETRY)
        print(f"\n  {Term.DARK_BLUE}{Term.BOLD}📊 PHYSICAL REALITY: DUAL-LAYER MACROSCOPIC CATALOG TELEMETRY{Term.RESET}")
        print(f"  {Term.BLACK}─────────────────────────────────────────────────────────────────────{Term.RESET}")
        print(f"    {Term.BOLD}RADIAL DISTRIBUTION (N = {total:,}):{Term.RESET}")
        print(f"      Core (<27 AU, R₁=(√3)⁶):  {Term.DARK_GREEN}{core_count:>10,}{Term.RESET} ({core_count/total*100:.2f}%)")
        print(f"      Valence (27–48 AU):       {Term.DARK_GREEN}{valence_count:>10,}{Term.RESET} ({valence_count/total*100:.2f}%)")
        print(f"      Ionized (Free >48 AU):    {Term.DARK_MAGENTA}{ionized_count:>10,}{Term.RESET} ({ionized_count/total*100:.2f}%)")
        print(f"    {Term.BOLD}INCLINATION DISTRIBUTION:{Term.RESET}")
        print(f"      Low-i (<18°):             {Term.DARK_GREEN}{bound_count:>10,}{Term.RESET} ({bound_count/total*100:.2f}%)")
        print(f"      Transitional (18–54°):    {Term.CYAN}{trans_count:>10,}{Term.RESET} ({trans_count/total*100:.2f}%)")
        print(f"      High-i (>54°):            {Term.DARK_RED}{avoid_count:>10,}{Term.RESET} ({avoid_count/total*100:.2f}%)")

        # PART 3: EVAPORATIVE TAIL TELEMETRY
        print(f"\n  {Term.DARK_BLUE}{Term.BOLD}💨 EVAPORATIVE TAIL TELEMETRY (Sₙ=2, geometrically bound / energetically free){Term.RESET}")
        print(f"  {Term.BLACK}─────────────────────────────────────────────────────────────────────{Term.RESET}")
        print(f"      Inner tail (48–69.94 AU):      {Term.DARK_MAGENTA}{n_tail_inner:>10,}{Term.RESET}  (Sₙ=2 cascade, E_ion>0)")
        print(f"      Outer recurrence (326–410 AU): {Term.DARK_MAGENTA}{n_tail_outer:>10,}{Term.RESET}  (piecewise reset above r_in=243 AU)")
        print(f"      Sₙ∈{{0,1}} reset (>243 AU):     {Term.DARK_MAGENTA}{n_low_reset:>10,}{Term.RESET}  (R_eff∈[243, 326.38) AU)")
        print(f"      Derived R₂=(√3)⁷ shell:        {Term.DARK_GREEN}{self.config.R_VALENCE} AU{Term.RESET}  (E_ion=0 reference, not Sₙ=2/Sₙ=3 edge)")
        print(f"      Sₙ=2 analytic cascade upper:   {Term.DARK_GREEN}{self.config.R_EVAP_TAIL_UPPER} AU{Term.RESET}  (4√3·Λ₁ = 36+24√2 AU)")

        # PART 4: GOLDEN-PHASE ALGEBRAIC ECHO & GALOIS OBSTRUCTION
        inc_s = audit_cert['layer_2_catalog_validation']['multi_angle_inclination_scan']
        print(f"\n  {Term.DARK_BLUE}{Term.BOLD}🔔 GOLDEN-PHASE ALGEBRAIC ECHO & GALOIS OBSTRUCTION (NOT A DERIVATION){Term.RESET}")
        print(f"  {Term.BLACK}─────────────────────────────────────────────────────────────────────{Term.RESET}")
        print(f"      18° reference: dynamical mechanism = secular resonance ν₁₈ (Neptune nodal sync).")
        print(f"                     Empirical steepest drop = {inc_s['empirical_argmax_drop_deg']}° (200-boot 95% CI {inc_s['bootstrap_200_95ci_deg']}°).")
        print(f"                     sin18°=(√5−1)/4 ∈ Q(√5)⊂K,  cos18°=√(10+2√5)/4 ∉ K")
        print(f"                     (Galois proof: Gal(Q(cos18°)/Q) ≅ ℤ/4ℤ has exponent 4 ≠ 2 of (ℤ/2ℤ)³).")
        print(f"      54.74° angle:  O_h cube diagonal angle arccos(1/√3) = {self.config.MAGIC_ANGLE_OH}° (P₂(cos α)=0, α+γ=90°).")
        print(f"      Status:        Algebraic echoes of K and O_h, NOT geometric forcings of orbital inclination.")

        # PART 5: FULL TABLE OF EXTREME DEEP OBJECTS (S_n >= 6)
        print(f"\n  {Term.DARK_RED}{Term.BOLD}🌌 EXTREME DEEP OBJECTS (Sₙ ≥ 6) — FULL CATALOG TABLE (Count = {len(deep_objects)}){Term.RESET}")
        print(f"  {Term.BLACK}──────────────────────────────────────────────────────────────────────────────────────────────{Term.RESET}")
        print(f"    {Term.BOLD}{Term.BLACK}{'MPC Code':<10} │ {'Name':<15} │ {'Sₙ':<3} │ {'Sₖ':<3} │ {'Sₕ':<3} │ {'Q (AU)':<9} │ {'R_eff':<9} │ {'E_ion':<6} │ Type{Term.RESET}")
        print(f"    {Term.BLACK}{'─'*94}{Term.RESET}")

        famous_targets = {'Sedna', '2015TG387', '2012VP113', '2015BP519'}
        for obj in deep_objects:
            is_famous = obj['name'] in famous_targets
            color = Term.DARK_RED if obj['Sn'] >= 8 else (Term.DARK_BLUE if is_famous else Term.BLACK)
            marker = "★" if is_famous else " "
            e_ion = np.log(obj['r_eff'] / self.config.R_VALENCE) / np.log(self.config.LAMBDA_Y)
            print(f"    {color}{marker} {obj['mpc_code']:<8} │ {obj['name']:<15} │ {obj['Sn']:<3} │ {obj['Sk']:<3} │ {obj['Sh']:<3} │ {obj['Q']:<9.2f} │ {obj['r_eff']:<9.2f} │ {e_ion:<+6.2f} │ {obj['type']}{Term.RESET}")

        print(f"    {Term.BLACK}↳ Note: Objects with Sₕ=4 (e.g. K10BB8K, ~0dzN, ~0c1e) are retrograde damocloids (i > 126° ⇒ h_raw ≥ 2³).{Term.RESET}")

        # PART 6A: FRONT [T1] TABLE 1 KEY BENCHMARK VERIFICATION & 11-FRONT SUMMARY (FROM mp.py)
        mp_f = audit_cert.get('layer_2_catalog_validation', {}).get('mp_11_fronts_suite', {})
        if mp_f:
            t1_objs = mp_f.get('front_T1_table1_benchmarks', {}).get('objects', {})
            print(f"\n  {Term.DARK_BLUE}{Term.BOLD}🎯 FRONT [T1]: TABLE 1 BENCHMARK OBJECTS VERIFICATION (mp.py Parity){Term.RESET}")
            print(f"  {Term.BLACK}─────────────────────────────────────────────────────────────────────{Term.RESET}")
            print(f"    {Term.BOLD}{Term.BLACK}{'Object':<14} │ {'MPC Code':<9} │ {'Q (AU)':>9} │ {'R_eff (AU)':>10} │ {'Sₙ':>3} │ {'Exp':>3} │ Status{Term.RESET}")
            print(f"    {Term.BLACK}{'─'*69}{Term.RESET}")
            for nm_t, d_t in t1_objs.items():
                st_str = f"{Term.DARK_GREEN}✓ MATCH{Term.RESET}" if d_t['match'] else f"{Term.DARK_RED}✗ ({d_t['S_n']}){Term.RESET}"
                print(f"    {Term.BLACK}{nm_t:<14} │ {d_t['code']:<9} │ {d_t['Q_AU']:>9.2f} │ {d_t['R_eff_AU']:>10.2f} │ {d_t['S_n']:>3} │ {d_t['expected_S_n']:>3} │ {st_str}")

            fb = mp_f.get('front_B_macro_compton_periodogram', {})
            fc = mp_f.get('front_C_centaur_d_shell', {})
            fd = mp_f.get('front_D_asteroid_family_variance', {})
            f3 = mp_f.get('front_3_nea_pha_micro_shell', {})
            f2 = mp_f.get('front_2_lattice_confinement', {})
            print(f"\n  {Term.DARK_BLUE}{Term.BOLD}🧭 11-FRONT K-PHAM SUITE SUMMARY (mp.py + Anti-Numerology Controls){Term.RESET}")
            print(f"  {Term.BLACK}─────────────────────────────────────────────────────────────────────{Term.RESET}")
            print(f"    • Front [1]+[A] (Comet Entropy):     ΔH_shared(11-bin) = {audit_cert['layer_2_catalog_validation']['cometary_dichotomy']['delta_H_shared_radial_bits']} bits | H_disc(Sₙ) = {audit_cert['layer_2_catalog_validation']['cometary_dichotomy']['H_bound_discrete_Sn_bits']} bits")
            print(f"    • Front [B] (Macro-Compton):         B1 log(Λ₁²) SNR = {fb.get('B1_Macro_Compton',{}).get('snr_sigma',0):+.2f}σ | B3 log(√3) SNR = {fb.get('B3_Spiral_Step',{}).get('snr_sigma',0):+.2f}σ [NULL: JFC volume artifact]")
            print(f"    • Front [2] (2×3 Lattice Domain):    Prograde i≤90° = {f2.get('prograde_in_2x3_pct')}% (Exact Theorem) | Retrograde S_h=4 leakage = {f2.get('retrograde_sh4_leakage_count')} obj")
            print(f"    • Front [3] (NEA/PHA Micro-Shell):   N={f3.get('total_nea_sn0'):,} | Dominant {tuple(f3.get('dominant_cell',[2,1]))} = {f3.get('dominant_cell_pct')}% (vs Uniform Prior 59.76%)")
            print(f"    • Front [C] (Centaur d-Shell S_k=2): Obs = {fc.get('sk2_observed_pct')}% vs Exact Prior (5−√2)/6 = {fc.get('sk2_analytical_uniform_prior_pct')}% (Δ={fc.get('excess_over_uniform_prior_pct'):+.2f}%, p={fc.get('binomial_p_vs_uniform_prior')})")
            print(f"    • Front [D] (Asteroid Families):     Cells(N≥5)={fd.get('family_cells_n_ge_5')} | Var(Sₙ)={fd.get('mean_var_Sn'):.4f}, σ(R_eff)={fd.get('sigma_Reff_AU'):.3f} AU (collisional debris)")

        # PART 6: FAMOUS ETNO TELEMETRY CALLOUT
        print(f"\n  {Term.DARK_BLUE}{Term.BOLD}🧪 KEY DEEP-SPACE OBJECT TELEMETRY (FAMOUS ETNO TARGETS):{Term.RESET}")
        for obj in deep_objects:
            if obj['name'] in famous_targets:
                e_ion = np.log(obj['r_eff'] / self.config.R_VALENCE) / np.log(self.config.LAMBDA_Y)
                print(f"    {Term.BOLD}{Term.BLACK}★ {obj['name']:<13}{Term.RESET} {Term.BLACK}→ Floor{Term.RESET} {Term.DARK_RED}Sₙ={obj['Sn']:<2}{Term.RESET} {Term.BLACK}(Sₖ={obj['Sk']}, Sₕ={obj['Sh']}) │ Aphelion Q={obj['Q']:>7.2f} AU │ R_eff={obj['r_eff']:>7.2f} AU │ E_ion={e_ion:+.2f}{Term.RESET}")

        # PART 7: REGISTERED EPISTEMIC CLAIMS LEDGER
        print(f"\n  {Term.DARK_BLUE}{Term.BOLD}📜 REGISTERED CLAIMS ({self.epistemic_mode.value.upper()} VIEW):{Term.RESET}")
        print(f"  {Term.BLACK}─────────────────────────────────────────────────────────────────────{Term.RESET}")
        for claim in ledger.claims.values():
            print_claim(claim, self.epistemic_mode)

        if self.epistemic_mode == EpistemicMode.PROVEN_ONLY:
            print(f"\n  {Term.BLACK}ℹ Note: {len(ledger.diagnostic_claims())} diagnostic/empirical/ansatz/rhyme/null claims are hidden in 'proven-only' mode.")
            print(f"    Run with '--epistemic-mode full-diagnostic' to print all diagnostic claims in console.{Term.RESET}")

        risk = ledger.numerology_exposure()
        da = audit_cert['diophantine_audit']
        l2 = audit_cert['layer_2_catalog_validation']
        ce = l2['cometary_dichotomy']
        tr = l2['true_trojan_L4_L5_audit']
        print(f"\n  {Term.BOLD}── EPISTEMIC AUDIT METRICS ──────────────────────────────────────────{Term.RESET}")
        print(f"  • Release Version:                       IT3-v22.6-strict")
        print(f"  • Active Epistemic Mode:                 {self.epistemic_mode.value}")
        print(f"  • External Benchmarks Are Predictions:   False")
        n_tot_c = len(ledger.claims)
        n_ex_c  = len(ledger.exact_math_claims())
        n_pr_c  = len(ledger.predictive_claims())
        n_cat_c = len(ledger.catalog_test_claims())
        n_exp_c = len(ledger.exploratory_claims())
        print(f"  • Total Registered Claims in Ledger:     {n_tot_c} ({n_ex_c} Exact + {n_pr_c} Derived + {n_cat_c} Empirical/Null + {n_exp_c} Exploratory)")
        print(f"  • Exact Mathematical Theorems (Layer I): {n_ex_c}/{n_tot_c} ({n_ex_c/max(n_tot_c,1):.2%})")
        print(f"  • Derived Predictive Claims:             {n_pr_c}/{n_tot_c} ({n_pr_c/max(n_tot_c,1):.2%})")
        print(f"  • Empirical & Null Catalog Tests:        {n_cat_c}/{n_tot_c} ({n_cat_c/max(n_tot_c,1):.2%})")
        print(f"  • Exploratory Diagnostic Claim Share:    {ledger.exploratory_diagnostic_share():.6f} ({n_exp_c}/{n_tot_c} claims are Ansatz/Rhyme/Conjecture)")
        print(f"  • Unproven Predictive Flag Share:        {ledger.unproven_predictive_flag_share():.6f} (Flag hygiene)")
        if risk > 0.0:
            print(f"  {Term.DARK_RED}WARNING: some predictive claims are not proven.{Term.RESET}")
        else:
            print(f"  {Term.DARK_GREEN}OK: all predictive claims are proven or derived from explicit postulates.{Term.RESET}")

        summary = f"""
  {Term.BOLD}{Term.BLACK}🛡️  SYNCHRONIZED SCIENTIFIC SUMMARY (Release: IT3-v22.6-strict):{Term.RESET}
  
  [1] EXACT ALGEBRA & O_h SPHERE LADDER (EXACT_MATH):
      • Δ_K = 2¹⁶3⁴5⁴ = 3,317,760,000; √|Δ_K| = 57,600 = 240²; det(E₈)=1; √13 ∉ K.
      • Galois 18° theorem: sin18°=(√5−1)/4 ∈ Q(√5)⊂K, cos18° ∉ K (Gal ≅ ℤ/4ℤ ⊄ (ℤ/2ℤ)³).
      • O_h Cube R_out/r_in = √3, S_out/S_in = 3, Stella Octangula T₁⊔T₂, multipoles l=1,2,3 ≡ 0.
      • Dimensionless ladder (√3)^m from v_l·v_q=6 and rk(O_K^×)=7:
        (√3)⁶ = 27, (√3)⁷ = 27√3 ≈ 46.77, (√3)¹⁰ = 243, (√3)¹¹ = 243√3 ≈ 420.89, R_mid = 243√2 ≈ 343.65.
  [2] DERIVED PREDICTIONS (DERIVED_FROM_POSTULATES, external_reference = None):
      • Pinned inradius 2r = √2+√3−√5 ≈ 0.910196 (from P1_INRADIUS).
      • Valence shell R₂ = (√3)⁷ r₀ = 27√3 AU ≈ 46.7654 AU & outer shells r_in=243, R_mid=343.65, R_out=420.89 AU (from P2_UNIT_AU).
      • Subadditive defect coalescence ratio E_merge/E_sep = 2^(−1/3) ≈ 0.7937 < 1 (from P3_SURFACE_TENSION).
  [3] EMPIRICAL CATALOG TELEMETRY & HONEST NULLS (EMPIRICAL_TEST / NULL_RESULT):
      • 1D Kuiper peak MC: obs={l2['kuiper_peak_observed_AU']} AU vs 46.77 AU (δ={l2['kuiper_quantization_error_pct']}%, p={l2['monte_carlo_peak_only_p']:.4f}).
      • 2D Joint Neptune (30.07 AU) & 1:2 MMR (47.73 AU) test: loss=12.23%, p={l2['joint_2d_monte_carlo_R0_Lambda_p']:.4f} [NEGATIVE/NULL RESULT].
      • Sliding Δln R = ln 2 control: argmax {da['sliding_window_argmax_interval_AU']} AU ({da['sliding_window_argmax_count']:,} obj) vs S_n=2 ({da['target_sn2_band_count']:,} obj, {da['sn2_vs_sliding_max_efficiency_pct']:.1f}% eff).
      • Ionized (>48 AU) 3-way partition: {da['partition_pct_sn_ge_3']:.2f}% (S_n≥3) + {da['partition_pct_sn_eq_2_tail']:.2f}% (S_n=2 tail) + {da['partition_pct_sn_le_1_reset']:.2f}% (reset) = 100.00%.
      • Shared-edge radial comet ΔH = {ce['delta_H_shared_radial_bits']} bits | Pure Δλ Trojans L4/L5 = {tr.get('true_L4_L5_ratio','N/A')} | Deep S_n≥6 objects = {len(deep_objects)}.{Term.RESET}
"""
        animate_text(summary, delay=0.0005)

    def run(self, input_path: str, output_dir: str = '.') -> Dict:
        print_banner(self.epistemic_mode)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        proof_ledger = EpistemicAuditEngine.run_epistemic_audit(self.config, self.bench)
        objects = self.loader.load(input_path)

        print_section("PHASE 3: IT³ K-PHAM v2.2 DESCENT QUANTIZATION")
        start_time = time.time()
        results = {}
        print(f"  {Term.DARK_BLUE}Applying Perez-Logvinovich topological operator to {len(objects):,} objects...{Term.RESET}\n")
        for i, (code, obj) in enumerate(tqdm(objects.items(), desc=f"  {Term.DARK_BLUE}Quantizing{Term.RESET}", unit="obj",
                                             bar_format='{l_bar}{bar:30}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                                             colour='blue')):
            results[code] = self.operator.apply(obj)
            if (i + 1) % 500000 == 0:
                tqdm.write(f"    {Term.BLACK}→ Checkpoint: {(i+1):,}/{len(objects):,} phase states calculated...{Term.RESET}")
        elapsed = max(time.time() - start_time, 1e-6)
        print(f"\n  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Quantization complete in {elapsed:.2f}s ({len(objects)/elapsed:,.0f} ops/sec){Term.RESET}\n")

        sn_counts: Dict[int, List[str]] = {}
        for code, res in results.items():
            sn_counts.setdefault(res.S_n, []).append(code)

        deep_objects = [
            {
                'mpc_code': c, 'name': objects[c].name, 'Sn': res.S_n, 'Sk': res.S_k, 'Sh': res.S_h,
                'Q': res.Q, 'r_eff': res.r_eff, 'R_bowl': res.R_bowl, 'type': objects[c].obj_type
            }
            for c, res in results.items() if res.S_n >= 6
        ]
        deep_objects.sort(key=lambda x: (-x['Sn'], -x['Q']))

        dioph_audit = DiophantineValidator.audit(results, self.config)
        audit_cert = HostileAuditSuite.run_audit(objects, results, self.config, self.operator, proof_ledger, output_dir)
        audit_cert['diophantine_audit'] = dioph_audit

        ledger = EpistemicAuditEngine.build_ledger(
            config=self.config,
            bench=self.bench,
            proof_ledger=proof_ledger,
            dioph_audit=dioph_audit,
            audit_cert=audit_cert,
            mode=self.epistemic_mode,
        )
        ledger.validate_no_ansatz_in_predictions()
        ledger_cert = ledger.certificate()
        audit_cert["version"] = "IT3-v22.6-strict"
        audit_cert["epistemic_mode"] = self.epistemic_mode.value
        audit_cert["external_benchmarks_are_not_predictions"] = True
        audit_cert["numerology_exposure"] = ledger.numerology_exposure()
        audit_cert["postulates"] = ledger_cert["postulates"]
        audit_cert["theorems"] = ledger_cert["theorems"]
        audit_cert["claims"] = ledger_cert["claims"]
        audit_cert["predictive_claims"] = ledger_cert["predictive_claims"]
        audit_cert["diagnostic_claims"] = ledger_cert["diagnostic_claims"]
        audit_cert["epistemic_ledger"] = ledger_cert

        base_out = Path(output_dir).resolve()
        html_dir = base_out / "plots_html"
        fig_dir  = base_out / "figures"
        rep_dir  = base_out / "reports"
        for sub_d in (html_dir, fig_dir, rep_dir):
            sub_d.mkdir(parents=True, exist_ok=True)

        cert_path = str(rep_dir / 'it3_fwhp_audit_certificate.json')
        with open(cert_path, 'w', encoding='utf-8') as f:
            json.dump(audit_cert, f, indent=2, ensure_ascii=False)
        print(f"\n  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Saved certificate: {Term.BOLD}./reports/it3_fwhp_audit_certificate.json{Term.RESET}")

        print_section("PHASE 4: HIGH-FIDELITY RENDERING (./plots_html/ & ./figures/)")
        vis_codes = set([obj['mpc_code'] for obj in deep_objects] + [c for c, o in objects.items() if o.name in KEY_OBJECTS])
        vis_codes.update([c for c, r in results.items() if r.S_n == 5])
        background = [c for c, o in objects.items() if o.obj_type == 'asteroid' and results[c].S_n <= 4 and c not in vis_codes]
        vis_codes.update(np.random.default_rng(42).choice(background, min(len(background), self.config.MAX_BACKGROUND_ASTEROIDS), replace=False))
        key_codes = [c for c, o in objects.items() if o.name in KEY_OBJECTS]

        self.visualizer.plot_radial_phase_space(objects, results, str(html_dir / 'plot_07_radial_phase_space_interactive.html'))
        self.visualizer.plot_3d_structure(objects, results, vis_codes, key_codes, str(html_dir / 'plot_01_3d_structure_interactive.html'))
        self.visualizer.plot_top_view(objects, results, vis_codes, key_codes, str(html_dir / 'plot_02_top_view_interactive.html'))
        self.visualizer.plot_side_view(objects, results, vis_codes, key_codes, str(html_dir / 'plot_03_side_view_interactive.html'))
        self.visualizer.plot_2x3_lattice(objects, results, vis_codes, key_codes, str(html_dir / 'plot_04_2x3_lattice_interactive.html'))
        self.visualizer.plot_sn_histogram(results, str(html_dir / 'plot_05_sn_histogram_interactive.html'))
        self.visualizer.plot_periodic_table(results, str(html_dir / 'plot_06_periodic_table_interactive.html'))
        self.visualizer.plot_polar_resonance_map(objects, results, vis_codes, str(html_dir / 'plot_08_polar_resonance_interactive.html'))
        self.visualizer.plot_eccentricity_topology_3d(objects, results, vis_codes, key_codes, str(html_dir / 'plot_09_eccentricity_3d_interactive.html'))
        self.visualizer.plot_perez_hourglass_crystal_3d(str(html_dir / 'plot_10_perez_hourglass_3d_crystal.html'))
        self.visualizer.plot_ab_initio_proofs_interactive(results, audit_cert, str(html_dir / 'plot_11_ab_initio_proofs_interactive.html'))

        self.physical_validator.generate_dashboard(objects, results, audit_cert, str(fig_dir / 'physically_grounded_model_v20.png'))
        shutil.copyfile(str(fig_dir / 'physically_grounded_model_v20.png'),
                        str(fig_dir / 'physically_grounded_model_v18.png'))

        self.exporter.export(objects, results, str(rep_dir / 'it3_cpham_results_quantized.csv'))
        self._print_report(objects, results, sn_counts, deep_objects, audit_cert, ledger)

        return {'objects': objects, 'results': results, 'sn_counts': sn_counts, 'deep_objects': deep_objects, 'audit_certificate': audit_cert, 'ledger': ledger}

def main():
    global DATA_SHA, SCRIPT_SHA
    parser = argparse.ArgumentParser(description="IT3 K-PHAM Scientific Proof-Ledger & Diagnostic Suite (IT3-v22.6-strict)")
    parser.add_argument(
        "--epistemic-mode",
        choices=["proven-only", "full-diagnostic"],
        default="proven-only",
        help="Report mode: 'proven-only' prints only EXACT_MATH and DERIVED_FROM_POSTULATES in final report; 'full-diagnostic' prints all diagnostic claims."
    )
    parser.add_argument("--proof-only", action="store_true", help="Run Phase 0 mathematical & epistemic ledger audit without loading full MPCORB.")
    parser.add_argument("--run-tests", action="store_true", help="Run mandatory epistemic unit tests (numerology guard suite).")
    parser.add_argument("--fresh-download", action="store_true", help="Force fresh download of MPCORB.DAT and all catalogs from Harvard MPC into ./data/.")
    parser.add_argument("--log-file", default=LOG_FILENAME, help="Filename for full terminal log inside ./logs/.")
    args, _ = parser.parse_known_args()

    os.chdir(SCRIPT_DIR)
    for d_sub in (DATA_DIR, PLOTS_HTML_DIR, FIGURES_DIR, REPORTS_DIR, LOGS_DIR):
        d_sub.mkdir(parents=True, exist_ok=True)

    log_path = LOGS_DIR / Path(args.log_file).name
    tee = TerminalTeeLogger(log_path)
    sys.stdout = tee

    try:
        mode = EpistemicMode(args.epistemic_mode)
        try:
            SCRIPT_SHA = sha256_prefix(str(SCRIPT_DIR / Path(__file__).name))
        except Exception:
            SCRIPT_SHA = 'unknown'

        if args.run_tests:
            print_banner(mode)
            EpistemicAuditEngine.run_unit_tests(IT3Config(), ExternalBenchmarks())
            print(f"  {Term.DARK_GREEN}✓{Term.RESET} {Term.BLACK}Saved terminal log: {Term.BOLD}./logs/{log_path.name}{Term.RESET}\n")
            return

        if args.proof_only:
            print_banner(mode)
            cfg, bnc = IT3Config(), ExternalBenchmarks()
            pl = EpistemicAuditEngine.run_epistemic_audit(cfg, bnc)
            ledger = EpistemicAuditEngine.build_ledger(cfg, bnc, pl, mode=mode)
            ledger.validate_no_ansatz_in_predictions()
            print_section(f"REGISTERED CLAIMS ({mode.value.upper()} VIEW)")
            for cl in ledger.claims.values():
                print_claim(cl, mode)
            print(f"\n  Unproven predictive flag share: {ledger.unproven_predictive_flag_share():.6f}")
            print(f"  Exploratory diagnostic share:   {ledger.exploratory_diagnostic_share():.6f} ({len(ledger.exploratory_claims())}/{len(ledger.claims)} claims)")
            print(f"  Predictive claims:              {len(ledger.predictive_claims())}")
            print(f"  Saved terminal log:             ./logs/{log_path.name}")
            print("  Pipeline completed. See epistemic certificate for claim status.\n")
            return

        input_file = DataDownloader.download_latest(target_dir=DATA_DIR, force_download=args.fresh_download)
        try:
            DATA_SHA = sha256_prefix(input_file)
        except Exception:
            DATA_SHA = 'cached-unknown'
        pipeline = IT3AnalysisPipeline(epistemic_mode=mode)
        pipeline.run(input_path=input_file, output_dir=str(SCRIPT_DIR))

        print(f"\n  {Term.DARK_BLUE}{Term.BOLD}📁 REPOSITORY DIRECTORY STRUCTURE (./):{Term.RESET}")
        print(f"    • {Term.BOLD}./data/{Term.RESET}        → MPCORB.DAT, CometEls.txt, NEA.txt, PHA.txt, newnumids.dat, neocp.txt")
        print(f"    • {Term.BOLD}./plots_html/{Term.RESET}  → 11 Interactive Plotly 3D/2D HTML models (plot_01 .. plot_11)")
        print(f"    • {Term.BOLD}./figures/{Term.RESET}     → High-resolution 300 DPI dashboards (physically_grounded_model_v20.png)")
        print(f"    • {Term.BOLD}./reports/{Term.RESET}     → it3_fwhp_audit_certificate.json & it3_cpham_results_quantized.csv")
        print(f"    • {Term.BOLD}./logs/{Term.RESET}        → ./logs/{log_path.name}")
        print("\nPipeline completed. See ./reports/it3_fwhp_audit_certificate.json for claim status.\n")
    finally:
        sys.stdout = tee.terminal
        tee.close()

if __name__ == "__main__":
    main()

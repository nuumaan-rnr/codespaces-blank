"""High-level pipeline: config -> model -> analysis -> checks."""

from __future__ import annotations

from dataclasses import dataclass

from .checks import CheckReport, run_checks
from .config import RackConfig
from .loads import Combination, LoadCase, build_default_combinations, build_load_cases
from .model import RackModel, build_rack_model
from .results import AnalysisResults


@dataclass
class RunOutput:
    cfg: RackConfig
    model: RackModel
    load_cases: dict[str, LoadCase]
    combinations: list[Combination]
    results: AnalysisResults
    report: CheckReport


def make_engine(cfg: RackConfig):
    if cfg.analysis.engine == "rfem":
        from .engine_rfem import RFEMEngine
        return RFEMEngine(cfg, url=cfg.analysis.rfem_url)
    if cfg.analysis.engine == "internal":
        from .engine_internal import InternalEngine
        return InternalEngine(max_iterations=cfg.analysis.max_iterations,
                              tolerance=cfg.analysis.tolerance)
    raise ValueError(f"unknown engine '{cfg.analysis.engine}' "
                     f"(expected 'internal' or 'rfem')")


def run(cfg: RackConfig) -> RunOutput:
    model = build_rack_model(cfg)
    load_cases = build_load_cases(cfg, model)
    combinations = build_default_combinations(cfg)
    engine = make_engine(cfg)
    results = engine.analyze(model, load_cases, combinations)
    report = run_checks(cfg, model, results)
    return RunOutput(cfg, model, load_cases, combinations, results, report)

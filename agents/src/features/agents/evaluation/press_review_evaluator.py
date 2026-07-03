from asyncio import gather, run
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from time import perf_counter

from draive import State, ctx
from draive.evaluation import (
    EvaluationReference,
    EvaluationScoreValue,
    EvaluatorResult,
    EvaluatorSuiteResult,
    PreparedEvaluator,
    cohen_kappa,
    evaluation_score_level,
    evaluator_suite,
    quadratic_weighted_kappa,
    reference_conformance,
)
from draive.evaluators import (
    coverage_evaluator,
    factual_accuracy_evaluator,
    groundedness_evaluator,
    relevance_evaluator,
    truthfulness_evaluator,
)
from draive.openai import OpenAI, OpenAIResponsesConfig

__all__ = (
    "PressReviewParams",
    "evaluation_report",
    "press_review_suite",
    "report",
)

REFERENCE_KAPPA_GATE: float = 0.61
HALLUCINATION_DETECTION_GATE: float = 0.90
EVALUATION_TIME_GATE_SECONDS: float = 180.0

_REFERENCE_METRICS: tuple[str, ...] = (
    "truthfulness",
    "groundedness",
    "coverage",
    "relevance",
)

_HALLUCINATION_PRESENT_BELOW: float = 0.6
# The reference for the derived hallucination check is the inverted label:
# 1.0 == absent, 0.0 == present; the midpoint separates the two.
_HALLUCINATION_ABSENT_FROM: float = 0.5
# Cohen's kappa needs at least two ratings and at least two distinct levels,
# otherwise chance agreement is undefined.
_MIN_KAPPA_RATINGS: int = 2

# Calibration for the relevance judge. Uncalibrated it rates fluent digests one level
# high (excellent where human raters say good) because it treats appended editorial or
# advisory material as a "minor inclusion". Human raters count anything not selected
# from the REFERENCE as unnecessary information, which caps the rating at good.
_RELEVANCE_GUIDELINES: str = """\
Relevance measures selection from the REFERENCE only. Treat any content that is not \
drawn from the REFERENCE — editorial commentary, practical advice, recommendations, \
forward-looking speculation, or "what teams should do next" takeaways — as unnecessary \
excess information, even when it is fluent, plausible, and on the same general topic. \
Content whose body tracks the REFERENCE but which appends or interleaves such \
editorial or advisory material includes "some unnecessary information" and is rated at \
most "good". Reserve "excellent" and "perfect" for content whose every sentence \
selects information actually present in the REFERENCE. Do not penalize brevity or \
compression: omitting REFERENCE material is not a relevance flaw.\
"""


class PressReviewParams(State):
    identifier: str
    topic: str
    review: str
    sources: str
    # Ground-truth labels. When present, the matching check is scored as
    # agreement with the label instead of as raw quality (see _scored_against).
    # expected_hallucination is the PRESENCE of hallucination (True == present).
    expected_hallucination: bool | None = None
    expected_truthfulness: EvaluationReference | EvaluationScoreValue | None = None
    expected_groundedness: EvaluationReference | EvaluationScoreValue | None = None
    expected_coverage: EvaluationReference | EvaluationScoreValue | None = None
    expected_relevance: EvaluationReference | EvaluationScoreValue | None = None
    expected_factual_accuracy: EvaluationReference | EvaluationScoreValue | None = None


def _scored_against(
    result: EvaluatorResult,
    expected: EvaluationReference | EvaluationScoreValue | None,
) -> EvaluatorResult:
    if expected is None or result.meta.error is not None:
        return result

    window: EvaluationReference = EvaluationReference.of(expected)
    return EvaluatorResult.of(
        result.evaluator,
        score=reference_conformance(result.score, window),
        threshold=result.threshold,
        meta=result.meta.merged_with(
            {
                "predicted_score": result.score,
                "reference_lower": window.lower,
                "reference_upper": window.upper,
                "within_reference": window.contains(result.score),
            }
        ),
    )


@evaluator_suite(
    PressReviewParams,
    name="press_review",
    storage=Path(__file__).parent / "press_review" / "cases.json",
    concurrent_evaluations=2,
)
async def press_review_suite(
    parameters: PressReviewParams,
) -> Sequence[EvaluatorResult]:
    truthfulness_check: PreparedEvaluator[PressReviewParams] = truthfulness_evaluator.contra_map(
        PressReviewParams._.review
    ).prepared(reference=parameters.sources)
    groundedness_check: PreparedEvaluator[PressReviewParams] = groundedness_evaluator.contra_map(
        PressReviewParams._.review
    ).prepared(reference=parameters.sources)
    coverage_check: PreparedEvaluator[PressReviewParams] = coverage_evaluator.contra_map(
        PressReviewParams._.review
    ).prepared(reference=parameters.sources)
    relevance_check: PreparedEvaluator[PressReviewParams] = relevance_evaluator.contra_map(
        PressReviewParams._.review
    ).prepared(
        reference=parameters.sources,
        guidelines=_RELEVANCE_GUIDELINES,
    )
    # factual_accuracy judges claims against world knowledge, so it takes no source.
    factual_accuracy_check: PreparedEvaluator[PressReviewParams] = (
        factual_accuracy_evaluator.contra_map(PressReviewParams._.review).prepared()
    )

    # The judges are independent, so run them concurrently and collect their RAW
    # quality scores. Label conformance is applied afterwards so the hallucination
    # formula below sees the true scores rather than agreement values.
    started_at: float = perf_counter()
    (
        truthfulness_result,
        groundedness_result,
        coverage_result,
        relevance_result,
        factual_accuracy_result,
    ) = await gather(
        truthfulness_check(parameters),
        groundedness_check(parameters),
        coverage_check(parameters),
        relevance_check(parameters),
        factual_accuracy_check(parameters),
    )
    elapsed_seconds: float = perf_counter() - started_at

    # Hallucination is fabricated or unsupported content. Rather than spending a
    # separate judge on it, derive it deterministically from the two reference-grounded
    # judges already computed: a review is only hallucination-free when it stays
    # anchored to its sources (groundedness) and does not contradict them
    # (truthfulness). Coverage and relevance say nothing about fabrication, so they
    # are excluded. factual_accuracy is ALSO excluded — unlike the other two it has
    # no REFERENCE to check against, and its guideline explicitly defaults to "good"
    # for any plausible-but-unverifiable claim (nearly all current-events content),
    # so it lands at exactly the "good" cutoff in ~2/3 of cases and, as a min() input,
    # was pinning the derived score exactly on the hallucination/clean boundary for
    # both hallucinated and clean cases alike — noise, not signal. Freedom from
    # hallucination is the weaker of the two remaining signals — a single low signal
    # already means something was made up.
    hallucination_result: EvaluatorResult = EvaluatorResult.of(
        "hallucination",
        score=min(
            groundedness_result.score,
            truthfulness_result.score,
        ),
        threshold="good",
        meta={
            "comment": "Derived deterministically as min(groundedness, truthfulness).",
            "groundedness": groundedness_result.score,
            "truthfulness": truthfulness_result.score,
        },
    )

    # The derived score measures the ABSENCE of hallucination while
    # expected_hallucination records its PRESENCE, so invert the label.
    expected_no_hallucination: EvaluationScoreValue | None = (
        None if parameters.expected_hallucination is None else not parameters.expected_hallucination
    )

    return [
        _scored_against(truthfulness_result, parameters.expected_truthfulness),
        _scored_against(groundedness_result, parameters.expected_groundedness),
        _scored_against(coverage_result, parameters.expected_coverage),
        _scored_against(relevance_result, parameters.expected_relevance),
        _scored_against(factual_accuracy_result, parameters.expected_factual_accuracy),
        _scored_against(hallucination_result, expected_no_hallucination),
        EvaluatorResult.of(
            "evaluation_time",
            score=1.0 if elapsed_seconds <= EVALUATION_TIME_GATE_SECONDS else 0.0,
            threshold="good",
            meta={
                "elapsed_seconds": elapsed_seconds,
                "budget_seconds": EVALUATION_TIME_GATE_SECONDS,
            },
        ),
    ]


def _score_percentage(score: float) -> float:
    # Express a score as a 0-100% performance. draive's built-in performance is
    # score / threshold, which runs past 100% on any clear pass; here a perfect
    # score is 100% and the threshold only decides passed / failed. Scores are
    # already in [0, 1]; the cap only guards against rounding.
    return min(100.0, score * 100.0)


def _check_line(check: EvaluatorResult) -> str:
    # The headline percentage is whatever the check measures: for a labelled
    # check it is agreement with the ground-truth label, for an unlabelled one it
    # is the raw quality score. Spell out which, and surface the prediction behind
    # an agreement number so the report stands on its own.
    status: str = "passed" if check.passed else "failed"
    head: str = f"  {check.evaluator:<16} {status}  {_score_percentage(check.score):>6.2f}%"

    elapsed: float | None = check.meta.get_float("elapsed_seconds")
    if elapsed is not None:
        budget: float = check.meta.get_float("budget_seconds", default=EVALUATION_TIME_GATE_SECONDS)
        return f"{head}  {elapsed:.1f}s vs budget {budget:.0f}s"

    predicted: float | None = check.meta.get_float("predicted_score")
    if predicted is None:
        return f"{head}  quality {check.score:.3f} (no label)"

    lower: float = check.meta.get_float("reference_lower", default=0.0)
    upper: float = check.meta.get_float("reference_upper", default=1.0)
    window: str = f"{lower:.2f}" if lower == upper else f"[{lower:.2f}, {upper:.2f}]"
    return f"{head}  agreement — predicted {predicted:.3f} vs expected {window}"


def evaluation_report(result: EvaluatorSuiteResult) -> str:
    lines: list[str] = []
    suite_percentages: list[float] = []
    for case in result.results:
        checks: list[EvaluatorResult] = [
            check for check in case.results if isinstance(check, EvaluatorResult)
        ]
        check_percentages: list[float] = [_score_percentage(check.score) for check in checks]
        case_performance: float = (
            sum(check_percentages) / len(check_percentages) if check_percentages else 0.0
        )
        suite_percentages.append(case_performance)

        case_status: str = "passed" if case.passed else "failed"
        lines.append(f"\n{case.case_identifier}: {case_status} ({case_performance:.2f}%)")
        lines.extend(_check_line(check) for check in checks)

    suite_performance: float = (
        sum(suite_percentages) / len(suite_percentages) if suite_percentages else 0.0
    )
    suite_status: str = "passed" if result.passed else "failed"
    return "\n".join((f"{result.suite}: {suite_status} ({suite_performance:.2f}%)", *lines))


class _GateObservations(State):
    judge_levels_by_metric: Mapping[str, Sequence[str]]
    human_levels_by_metric: Mapping[str, Sequence[str]]
    hallucination_predicted: Sequence[str]
    hallucination_expected: Sequence[str]
    elapsed_seconds: Sequence[float]


def _collect_observations(result: EvaluatorSuiteResult) -> _GateObservations:
    judge_levels_by_metric: dict[str, list[str]] = {metric: [] for metric in _REFERENCE_METRICS}
    human_levels_by_metric: dict[str, list[str]] = {metric: [] for metric in _REFERENCE_METRICS}
    hallucination_predicted: list[str] = []
    hallucination_expected: list[str] = []
    elapsed_seconds: list[float] = []

    for case in result.results:
        for check in case.results:
            if not isinstance(check, EvaluatorResult):
                continue

            elapsed: float | None = check.meta.get_float("elapsed_seconds")
            if elapsed is not None:
                elapsed_seconds.append(elapsed)
                continue

            predicted: float | None = check.meta.get_float("predicted_score")
            if predicted is None:  # only labelled checks have a reference to agree with
                continue

            lower: float = check.meta.get_float("reference_lower", default=0.0)
            upper: float = check.meta.get_float("reference_upper", default=1.0)
            reference_value: float = (lower + upper) / 2.0

            if check.evaluator == "hallucination":
                hallucination_predicted.append(
                    "present" if predicted < _HALLUCINATION_PRESENT_BELOW else "absent"
                )
                hallucination_expected.append(
                    "present" if reference_value < _HALLUCINATION_ABSENT_FROM else "absent"
                )

            elif check.evaluator in _REFERENCE_METRICS:
                judge_levels_by_metric[check.evaluator].append(evaluation_score_level(predicted))
                human_levels_by_metric[check.evaluator].append(
                    evaluation_score_level(reference_value)
                )

    return _GateObservations(
        judge_levels_by_metric=judge_levels_by_metric,
        human_levels_by_metric=human_levels_by_metric,
        hallucination_predicted=hallucination_predicted,
        hallucination_expected=hallucination_expected,
        elapsed_seconds=elapsed_seconds,
    )


def _accuracy_section(observations: _GateObservations) -> tuple[bool, list[str]]:
    passed: bool = True
    lines: list[str] = [f"1. Accuracy — κ per base evaluator, gate>{REFERENCE_KAPPA_GATE:.2f}:"]
    for metric in _REFERENCE_METRICS:
        judge_levels: Sequence[str] = observations.judge_levels_by_metric[metric]
        human_levels: Sequence[str] = observations.human_levels_by_metric[metric]
        if (
            len(judge_levels) >= _MIN_KAPPA_RATINGS
            and len(set(judge_levels) | set(human_levels)) >= _MIN_KAPPA_RATINGS
        ):
            weighted: float = quadratic_weighted_kappa(judge_levels, human_levels)
            unweighted: float = cohen_kappa(judge_levels, human_levels)
            metric_ok: bool = weighted > REFERENCE_KAPPA_GATE
            passed = passed and metric_ok
            lines.append(
                f"  {metric:<14} QWK={weighted:+.3f} (unweighted κ={unweighted:+.3f})"
                f"  {'PASS' if metric_ok else 'FAIL'}  [n={len(judge_levels)}]"
            )
        else:
            passed = False
            lines.append(
                f"  {metric:<14} insufficient data for κ  [n={len(judge_levels)}]"
                "  (need ≥2 labelled cases with varied ratings)"
            )

    return passed, lines


def _detection_section(observations: _GateObservations) -> tuple[bool, list[str]]:
    lines: list[str] = [
        f"\n2. Hallucination detection — recall, gate≥{HALLUCINATION_DETECTION_GATE:.2f}:"
    ]
    confusion: Counter[tuple[str, str]] = Counter(
        zip(
            observations.hallucination_predicted,
            observations.hallucination_expected,
            strict=True,
        )
    )
    true_positives: int = confusion[("present", "present")]
    false_negatives: int = confusion[("absent", "present")]
    false_positives: int = confusion[("present", "absent")]
    true_negatives: int = confusion[("absent", "absent")]
    actual_positives: int = true_positives + false_negatives
    if actual_positives == 0:
        lines.append("  insufficient data: no cases labelled hallucinated  [n=0]")
        return False, lines

    detection_rate: float = true_positives / actual_positives
    detection_ok: bool = detection_rate >= HALLUCINATION_DETECTION_GATE
    lines.append(
        f"  detected {true_positives}/{actual_positives} actual hallucinations"
        f" = {detection_rate * 100:.1f}%  {'PASS' if detection_ok else 'FAIL'}"
        f"  (FP={false_positives}, TN={true_negatives})"
    )
    return detection_ok, lines


def _timing_section(observations: _GateObservations) -> tuple[bool, list[str]]:
    lines: list[str] = [
        f"\n3. Evaluation time per review — gate≤{EVALUATION_TIME_GATE_SECONDS:.0f}s:"
    ]
    elapsed_seconds: Sequence[float] = observations.elapsed_seconds
    if not elapsed_seconds:
        lines.append("  insufficient data: no timed cases  [n=0]")
        return False, lines

    mean_seconds: float = sum(elapsed_seconds) / len(elapsed_seconds)
    max_seconds: float = max(elapsed_seconds)
    over_budget: int = sum(1 for s in elapsed_seconds if s > EVALUATION_TIME_GATE_SECONDS)
    timing_ok: bool = over_budget == 0
    lines.append(
        f"  mean={mean_seconds:.1f}s max={max_seconds:.1f}s"
        f"  over-budget={over_budget}/{len(elapsed_seconds)}"
        f"  {'PASS' if timing_ok else 'FAIL'}"
    )
    return timing_ok, lines


def report(result: EvaluatorSuiteResult) -> tuple[bool, str]:
    observations: _GateObservations = _collect_observations(result)
    accuracy_ok, accuracy_lines = _accuracy_section(observations)
    detection_ok, detection_lines = _detection_section(observations)
    timing_ok, timing_lines = _timing_section(observations)

    passed: bool = accuracy_ok and detection_ok and timing_ok
    header: str = f"Milestone verification gate: {'PASS' if passed else 'FAIL'}"
    return passed, "\n".join((header, *accuracy_lines, *detection_lines, *timing_lines))


if __name__ == "__main__":
    from sys import exit as sys_exit

    from draive import load_env

    load_env()

    async def main() -> int:
        async with ctx.scope(
            "evaluation",
            OpenAIResponsesConfig(model="gpt-5-mini"),
            disposables=(OpenAI(),),
        ):
            result = await press_review_suite()
            print(evaluation_report(result))
            gate_passed, gate_report = report(result)
            print(f"\n{gate_report}")
            return 0 if gate_passed else 1

    sys_exit(run(main()))

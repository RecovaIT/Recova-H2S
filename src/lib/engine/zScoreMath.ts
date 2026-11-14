import type {
  SyntheticPatientCase,
  DeterministicScoreOutput,
  RiskTier,
  MetricDirection,
} from '@/types/recova';

/**
 * Clinical minimum standard deviations per metric.
 * Prevents tiny baseline variance from producing absurd Z-scores.
 * Values derived from published clinical norms (see README §3.2).
 */
export const SD_FLOORS: Record<string, number> = {
  sleep_hours: 0.5,       // normal night-to-night variability
  hrv_ms: 5.0,            // HRV is inherently noisy
  resting_hr: 3.0,
  steps: 1500,
  hba1c: 0.15,            // % — clinically meaningful minimum change
  systolic_bp: 5.0,
  diastolic_bp: 3.0,
  phq9: 1.5,              // 1.5 points is within noise
  cognitive_score: 3.0,   // cognitive test SD floor
  core_temp_est: 0.2,
  recovery_minutes: 3.0,  // heat / OSH
  // default fallback used if metric key not present
  __default: 0.1,
};

/**
 * Direction of "badness" per metric.
 * 'lower_is_bad': a drop in value is the risk signal (sleep, cognition)
 * 'higher_is_bad': a rise in value is the risk signal (HbA1c, heat recovery)
 */
export const METRIC_DIRECTION: Record<string, MetricDirection> = {
  sleep_hours: 'lower_is_bad',
  hrv_ms: 'lower_is_bad',
  resting_hr: 'higher_is_bad',
  steps: 'lower_is_bad',
  hba1c: 'higher_is_bad',
  systolic_bp: 'higher_is_bad',
  diastolic_bp: 'higher_is_bad',
  phq9: 'higher_is_bad',
  cognitive_score: 'lower_is_bad',
  core_temp_est: 'higher_is_bad',
  recovery_minutes: 'higher_is_bad',
  __default: 'lower_is_bad',
};

/** Which tracks legitimately have a practice gain effect */
const PRACTICE_GAIN_TRACKS = new Set(['neuro-brain']);

/**
 * Compute the deterministic baseline and drift score for a synthetic patient case.
 *
 * Contract (locked — do not change without team-wide migration):
 *   - Returns a DeterministicScoreOutput with a numeric zScore, a riskTier,
 *     a confidenceIndex 0–100, and flags for missing streams.
 *   - Emergency bypass short-circuits: returns zScore = 0, riskTier = 'EMERGENCY_BYPASS',
 *     confidenceIndex = 100, and does NOT apply the math.
 *   - For a stable case, zScore must be close to 0 and tier GREEN.
 *   - The tier uses SIGNED z relative to the metric direction, not |Z|.
 */
export function computeDeterministicDrift(
  patientCase: SyntheticPatientCase
): DeterministicScoreOutput {
  // ─── Emergency short-circuit (deterministic, before any math) ───────────
  if (patientCase.acuteCrisisFlag) {
    return {
      baselineMean: 0,
      currentObservation: 0,
      sampleSd: 0,
      adjustedSe: 0,
      practiceGainOffset: 0,
      zScore: 0,
      riskTier: 'EMERGENCY_BYPASS',
      acuteCrisisFlag: true,
      confidenceIndex: 100,
      missingStreamFlags: [],
      signedZ: 0,
      metricKey: patientCase.metricKey ?? '__default',
    };
  }

  const baseline = patientCase.baselineWindow ?? [];
  const current = patientCase.currentObservations ?? [];

  // ─── Guard: minimum data requirements ───────────────────────────────────
  if (baseline.length < 2) {
    // Cannot compute variance from a single point. Return low-confidence GREEN
    // rather than crash. This path is exercised by edge cases (null data).
    return {
      baselineMean: baseline[0] ?? 0,
      currentObservation: current[0] ?? 0,
      sampleSd: 0,
      adjustedSe: 0,
      practiceGainOffset: 0,
      zScore: 0,
      riskTier: 'GREEN',
      confidenceIndex: 20,
      missingStreamFlags: ['INSUFFICIENT_BASELINE'],
      signedZ: 0,
      metricKey: patientCase.metricKey ?? '__default',
    };
  }
  if (current.length < 1) {
    return {
      baselineMean: mean(baseline),
      currentObservation: 0,
      sampleSd: sampleSd(baseline),
      adjustedSe: 0,
      practiceGainOffset: 0,
      zScore: 0,
      riskTier: 'GREEN',
      confidenceIndex: 20,
      missingStreamFlags: ['NO_CURRENT_OBSERVATION'],
      signedZ: 0,
      metricKey: patientCase.metricKey ?? '__default',
    };
  }

  // ─── Core deterministic math ────────────────────────────────────────────
  const metricKey = patientCase.metricKey ?? '__default';
  const muBaseline = mean(baseline);
  const xCurrent = mean(current);
  const sdBaseline = sampleSd(baseline);

  const sdFloor = SD_FLOORS[metricKey] ?? SD_FLOORS.__default;
  const sdEffective = Math.max(sdBaseline, sdFloor);

  // Practice gain: only for cognitive track, only for lower_is_bad cognitive metrics
  const practiceGainOffset =
    PRACTICE_GAIN_TRACKS.has(patientCase.track) && metricKey === 'cognitive_score'
      ? 0.05 * muBaseline
      : 0;

  // Pooled standard error for difference of means
  const sePooled =
    sdEffective * Math.sqrt(1 / baseline.length + 1 / current.length);

  // Confounder multiplier (structured — see Task 3.2)
  const confounderMultiplier = computeConfounderMultiplier(patientCase);

  const zRaw = (xCurrent - (muBaseline + practiceGainOffset)) / sePooled;
  const zAdjusted = zRaw / confounderMultiplier;

  // Directional sign: positive Z always means "moving toward risk"
  const direction = METRIC_DIRECTION[metricKey] ?? METRIC_DIRECTION.__default;
  const signedZ = direction === 'higher_is_bad' ? zAdjusted : -zAdjusted;

  // Tier is based on SIGNED Z, not |Z|
  const riskTier: RiskTier =
    signedZ >= 1.96 ? 'RED' :
    signedZ >= 1.0  ? 'AMBER' :
    'GREEN';

  // Confidence: degrade per missing stream + low-sample penalties
  const missingStreamFlags = [...(patientCase.missingDataStreams ?? [])];
  let confidence = 100;
  confidence -= 35 * missingStreamFlags.length;
  if (baseline.length < 3) confidence -= 15;
  if (current.length < 2) confidence -= 15;
  confidence = Math.max(20, confidence);

  return {
    baselineMean: round(muBaseline, 3),
    currentObservation: round(xCurrent, 3),
    sampleSd: round(sdBaseline, 3),
    adjustedSe: round(sePooled, 4),
    practiceGainOffset: round(practiceGainOffset, 3),
    zScore: round(zRaw, 3),        // raw Z for display (un-directionalized)
    signedZ: round(signedZ, 3),    // direction-aware Z used for tier
    riskTier,
    confidenceIndex: confidence,
    missingStreamFlags,
    metricKey,
    confounderMultiplier,
  };
}

// ─── Helpers ─────────────────────────────────────────────────────────────

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function sampleSd(xs: number[]): number {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  const v = xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1);
  return Math.sqrt(v);
}

function round(x: number, dp: number): number {
  const f = 10 ** dp;
  return Math.round(x * f) / f;
}

/**
 * Structured confounder multiplier (Task 3.2).
 * Widens the denominator when hearing / vision / language / education
 * could suppress the measured score independent of true cognitive decline.
 *
 * Heuristic: each active confounder multiplies SE by 1.15 (i.e. shrinks Z).
 * Documented in README §3.2.
 */
function computeConfounderMultiplier(patientCase: SyntheticPatientCase): number {
  const c = patientCase.confounders ?? {};
  let mult = 1.0;
  if (c.hearingLoss) mult *= 1.15;
  if (c.visionLoss) mult *= 1.10;
  if (c.nonNativeLanguage) mult *= 1.10;
  if (c.lowEducation) mult *= 1.05;
  return mult;
}
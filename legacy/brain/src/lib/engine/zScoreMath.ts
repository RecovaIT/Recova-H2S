import type {
  SyntheticPatientCase,
  DeterministicScoreOutput,
  RiskTier,
  MetricDirection,
} from '@/types/recova';

/** Clinical minimum SDs per metric — prevents tiny-baseline blowup. See README §3. */
export const SD_FLOORS: Record<string, number> = {
  sleep_hours: 0.5,
  hrv_ms: 5.0,
  resting_hr: 3.0,
  steps: 1500,
  hba1c: 0.15,
  systolic_bp: 5.0,
  diastolic_bp: 3.0,
  phq9: 1.5,
  cognitive_score: 3.0,
  core_temp_est: 0.2,
  recovery_minutes: 3.0,
  __default: 0.1,
};

/** Which direction of movement is the risk signal. */
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

const PRACTICE_GAIN_TRACKS = new Set(['neuro-brain']);

export function computeDeterministicDrift(
  patientCase: SyntheticPatientCase
): DeterministicScoreOutput {
  // ── Emergency short-circuit (deterministic, before any math) ──────────
  if (patientCase.acuteCrisisFlag) {
    return {
      baselineMean: 0, currentObservation: 0, sampleSd: 0,
      adjustedSe: 0, practiceGainOffset: 0,
      zScore: 0, signedZ: 0,
      riskTier: 'EMERGENCY_BYPASS', acuteCrisisFlag: true,
      confidenceIndex: 100, missingStreamFlags: [],
      metricKey: patientCase.metricKey ?? '__default',
    };
  }

  const baseline = patientCase.baselineWindow ?? [];
  const current = patientCase.currentObservations ?? [];
  const metricKey = patientCase.metricKey ?? '__default';

  // ── Guards: insufficient data must not crash ──────────────────────────
  if (baseline.length < 2) {
    return {
      baselineMean: baseline[0] ?? 0, currentObservation: current[0] ?? 0,
      sampleSd: 0, adjustedSe: 0, practiceGainOffset: 0,
      zScore: 0, signedZ: 0, riskTier: 'GREEN',
      confidenceIndex: 20,
      missingStreamFlags: ['INSUFFICIENT_BASELINE'],
      metricKey,
    };
  }
  if (current.length < 1) {
    return {
      baselineMean: mean(baseline), currentObservation: 0,
      sampleSd: sampleSd(baseline), adjustedSe: 0, practiceGainOffset: 0,
      zScore: 0, signedZ: 0, riskTier: 'GREEN',
      confidenceIndex: 20,
      missingStreamFlags: ['NO_CURRENT_OBSERVATION'],
      metricKey,
    };
  }

    // ── Core math ─────────────────────────────────────────────────────────
  const muBaseline = mean(baseline);
  const xCurrent = mean(current);
  const sdBaseline = sampleSd(baseline);
  const sdFloor = SD_FLOORS[metricKey] ?? SD_FLOORS.__default;
  const sdEffective = Math.max(sdBaseline, sdFloor);

  const practiceGainOffset =
    PRACTICE_GAIN_TRACKS.has(patientCase.track) && metricKey === 'cognitive_score'
      ? 0.05 * muBaseline
      : 0;

  const sePooled =
    sdEffective * Math.sqrt(1 / baseline.length + 1 / current.length);

  const confounderMultiplier = computeConfounderMultiplier(patientCase);
  const zRaw = (xCurrent - (muBaseline + practiceGainOffset)) / sePooled;
  const zAdjusted = zRaw / confounderMultiplier;

  const direction = METRIC_DIRECTION[metricKey] ?? METRIC_DIRECTION.__default;
  const signedZ = zAdjusted;
  const riskMagnitude = direction === 'higher_is_bad' ? signedZ : -signedZ;

  let riskTier: RiskTier =
    riskMagnitude >= 1.96 ? 'RED' :
    riskMagnitude >= 1.0  ? 'AMBER' :
    'GREEN';

  // Cap RED to AMBER when sensory/language confounders are present
  if (riskTier === 'RED' && confounderMultiplier > 1.0) {
    riskTier = 'AMBER';
  }

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
    zScore: round(zRaw, 3),
    signedZ: round(signedZ, 3),
    riskTier,
    confidenceIndex: confidence,
    missingStreamFlags,
    metricKey,
    confounderMultiplier,
  };
}

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
function computeConfounderMultiplier(c: SyntheticPatientCase): number {
  const cf = c.confounders ?? {};
  let m = 1.0;
  if (cf.hearingLoss) m *= 1.15;
  if (cf.visionLoss) m *= 1.10;
  if (cf.nonNativeLanguage) m *= 1.10;
  if (cf.lowEducation) m *= 1.05;
  return m;
}
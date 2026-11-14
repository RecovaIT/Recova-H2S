import { describe, it, expect } from 'vitest';
import { computeDeterministicDrift } from '@/lib/engine/zScoreMath';
import { SYNTHETIC_CASES } from '@/lib/data/syntheticCases';

describe('computeDeterministicDrift', () => {
  it('stable case → GREEN with |signedZ| < 1.0', () => {
    const r = computeDeterministicDrift(SYNTHETIC_CASES.find(c => c.id === 'rehab-case-a')!);
    expect(r.riskTier).toBe('GREEN');
    expect(Math.abs(r.signedZ)).toBeLessThan(1.0);
  });

  it('pre-relapse drift → AMBER or RED with signedZ ≤ -1.5', () => {
    const r = computeDeterministicDrift(SYNTHETIC_CASES.find(c => c.id === 'rehab-case-b')!);
    expect(['AMBER', 'RED']).toContain(r.riskTier);
    expect(r.signedZ).toBeLessThan(-1.5);
  });

  it('acute crisis → EMERGENCY_BYPASS, confidence 100', () => {
    const r = computeDeterministicDrift({
      ...SYNTHETIC_CASES[0],
      acuteCrisisFlag: true,
    });
    expect(r.riskTier).toBe('EMERGENCY_BYPASS');
    expect(r.confidenceIndex).toBe(100);
  });

  it('missing stream → confidence degraded, tier still computed', () => {
    const r = computeDeterministicDrift({
      ...SYNTHETIC_CASES[0],
      missingDataStreams: ['Smartwatch HRV'],
    });
    expect(r.confidenceIndex).toBeLessThan(100);
    expect(['GREEN', 'AMBER', 'RED']).toContain(r.riskTier);
  });

  it('HbA1c rise → RED (higher_is_bad)', () => {
    const r = computeDeterministicDrift({
      id: 'ifhas-1', track: 'ifhas-screening',
      caseLabel: 'IFHAS', patientName: 'X', age: 52, gender: 'F',
      insuranceTier: 'Thiqa', metricKey: 'hba1c',
      baselineWindow: [5.4, 5.5, 5.4, 5.6],
      currentObservations: [6.7, 6.9],
      symptomsText: 'HbA1c drift',
    });
    expect(r.riskTier).toBe('RED');
    expect(r.signedZ).toBeGreaterThan(1.96);
  });

  it('cognitive drop WITH hearing loss → AMBER (not RED)', () => {
    const r = computeDeterministicDrift({
      id: 'neuro-1', track: 'neuro-brain',
      caseLabel: 'Neuro', patientName: 'X', age: 68, gender: 'M',
      insuranceTier: 'Enhanced', metricKey: 'cognitive_score',
      baselineWindow: [88, 90, 87, 89],
      currentObservations: [78, 76],
      confounders: { hearingLoss: true },
      symptomsText: 'Hearing affected audio component',
    });
    expect(r.riskTier).toBe('AMBER');
  });

  it('zero-variance baseline → SD floor prevents blowup', () => {
    const r = computeDeterministicDrift({
      id: 'edge-zero', track: 'relapse-rehab',
      caseLabel: 'Edge', patientName: 'X', age: 30, gender: 'Other',
      insuranceTier: 'Basic', metricKey: 'sleep_hours',
      baselineWindow: [7, 7, 7, 7, 7],
      currentObservations: [7, 7],
      symptomsText: 'flat',
    });
    expect(Number.isFinite(r.signedZ)).toBe(true);
    expect(r.riskTier).toBe('GREEN');
  });

  it('null current observations → does not crash, low confidence', () => {
    const r = computeDeterministicDrift({
      id: 'edge-null', track: 'ifhas-screening',
      caseLabel: 'Edge', patientName: 'X', age: 50, gender: 'Other',
      insuranceTier: 'Basic', metricKey: 'hba1c',
      baselineWindow: [5.4, 5.5, 5.4],
      currentObservations: [],
      symptomsText: 'null',
    });
    expect(r.confidenceIndex).toBeLessThan(50);
    expect(r.missingStreamFlags).toContain('NO_CURRENT_OBSERVATION');
  });
});
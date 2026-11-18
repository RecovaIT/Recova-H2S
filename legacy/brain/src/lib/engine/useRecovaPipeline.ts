'use client';
import { useState } from 'react';
import type { SyntheticPatientCase, DeterministicScoreOutput } from '@/types/recova';
import { computeDeterministicDrift } from './zScoreMath';

export function useRecovaPipeline(activeCase: SyntheticPatientCase) {
  const [scoringResult] = useState<DeterministicScoreOutput>(() => computeDeterministicDrift(activeCase));
  return { loading: false, scoringResult, steps: [], fhirBundle: null };
}
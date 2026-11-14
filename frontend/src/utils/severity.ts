export const SEVERITIES = [
  'TRACE',
  'DEBUG',
  'INFO',
  'WARN',
  'WARNING',
  'ERROR',
  'FATAL',
  'CRITICAL',
  'UNKNOWN',
] as const

export type Severity = (typeof SEVERITIES)[number]

const ORDER: Record<string, number> = {
  TRACE: 0,
  DEBUG: 1,
  INFO: 2,
  WARN: 3,
  WARNING: 4,
  ERROR: 5,
  FATAL: 6,
  CRITICAL: 7,
  UNKNOWN: -1,
}

export function severityRank(sev: string): number {
  return ORDER[sev] ?? -1
}

export function isErrorLike(sev: string): boolean {
  return sev === 'ERROR' || sev === 'FATAL' || sev === 'CRITICAL'
}

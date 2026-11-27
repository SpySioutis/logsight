import axios from 'axios'

const baseURL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api`
  : '/api'

export const api = axios.create({ baseURL, timeout: 120000 })

export interface ImportRecord {
  id: string
  filename: string
  file_size: number
  file_hash: string
  format: string
  status: string
  total_lines: number
  parsed_count: number
  error_count: number
  duplicate_of: string | null
  error_message: string | null
  started_at: string | null
  finished_at: string | null
  duplicate?: boolean
}

export interface LogEntry {
  id: string
  import_id: string
  timestamp: string | null
  severity: string
  service: string | null
  source: string | null
  message: string
  raw: string | null
  attributes: Record<string, unknown> | null
  fingerprint: string | null
  trace_id: string | null
  request_id: string | null
  seq?: number | null
  snippet?: string | null
}

export interface LogPage {
  items: LogEntry[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface LogQuery {
  q?: string
  severity?: string[]
  source?: string
  service?: string
  import_id?: string
  trace_id?: string
  request_id?: string
  date_from?: string
  date_to?: string
  sort?: string
  direction?: 'asc' | 'desc'
  page?: number
  page_size?: number
}

export function toParams(query: LogQuery): Record<string, string | string[]> {
  const params: Record<string, string | string[]> = {}
  if (query.q) params.q = query.q
  if (query.severity?.length) params.severity = query.severity
  if (query.source) params.source = query.source
  if (query.service) params.service = query.service
  if (query.import_id) params.import_id = query.import_id
  if (query.trace_id) params.trace_id = query.trace_id
  if (query.request_id) params.request_id = query.request_id
  if (query.date_from) params.date_from = query.date_from
  if (query.date_to) params.date_to = query.date_to
  if (query.sort) params.sort = query.sort
  if (query.direction) params.direction = query.direction
  if (query.page) params.page = String(query.page)
  if (query.page_size) params.page_size = String(query.page_size)
  return params
}

const LOCAL_INPUT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/

/**
 * `datetime-local` values carry no offset; the backend would read them as
 * UTC. Convert them to the instant the user meant (their local time).
 * Values that already carry an offset/`Z` pass through unchanged.
 */
export function localInputToIso(value: string): string {
  if (!LOCAL_INPUT.test(value)) return value
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toISOString()
}

/** Format an instant as a `datetime-local` value in the user's timezone. */
export function isoToLocalInput(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** Params for API calls: like `toParams`, with dates as UTC instants. */
export function apiParams(query: LogQuery): Record<string, string | string[]> {
  const params = toParams(query)
  if (typeof params.date_from === 'string') params.date_from = localInputToIso(params.date_from)
  if (typeof params.date_to === 'string') params.date_to = localInputToIso(params.date_to)
  return params
}

/** Download URL for the current explorer filters (all pages, capped server-side). */
export function exportUrl(query: LogQuery, format: 'csv' | 'jsonl'): string {
  const params = apiParams(query)
  delete params.page
  delete params.page_size
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    for (const v of Array.isArray(value) ? value : [value]) search.append(key, v)
  }
  search.set('format', format)
  return `${baseURL}/logs/export?${search.toString()}`
}

export interface LogHistogram {
  bucket: 'minute' | 'hour' | 'day' | 'month'
  points: TimelinePoint[]
}

export interface LogContext {
  entry: LogEntry
  before: LogEntry[]
  after: LogEntry[]
}

export interface DashboardSummary {
  total: number
  errors: number
  warnings: number
  info: number
  critical: number
  sources: number
  imports: number
  first_seen: string | null
  last_seen: string | null
}

export interface TimelinePoint {
  bucket: string
  total: number
  errors: number
}

export interface ErrorGroup {
  fingerprint: string
  sample: string
  severity: string
  count: number
  sources: string[]
  first_seen: string | null
  last_seen: string | null
  status: string
  assignee: string | null
  note: string | null
}

export interface ErrorTrendPoint {
  bucket: string
  count: number
}

export interface TraceSummary {
  trace_id: string
  count: number
  services: string[]
  severities: string[]
  first_seen: string | null
  last_seen: string | null
}

export interface TraceDetail extends TraceSummary {
  duration_seconds: number | null
  entries: LogEntry[]
}

export interface SavedFilter {
  id: string
  name: string
  description: string | null
  params: LogQuery
  created_at: string | null
  updated_at: string | null
}

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

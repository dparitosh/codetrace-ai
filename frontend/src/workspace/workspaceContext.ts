import { createContext, useContext } from 'react'
import type { ReviewRecord } from '../reviewSession'
import type { Catalog, TraceGraph, TraceNode } from './types'

export interface WorkspaceGraphState {
  graph: TraceGraph | null
  review: ReviewRecord | null
  sourceLabel: string
  busy: boolean
  uploaded: boolean
  notice: string
  synchronize: () => Promise<void>
  analyzeUpload: (files: File[]) => Promise<boolean>
  select: (node: TraceNode | null) => void
  openGraph: () => void
}
export const WorkspaceGraphContext = createContext<WorkspaceGraphState | null>(null)
export function mergeSnapshotReview(current: ReviewRecord | null, incoming: ReviewRecord): ReviewRecord {
  if (current?.id === incoming.id && current.sessionToken === incoming.sessionToken
      && current.result_digest === incoming.result_digest) return { ...incoming, result: current.result ?? incoming.result }
  return incoming
}
export function useWorkspaceGraph() {
  const context = useContext(WorkspaceGraphContext)
  if (!context) throw new Error('Source views require a workspace graph context.')
  return context
}

export function agentTimeoutSeconds(catalog: Catalog, profileTimeout?: number) {
  return profileTimeout || catalog.ai.agent_timeout_seconds || catalog.settings.request_timeout_seconds + 5
}

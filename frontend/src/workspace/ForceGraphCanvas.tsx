import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import { D3ForceGraph, type ForceGraphActions, type ForceGraphOptions } from './D3ForceGraph'
import type { TraceGraph, TraceNode } from './types'

interface Props { graph: TraceGraph | null; nodes: TraceNode[]; edges: TraceGraph['edges']; options: ForceGraphOptions; onSelect: (node: TraceNode | null) => void; onExpand: (node: TraceNode) => void }

const ForceGraphCanvas = forwardRef<ForceGraphActions, Props>(function ForceGraphCanvas(props, ref) {
  const container = useRef<HTMLDivElement>(null)
  const engine = useRef<D3ForceGraph | null>(null)
  const callbacks = useRef(props)
  callbacks.current = props
  useImperativeHandle(ref, () => ({ fit: () => engine.current?.fit(), zoomBy: factor => engine.current?.zoomBy(factor),
    reheat: () => engine.current?.reheat(), releasePins: () => engine.current?.releasePins() }), [])
  useEffect(() => {
    const graph = new D3ForceGraph(container.current!, node => callbacks.current.onSelect(node), node => callbacks.current.onExpand(node))
    engine.current = graph
    return () => { graph.destroy(); engine.current = null }
  }, [])
  const { graph, nodes, edges, options } = props
  useEffect(() => { engine.current?.update(graph, nodes, edges, options) }, [graph, nodes, edges, options])
  return <div className="graph-canvas d3-force-stage" ref={container} aria-label="Interactive lifecycle graph canvas" />
})
export default ForceGraphCanvas

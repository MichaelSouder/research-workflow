import { useMemo, useEffect, useCallback, useRef } from 'react'
import {
  ReactFlow,
  useNodesState,
  useEdgesState,
  addEdge,
  Controls,
  Background,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { STAGE_ORDER, STAGE_LABELS, STEP_TO_STAGE, getStageState } from '../../constants'
import { PIPELINE_EDGES, getDefaultNodePositions } from './constants'
import PipelineFlowNode from './PipelineFlowNode'

const nodeTypes = { stage: PipelineFlowNode }

function buildNodes(status, currentStep, selectedNodeId = null) {
  const currentStageId = status === 'completed' ? null : (STEP_TO_STAGE[currentStep] ?? null)
  const currentStageIndex = currentStageId ? STAGE_ORDER.indexOf(currentStageId) : -1
  const positions = getDefaultNodePositions()

  return STAGE_ORDER.map((stageId, i) => {
    const state = getStageState(stageId, i, currentStageIndex, status || 'idle')
    return {
      id: stageId,
      type: 'stage',
      position: positions[stageId],
      data: {
        stageId,
        label: STAGE_LABELS[stageId],
        state,
        selected: selectedNodeId === stageId,
      },
      draggable: false,
    }
  })
}

function buildEdges() {
  return PIPELINE_EDGES.map(([source, target]) => ({
    id: `e-${source}-${target}`,
    source,
    target,
  }))
}

/** Convert API definition (nodes/edges) to React Flow nodes with run status merged in. */
function definitionToFlowNodes(definitionNodes, definitionEdges, status, currentStep, selectedNodeId) {
  const currentStageId = status === 'completed' ? null : (STEP_TO_STAGE[currentStep] ?? null)
  const stageOrder = definitionNodes.map((n) => n.id)
  const currentStageIndex = currentStageId ? stageOrder.indexOf(currentStageId) : -1

  return (definitionNodes || []).map((node, i) => {
    const stageId = node.id
    const state = getStageState(stageId, i, currentStageIndex, status || 'idle')
    const pos = node.position && typeof node.position.x === 'number' && typeof node.position.y === 'number'
      ? node.position
      : { x: i * 220, y: 0 }
    const pipelineType = node.type || 'stage'
    return {
      id: node.id,
      type: 'stage',
      position: pos,
      data: {
        stageId: node.id,
        label: node.data?.label ?? node.id,
        state,
        selected: selectedNodeId === node.id,
        pipelineType,
      },
      draggable: true,
    }
  })
}

function definitionToFlowEdges(definitionEdges) {
  return (definitionEdges || []).map((e) => ({
    id: e.id || `e-${e.source}-${e.target}`,
    source: e.source,
    target: e.target,
  }))
}

/** Serialize React Flow nodes/edges back to API definition format. */
function flowToDefinition(nodes, edges) {
  const outNodes = nodes.map((n) => ({
    id: n.id,
    type: n.data?.pipelineType ?? n.type ?? 'stage',
    position: { x: n.position?.x ?? 0, y: n.position?.y ?? 0 },
    data: { label: n.data?.label ?? n.id },
  }))
  const outEdges = edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
  }))
  return { nodes: outNodes, edges: outEdges }
}

const initialEdges = buildEdges()

function PipelineFlowInner({
  status,
  currentStep,
  selectedNodeId,
  onNodeClick,
  definition,
  onDefinitionChange,
  editable,
}) {
  const hasDefinition = definition && Array.isArray(definition.nodes)
  const initialNodes = useMemo(
    () =>
      hasDefinition
        ? definitionToFlowNodes(
            definition.nodes,
            definition.edges,
            status ?? 'idle',
            currentStep ?? '',
            selectedNodeId
          )
        : buildNodes(status ?? 'idle', currentStep ?? '', selectedNodeId),
    [hasDefinition, definition?.nodes, definition?.edges, status, currentStep, selectedNodeId]
  )
  const initialEdgesFromDef = useMemo(
    () => (hasDefinition ? definitionToFlowEdges(definition.edges) : buildEdges()),
    [hasDefinition, definition?.edges]
  )
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdgesFromDef)
  const onDefinitionChangeRef = useRef(onDefinitionChange)
  onDefinitionChangeRef.current = onDefinitionChange

  useEffect(() => {
    if (hasDefinition) {
      setNodes(
        definitionToFlowNodes(
          definition.nodes,
          definition.edges,
          status ?? 'idle',
          currentStep ?? '',
          selectedNodeId
        )
      )
      setEdges(definitionToFlowEdges(definition.edges))
    } else {
      setNodes(buildNodes(status ?? 'idle', currentStep ?? '', selectedNodeId))
      setEdges(buildEdges())
    }
  }, [hasDefinition, definition?.nodes, definition?.edges, status, currentStep, selectedNodeId, setNodes, setEdges])

  const nodesRef = useRef(nodes)
  const edgesRef = useRef(edges)
  nodesRef.current = nodes
  edgesRef.current = edges

  const handleNodesChange = useCallback(
    (changes) => {
      onNodesChange(changes)
      if (editable && onDefinitionChangeRef.current && changes.some((c) => c.type === 'position'))
        setTimeout(() => {
          onDefinitionChangeRef.current?.(flowToDefinition(nodesRef.current, edgesRef.current))
        }, 0)
    },
    [onNodesChange, editable]
  )

  const handleNodeClick = useCallback(
    (_, node) => {
      onNodeClick?.(node.id)
    },
    [onNodeClick]
  )

  const handlePaneClick = useCallback(() => {
    onNodeClick?.(null)
  }, [onNodeClick])

  const handleEdgesChange = useCallback(
    (changes) => {
      onEdgesChange(changes)
      if (editable && onDefinitionChangeRef.current && changes.length)
        setTimeout(() => {
          onDefinitionChangeRef.current?.(flowToDefinition(nodesRef.current, edgesRef.current))
        }, 0)
    },
    [onEdgesChange, editable]
  )

  const handleConnect = useCallback(
    (connection) => {
      if (!editable || !hasDefinition) return
      setEdges((eds) => {
        const next = addEdge(
          {
            ...connection,
            id: `e-${connection.source}-${connection.target}-${Date.now()}`,
          },
          eds
        )
        edgesRef.current = next
        setTimeout(() => {
          onDefinitionChangeRef.current?.(flowToDefinition(nodesRef.current, next))
        }, 0)
        return next
      })
    },
    [editable, hasDefinition, setEdges]
  )

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={handleNodesChange}
      onEdgesChange={handleEdgesChange}
      onConnect={handleConnect}
      onNodeClick={handleNodeClick}
      onPaneClick={handlePaneClick}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      nodesDraggable={editable && hasDefinition}
      nodesConnectable={editable && hasDefinition}
      elementsSelectable={true}
      proOptions={{ hideAttribution: true }}
      aria-label="Pipeline flow. Click a node to configure."
    >
      <Controls showInteractive={false} />
      <Background gap={12} size={1} />
    </ReactFlow>
  )
}

export default function PipelineFlow({
  status,
  currentStep,
  selectedNodeId,
  onNodeClick,
  definition,
  onDefinitionChange,
  editable = false,
}) {
  return (
    <div className="h-[400px] w-full rounded-xl border border-border bg-muted/20">
      <PipelineFlowInner
        status={status}
        currentStep={currentStep}
        selectedNodeId={selectedNodeId}
        onNodeClick={onNodeClick}
        definition={definition}
        onDefinitionChange={onDefinitionChange}
        editable={editable}
      />
    </div>
  )
}

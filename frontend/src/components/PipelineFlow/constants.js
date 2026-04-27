/** Pipeline graph: edges (source → target) and default layout. */

import { STAGE_ORDER } from '../../constants'

/** Ordered pairs [sourceId, targetId] for the 4-stage linear pipeline. */
export const PIPELINE_EDGES = [
  ['qualtrics', 'process'],
  ['process', 'grid'],
  ['grid', 'box'],
]

/** Horizontal spacing between node centers. */
export const NODE_WIDTH = 180
export const NODE_SPACING = 220

/** Default position for each stage (left to right). */
export function getDefaultNodePositions() {
  const positions = {}
  STAGE_ORDER.forEach((id, i) => {
    positions[id] = { x: i * NODE_SPACING, y: 0 }
  })
  return positions
}

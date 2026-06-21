export interface Position {
  x: number
  y: number
  z: number
  radius: number
  angle: number
  dynastyId: number
  generation: number
}

export interface LayoutData {
  nodeIds: string[]
  positions: Position[]
}

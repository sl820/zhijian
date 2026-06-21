export type RelationKind =
  | 'parentOf'
  | 'childOf'
  | 'siblingOf'
  | 'spouseOf'
  | 'other'

export interface Relation {
  src: string
  dst: string
  rel: RelationKind
  source: 'jiapu' | 'cbdb'
  raw_label: string
}

export interface BucketMeta {
  id: number
  count: number
  bytes: number
  start_pid: string
  end_pid: string
}

export interface BucketIndex {
  version: number
  prefix: string
  buckets: BucketMeta[]
}

export interface Person {
  pid: string
  uri: string
  source: 'jiapu' | 'cbdb'
  name: string
  name_alt: string
  courtesy: string
  pseudonym: string
  gender: string
  family_name: string
  family_uri: string
  family_role: string
  dynasty: string
  temporal_raw: string
  generation: number
  order: string
  description: string
  label_type: string
}

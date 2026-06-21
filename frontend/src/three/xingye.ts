/**
 * 28 宿 + 12 州分野
 * 复用 v1 xingye.js（已删 v1 残留时备份内容）
 * 东方苍龙 7 / 北方玄武 7 / 西方白虎 7 / 南方朱雀 7
 */
export interface Mansion {
  key: string
  cn: string
  pinyin: string
  branch: 'east' | 'north' | 'west' | 'south'
  angle: number
}

export const TWENTY_EIGHT_MANSIONS: readonly Mansion[] = [
  // 东方苍龙 (角、亢、氐、房、心、尾、箕)
  { key: 'jiao',   cn: '角', pinyin: 'jiǎo',   branch: 'east',  angle: 0.000 },
  { key: 'kang',   cn: '亢', pinyin: 'kàng',   branch: 'east',  angle: 0.224 },
  { key: 'di',     cn: '氐', pinyin: 'dǐ',     branch: 'east',  angle: 0.449 },
  { key: 'fang',   cn: '房', pinyin: 'fáng',   branch: 'east',  angle: 0.673 },
  { key: 'xin',    cn: '心', pinyin: 'xīn',    branch: 'east',  angle: 0.898 },
  { key: 'wei',    cn: '尾', pinyin: 'wěi',    branch: 'east',  angle: 1.122 },
  { key: 'ji',     cn: '箕', pinyin: 'jī',     branch: 'east',  angle: 1.347 },
  // 北方玄武 (斗、牛、女、虚、危、室、壁)
  { key: 'dou',    cn: '斗', pinyin: 'dǒu',    branch: 'north', angle: 1.571 },
  { key: 'niu',    cn: '牛', pinyin: 'niú',    branch: 'north', angle: 1.795 },
  { key: 'nv',     cn: '女', pinyin: 'nǚ',     branch: 'north', angle: 2.020 },
  { key: 'xu',     cn: '虚', pinyin: 'xū',     branch: 'north', angle: 2.244 },
  { key: 'wei_b',  cn: '危', pinyin: 'wēi',    branch: 'north', angle: 2.469 },
  { key: 'shi',    cn: '室', pinyin: 'shì',    branch: 'north', angle: 2.693 },
  { key: 'bi',     cn: '壁', pinyin: 'bì',     branch: 'north', angle: 2.918 },
  // 西方白虎 (奎、娄、胃、昴、毕、觜、参)
  { key: 'kui',    cn: '奎', pinyin: 'kuí',    branch: 'west',  angle: 3.142 },
  { key: 'lou',    cn: '娄', pinyin: 'lóu',    branch: 'west',  angle: 3.367 },
  { key: 'wei_w',  cn: '胃', pinyin: 'wèi',    branch: 'west',  angle: 3.591 },
  { key: 'mao',    cn: '昴', pinyin: 'mǎo',    branch: 'west',  angle: 3.816 },
  { key: 'bi_x',   cn: '毕', pinyin: 'bì',     branch: 'west',  angle: 4.040 },
  { key: 'zui',    cn: '觜', pinyin: 'zī',     branch: 'west',  angle: 4.265 },
  { key: 'shen',   cn: '参', pinyin: 'shēn',   branch: 'west',  angle: 4.489 },
  // 南方朱雀 (井、鬼、柳、星、张、翼、轸)
  { key: 'jing',   cn: '井', pinyin: 'jǐng',   branch: 'south', angle: 4.714 },
  { key: 'gui',    cn: '鬼', pinyin: 'guǐ',    branch: 'south', angle: 4.938 },
  { key: 'liu',    cn: '柳', pinyin: 'liǔ',    branch: 'south', angle: 5.163 },
  { key: 'xing',   cn: '星', pinyin: 'xīng',   branch: 'south', angle: 5.387 },
  { key: 'zhang',  cn: '张', pinyin: 'zhāng',  branch: 'south', angle: 5.612 },
  { key: 'yi',     cn: '翼', pinyin: 'yì',     branch: 'south', angle: 5.836 },
  { key: 'zhen',   cn: '轸', pinyin: 'zhěn',   branch: 'south', angle: 6.061 },
]

export const TWELVE_STATES_FENYE: readonly string[] = [
  '角、亢', '氐', '房、心', '尾、箕', '斗', '牛、女',
  '虚、危', '室、壁', '奎、娄', '胃、昴、毕', '觜、参', '井、鬼、柳',
]

export const REGION_TO_MANSIONS: ReadonlyArray<readonly [string, readonly string[]]> = [
  ['兖州', ['房、心']],
  ['豫州', ['角、亢']],
  ['青州', ['虚、危']],
  ['徐州', ['奎、娄']],
  ['扬州', ['斗、牛、女']],
  ['荆州', ['翼、轸']],
  ['梁州', ['井、鬼、柳']],
  ['雍州', ['奎、娄']],
  ['冀州', ['昴、毕']],
  ['幽州', ['斗、牛、女']],
  ['兖州', ['角、亢']],
  ['交州', ['翼、轸']],
]

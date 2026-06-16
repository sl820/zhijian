/**
 * 志鉴·星野图考 二十八宿 / 分野数据
 *
 * Why：星野图考传统把地理对应到天文。给每节点的"地理"打上星宿标记，
 * 实现「X 地望 X 宿」的古方志语义，让 3D 图谱在视觉与文化上都有根。
 *
 * 数据来源：参考《史记·天官书》《晋书·天文志》的"十二州·二十八宿·分野"映射（公版）。
 */

export const TWENTY_EIGHT_MANSIONS = [
  // 东方青龙七宿
  { id: 'jiao', cn: '角', en: 'Horn', dir: 'east', dragon: 'azure' },
  { id: 'kang', cn: '亢', en: 'Neck', dir: 'east', dragon: 'azure' },
  { id: 'di', cn: '氐', en: 'Root', dir: 'east', dragon: 'azure' },
  { id: 'fang', cn: '房', en: 'Room', dir: 'east', dragon: 'azure' },
  { id: 'xin', cn: '心', en: 'Heart', dir: 'east', dragon: 'azure' },
  { id: 'wei', cn: '尾', en: 'Tail', dir: 'east', dragon: 'azure' },
  { id: 'ji', cn: '箕', en: 'WinnowingBasket', dir: 'east', dragon: 'azure' },
  // 北方玄武七宿
  { id: 'dou', cn: '斗', en: 'Dipper', dir: 'north', dragon: 'black' },
  { id: 'niu', cn: '牛', en: 'Ox', dir: 'north', dragon: 'black' },
  { id: 'nu', cn: '女', en: 'Girl', dir: 'north', dragon: 'black' },
  { id: 'xu', cn: '虚', en: 'Emptiness', dir: 'north', dragon: 'black' },
  { id: 'wei2', cn: '危', en: 'Rooftop', dir: 'north', dragon: 'black' },
  { id: 'shi', cn: '室', en: 'Encampment', dir: 'north', dragon: 'black' },
  { id: 'bi', cn: '壁', en: 'Wall', dir: 'north', dragon: 'black' },
  // 西方白虎七宿
  { id: 'kui', cn: '奎', en: 'Legs', dir: 'west', dragon: 'white' },
  { id: 'lou', cn: '娄', en: 'Bond', dir: 'west', dragon: 'white' },
  { id: 'wei3', cn: '胃', en: 'Stomach', dir: 'west', dragon: 'white' },
  { id: 'mao', cn: '昴', en: 'HairyHead', dir: 'west', dragon: 'white' },
  { id: 'bi2', cn: '毕', en: 'Net', dir: 'west', dragon: 'white' },
  { id: 'zi', cn: '觜', en: 'TurtleBeak', dir: 'west', dragon: 'white' },
  { id: 'shen', cn: '参', en: 'Three', dir: 'west', dragon: 'white' },
  // 南方朱雀七宿
  { id: 'jing', cn: '井', en: 'Well', dir: 'south', dragon: 'vermilion' },
  { id: 'gui', cn: '鬼', en: 'Ghost', dir: 'south', dragon: 'vermilion' },
  { id: 'liu', cn: '柳', en: 'Willow', dir: 'south', dragon: 'vermilion' },
  { id: 'xing', cn: '星', en: 'Star', dir: 'south', dragon: 'vermilion' },
  { id: 'zhang', cn: '张', en: 'ExtendedNet', dir: 'south', dragon: 'vermilion' },
  { id: 'yi', cn: '翼', en: 'Wings', dir: 'south', dragon: 'vermilion' },
  { id: 'zhen', cn: '轸', en: 'Cart', dir: 'south', dragon: 'vermilion' },
]

// 十二州分野（简版，按"秦地=井鬼 / 宋地=角亢 / ... "）
export const TWELVE_STATES_FENYE = {
  '宋': '角亢氐',
  '郑': '房心',
  '燕': '尾箕',
  '越': '斗牛女',
  '吴': '虚危',
  '齐': '室壁',
  '卫': '奎娄',
  '鲁': '胃昴',
  '赵': '毕觜参',
  '魏': '井鬼',
  '秦': '柳星张',
  '周': '翼轸',
}

// 简化映射：州名 → 主导宿（用于节点默认归属）
export const REGION_TO_MANSIONS = {
  '宋': ['jiao', 'kang', 'di'],
  '秦': ['liu', 'xing', 'zhang'],
  '齐': ['shi', 'bi'],
  '燕': ['wei', 'ji'],
  '晋': ['shi', 'bi', 'kui'],
  '赵': ['bi2', 'zi', 'shen'],
  '魏': ['jing', 'gui'],
  '楚': ['zhen', 'yi'],
  '吴': ['xu', 'wei2'],
  '越': ['dou', 'niu', 'nu'],
}

export default {
  TWENTY_EIGHT_MANSIONS,
  TWELVE_STATES_FENYE,
  REGION_TO_MANSIONS,
}
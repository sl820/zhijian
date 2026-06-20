/**
 * 志鉴·星野图考 调色板
 *
 * 设计语言：靛蓝夜底 + 朱砂节点 + 墨黑连线 + 金粉高光 + 米白星点。
 * 灵感：苏州石刻天文图（1247，北极天球立体投影）— 深空背景上散布朱砂星辰。
 *
 * Why：星野图考是志鉴产品的核心差异化（vs 通用 3D 力导向图）。
 * 所有视觉组件统一从此处取色，避免散落的 hex 字符串。
 */

export const PALETTE = {
  // 背景层（自下而上：远空 → 中层 → 近层）
  indigo: {
    deep: '#0a0e1f',
    mid: '#131b35',
    near: '#1d2747',
  },

  // 朱砂红（节点主色 + 高亮）
  vermilion: {
    deep: '#8b2818',
    main: '#c2362a',
    bright: '#e84830',
    seal: '#a82a1f',
    faint: 'rgba(168, 42, 31, 0.12)',
  },

  // 墨黑（连线 + 文字）
  ink: {
    deep: '#0d0d12',
    main: '#1a1a24',
    light: '#2a2a38',
    pale: '#5a5a6e',
  },

  // 金粉（高亮 + 重要节点描边）
  gold: {
    dim: '#a89060',
    main: '#d4b070',
    bright: '#f0d090',
    pale: '#e8d8b0',
    faint: 'rgba(168, 144, 96, 0.45)',
  },

  // 米白（星点 + 文字）
  rice: {
    dim: '#d8d4c4',
    main: '#f0e8d4',
    bright: '#faf6e8',
  },

  // 功能色（节点家族）
  family: '#5b9b9c',
  female: '#b85878',
  official: '#c9a050',
  other: '#7a8090',
}

export const CATEGORY_COLORS = {
  0: PALETTE.family,
  1: PALETTE.female,
  2: PALETTE.other,
  3: PALETTE.official,
}

export const CATEGORY_NAMES = {
  0: '姓氏族',
  1: '妻妾',
  2: '其它人物',
  3: '官吏·文人',
}

// ============================================================
// 朝代配色（11 朝独立 hue）
// 设计语言：每朝取自传统色卡，与 PALETTE 主色协调（避免高饱和）
// Why：91% 节点无 birth_year → 按 category 配色只能分 4 类；
//      但大部分 jiapu 节点都有 name 含朝代字（宋/元/明/清等）。
//      朝代配色让用户一眼看出时间分布，叠合 z 维度形成"星空图考"层次。
// ============================================================
export const DYNASTY_COLORS = {
  pre_han:    '#9b6a3f',  // 赭石（先秦青铜 · 土黄偏红）
  three_jin:  '#7a8aa8',  // 玄青（魏晋风骨 · 蓝灰冷峻）
  north_sou:  '#a06070',  // 胭脂（南北朝 · 红粉淡雅）
  sui:        '#b89060',  // 黄丹（隋 · 暖橙）
  tang:      '#c9a050',  // 赭黄（唐 · 金碧辉煌）
  five_dyn:  '#8a7060',  // 沉香（五代 · 暗褐）
  song:      '#d4b070',  // 金粉（宋 · 雅致金）
  yuan:      '#5b9b9c',  // 青瓷（元 · 草原青）
  ming:     '#c2362a',  // 朱砂（明 · 御红）
  qing:      '#6080a0',  // 灰蓝（清 · 冷调）
  modern:    '#7a8090',  // 淡墨（近代 · 灰）
}

export const DYNASTY_NAMES = {
  pre_han: '先秦',
  three_jin: '魏晋',
  north_sou: '南北朝',
  sui: '隋',
  tang: '唐',
  five_dyn: '五代',
  song: '宋',
  yuan: '元',
  ming: '明',
  qing: '清',
  modern: '近代',
}

export default PALETTE

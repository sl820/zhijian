/**
 * 志鉴·星野图考 调色板
 *
 * 设计灵感：古方志"星野图考"传统 — 靛蓝夜底 + 留白星点 + 朱砂节点 + 墨黑连线 + 金粉高光。
 *
 * Why：星野图考是志鉴产品的核心差异化（vs 通用 3D 力导向图）。
 * 所有视觉组件统一从此处取色，避免散落的 hex 字符串。
 */

export const PALETTE = {
  // 背景层（自下而上）
  indigo: {
    deep: '#0a0e1f',      // 最深底色（远空）
    mid: '#131b35',       // 中间层
    near: '#1d2747',      // 近层（星云带）
  },

  // 朱砂红（节点主色 + 高亮）
  vermilion: {
    deep: '#8b2818',      // 深朱砂（休眠节点）
    main: '#c2362a',      // 主朱砂
    bright: '#e84830',    // 亮朱砂（hover/选中）
    seal: '#a82a1f',      // 印章朱砂（边框）
  },

  // 墨黑（连线 + 文字）
  ink: {
    deep: '#0d0d12',      // 最深墨
    main: '#1a1a24',      // 主墨色（连线）
    light: '#2a2a38',     // 淡墨
    pale: '#5a5a6e',      // 远墨
  },

  // 金粉（高亮 + 重要节点描边）
  gold: {
    dim: '#a89060',       // 暗金
    main: '#d4b070',      // 主金
    bright: '#f0d090',    // 亮金（hover 光晕）
    pale: '#e8d8b0',      // 淡金（卷轴装饰）
  },

  // 米白（星点 + 文字）
  rice: {
    dim: '#d8d4c4',       // 暗米白（远星）
    main: '#f0e8d4',      // 主米白（近星）
    bright: '#faf6e8',    // 亮米白（高亮文字）
  },

  // 功能色
  family: '#5b9b9c',     // 家族蓝青
  female: '#b85878',     // 妻妾绛紫
  official: '#c9a050',   // 官吏金
  other: '#7a8090',      // 其它灰蓝
}

export const CATEGORY_COLORS = {
  0: PALETTE.family,      // 姓氏族
  1: PALETTE.female,      // 妻妾
  2: PALETTE.other,       // 其它
  3: PALETTE.official,    // 官吏/文人/武将
}

export const CATEGORY_NAMES = {
  0: '姓氏族',
  1: '妻妾',
  2: '其它人物',
  3: '官吏·文人',
}

export default PALETTE
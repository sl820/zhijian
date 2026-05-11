/**
 * ECharts Theme - 古籍书房 Digital Scriptorium
 * 与古书房美学一致的图表主题
 */

export const scriptoriumTheme = {
  // 调色板
  color: [
    '#b54a32',  // 朱砂红（主色）
    '#6b8f8a',  // 青瓷
    '#5a8a6a',  // 草绿
    '#b8863a',  // 琥珀
    '#5a7a8a',  // 蓝灰
    '#8a6b5a',  // 暖棕
    '#7a5a8a',  // 暗紫
    '#5a8a7a',  // 墨绿
  ],

  // 背景
  backgroundColor: 'transparent',

  // 文字样式
  textStyle: {
    fontFamily: "'Noto Serif SC', serif",
    color: '#4a4a4a',
    fontSize: 12,
  },

  // 标题
  title: {
    textStyle: {
      fontFamily: "'ZCOOL XiaoWei', 'Noto Serif SC', serif",
      color: '#1a1a1a',
      fontSize: 18,
      fontWeight: 600,
    },
    subtextStyle: {
      fontFamily: "'Noto Serif SC', serif",
      color: '#8a8a8a',
      fontSize: 13,
    },
  },

  // 折线图
  line: {
    itemStyle: {
      borderWidth: 2,
    },
    lineStyle: {
      width: 2.5,
    },
    symbolSize: 6,
    smooth: true,
  },

  // 柱状图
  bar: {
    itemStyle: {
      borderRadius: [4, 4, 0, 0],
    },
  },

  // 饼图
  pie: {
    itemStyle: {
      borderRadius: 4,
      borderColor: '#faf8f3',
      borderWidth: 2,
    },
  },

  // 散点图
  scatter: {
    itemStyle: {
      borderWidth: 1,
      borderColor: '#faf8f3',
    },
  },

  // 力导向图（知识图谱）
  graph: {
    lineStyle: {
      color: '#d4cbc0',
      width: 1.5,
      curveness: 0.3,
    },
    itemStyle: {
      borderWidth: 2,
      borderColor: '#faf8f3',
    },
    label: {
      fontFamily: "'Noto Serif SC', serif",
      fontSize: 12,
      color: '#1a1a1a',
    },
    emphasis: {
      lineStyle: {
        width: 2.5,
        color: '#b54a32',
      },
    },
  },

  // 坐标轴
  axis: {
    lineStyle: {
      color: '#d4cbc0',
    },
    splitLine: {
      lineStyle: {
        color: '#e5dfd4',
        type: 'dashed',
      },
    },
    axisLabel: {
      fontFamily: "'Noto Serif SC', serif",
      color: '#8a8a8a',
    },
  },

  // 类目轴
  categoryAxis: {
    axisLine: {
      lineStyle: {
        color: '#d4cbc0',
      },
    },
    axisTick: {
      lineStyle: {
        color: '#d4cbc0',
      },
    },
    axisLabel: {
      fontFamily: "'Noto Serif SC', serif",
      color: '#8a8a8a',
    },
    splitLine: {
      show: false,
    },
  },

  // 数值轴
  valueAxis: {
    axisLine: {
      show: false,
    },
    splitLine: {
      lineStyle: {
        color: '#e5dfd4',
        type: 'dashed',
      },
    },
  },

  // 提示框
  tooltip: {
    backgroundColor: 'rgba(250, 248, 243, 0.95)',
    borderColor: '#d4cbc0',
    borderWidth: 1,
    borderRadius: 6,
    textStyle: {
      fontFamily: "'Noto Serif SC', serif",
      color: '#1a1a1a',
    },
    extraCssText: 'box-shadow: 0 4px 12px rgba(30, 25, 20, 0.1);',
  },

  // 图例
  legend: {
    textStyle: {
      fontFamily: "'Noto Serif SC', serif",
      color: '#4a4a4a',
    },
  },

  // 数据区域缩放
  dataZoom: {
    backgroundColor: 'var(--bg-secondary)',
    borderColor: 'var(--border-light)',
    fillerColor: 'rgba(181, 74, 50, 0.1)',
    handleColor: '#b54a32',
    handleStyle: {
      borderColor: '#b54a32',
    },
  },

  // 时间线
  timeline: {
    lineStyle: {
      color: '#d4cbc0',
    },
    itemStyle: {
      color: '#b54a32',
    },
    controlStyle: {
      color: '#b54a32',
      borderColor: '#b54a32',
    },
    label: {
      color: '#8a8a8a',
    },
  },

  // 视觉映射
  visualMap: {
    textStyle: {
      fontFamily: "'Noto Serif SC', serif",
      color: '#8a8a8a',
    },
  },

  // 全局强调
  emphasis: {
    scale: true,
    scaleSize: 5,
  },
}

export default scriptoriumTheme

/**
 * 字体配置
 *
 * Why：星野图考需要古风字体支撑视觉气质。霞鹜文楷（LXGW WenKai）开源自用，
 * 适合中文古籍风格；思源宋体用作 fallback；系统字体兜底。
 *
 * How to apply：
 * - 节点名称 / 朝代标签用 serif-font（霞鹜文楷优先）
 * - 卷轴装饰文字 / Tooltip 用 display-font（霞鹜文楷 TC）
 * - 数字 / 英文用 mono-font
 */

export const FONTS = {
  // 古风标题（节点标签、卷轴装饰）
  display: '"LXGW WenKai TC", "LXGW WenKai", "霞鹜文楷", "STKaiti", "KaiTi", serif',

  // 正文（朱砂印章、Tooltip 文本）
  serif: '"Source Han Serif SC", "Noto Serif SC", "Songti SC", "STSong", "SimSun", serif',

  // UI（按钮、菜单、表单）
  sans: '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',

  // 数字（坐标、年份）
  mono: '"JetBrains Mono", "SF Mono", "Fira Code", monospace',
}

// 霞鹜文楷 CDN URL（unpkg 静态资源；离线部署需自托管）
export const FONT_CDN = {
  wenkai_tc: 'https://chinese-fonts-cdn.deno.dev/packages/lxgwwenkai/dist/LXGWWenKaiTC-Regular/result.css',
  wenkai_screen: 'https://chinese-fonts-cdn.deno.dev/packages/lxgwwenkai/dist/LXGWWenKaiScreen/result.css',
}

export default FONTS
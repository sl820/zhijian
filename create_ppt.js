const pptxgen = require("pptxgenjs");

let pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "志鉴开发团队";
pres.title = "古籍方志智能化整理平台";

// Color palette
const COLORS = {
  navy: "1E3A5F",
  darkNavy: "15294D",
  lightBg: "F5F7FA",
  white: "FFFFFF",
  red: "C41E3A",
  darkText: "1A1A2E",
  grayText: "5D6D7E",
  blueAccent: "2980B9",
  lightGray: "ECF0F1",
  mediumGray: "BDC3C7",
  green: "27AE60",
  orange: "E67E22",
  teal: "16A085",
};

// Helper: create shadow
const mkShadow = () => ({ type: "outer", color: "000000", blur: 4, offset: 2, angle: 135, opacity: 0.1 });

// Helper: add slide number
function addSlideNumber(slide, num) {
  slide.addText(String(num), {
    x: 9.5, y: 5.3, w: 0.4, h: 0.25,
    fontSize: 10, color: COLORS.grayText, align: "right",
  });
}

// Helper: add bottom accent bar
function addBottomBar(slide) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 5.45, w: 10, h: 0.175,
    fill: { color: COLORS.red },
    line: { color: COLORS.red },
  });
}

// ==============================================================
// SLIDE 1: Cover
// ==============================================================
let slide1 = pres.addSlide();
slide1.background = { color: COLORS.navy };

// Decorative shape top
slide1.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 0, w: 10, h: 0.08,
  fill: { color: COLORS.red },
  line: { color: COLORS.red },
});

// Main title
slide1.addText("古籍方志智能化整理平台", {
  x: 0.5, y: 1.8, w: 9, h: 1.0,
  fontSize: 44, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.white, align: "center",
});

// Subtitle
slide1.addText("志鉴  ZhiJian", {
  x: 0.5, y: 2.85, w: 9, h: 0.6,
  fontSize: 28, fontFace: "Georgia", italic: true,
  color: COLORS.red, align: "center",
});

// Tagline
slide1.addText("2026中国大学生计算机设计大赛参赛作品", {
  x: 0.5, y: 3.6, w: 9, h: 0.5,
  fontSize: 18, fontFace: "Microsoft YaHei",
  color: COLORS.mediumGray, align: "center",
});

// Bottom info
slide1.addText([
  { text: "团队：志鉴开发团队", options: { breakLine: true } },
  { text: "2026年4月", options: {} },
], {
  x: 0.5, y: 4.6, w: 9, h: 0.7,
  fontSize: 14, fontFace: "Microsoft YaHei",
  color: COLORS.mediumGray, align: "center",
});

// ==============================================================
// SLIDE 2: Background & Pain Points
// ==============================================================
let slide2 = pres.addSlide();
slide2.background = { color: COLORS.lightBg };

slide2.addText("古籍数字化的四大核心痛点", {
  x: 0.5, y: 0.3, w: 9, h: 0.7,
  fontSize: 32, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

const painPoints = [
  { num: "01", title: "版本歧异无从比对", desc: "同一古籍存在多个版本，字词差异靠人工逐字比对，效率极低" },
  { num: "02", title: "避讳字、异体字阻碍理解", desc: "康熙「玄」改「元」，乾隆「弘」改「宏」，机器无法理解是同一字" },
  { num: "03", title: "知识碎片化，缺乏关联", desc: "人名地名散落各处，无法回答「张巡的籍贯在哪里？」" },
  { num: "04", title: "舆图要素难以数字化", desc: "古籍舆图为灰度图像，山河城池无法批量处理" },
];

painPoints.forEach((p, i) => {
  const y = 1.15 + i * 1.05;
  // Card background
  slide2.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y, w: 9, h: 0.95,
    fill: { color: COLORS.white },
    shadow: mkShadow(),
    line: { color: COLORS.white },
  });
  // Number badge
  slide2.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y, w: 0.75, h: 0.95,
    fill: { color: COLORS.red },
    line: { color: COLORS.red },
  });
  slide2.addText(p.num, {
    x: 0.5, y, w: 0.75, h: 0.95,
    fontSize: 20, fontFace: "Arial", bold: true,
    color: COLORS.white, align: "center", valign: "middle",
  });
  // Title
  slide2.addText(p.title, {
    x: 1.4, y: y + 0.1, w: 7.8, h: 0.38,
    fontSize: 16, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.darkText, margin: 0,
  });
  // Description
  slide2.addText(p.desc, {
    x: 1.4, y: y + 0.5, w: 7.8, h: 0.38,
    fontSize: 13, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, margin: 0,
  });
});

addBottomBar(slide2);
addSlideNumber(slide2, 2);

// ==============================================================
// SLIDE 3: System Overview - 7 Modules
// ==============================================================
let slide3 = pres.addSlide();
slide3.background = { color: COLORS.lightBg };

slide3.addText("志鉴系统七大功能模块", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 30, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

const modules = [
  { num: "01", title: "OCR古籍识别", desc: "PaddleOCR双引擎\n+ 避讳字还原", color: "3498DB" },
  { num: "02", title: "异体字规范化", desc: "繁简/古今字\n三级转换", color: "9B59B6" },
  { num: "03", title: "多版本校勘", desc: "Needleman-Wunsch\n语义对齐", color: "E74C3C" },
  { num: "04", title: "知识图谱构建", desc: "Neo4j + Milvus\n+ LLM辅助", color: "27AE60" },
  { num: "05", title: "RAG智能问答", desc: "混合检索\n+ 本地LLM生成", color: "F39C12" },
  { num: "06", title: "舆图要素分割", desc: "U-Net语义分割\n识别6类要素", color: "1ABC9C" },
  { num: "07", title: "标点与编纂", desc: "智能断句\n+ 多源融合", color: "E67E22" },
];

// 7-card layout: top 4, bottom 3
const topRow = modules.slice(0, 4);
const bottomRow = modules.slice(4);

topRow.forEach((m, i) => {
  const x = 0.4 + i * 2.4;
  slide3.addShape(pres.shapes.RECTANGLE, {
    x, y: 1.0, w: 2.2, h: 1.75,
    fill: { color: COLORS.white },
    shadow: mkShadow(),
    line: { color: COLORS.white },
  });
  slide3.addShape(pres.shapes.RECTANGLE, {
    x, y: 1.0, w: 2.2, h: 0.08,
    fill: { color: m.color },
    line: { color: m.color },
  });
  slide3.addText(m.num, {
    x, y: 1.15, w: 2.2, h: 0.35,
    fontSize: 22, fontFace: "Arial", bold: true,
    color: m.color, align: "center", margin: 0,
  });
  slide3.addText(m.title, {
    x, y: 1.52, w: 2.2, h: 0.38,
    fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.darkText, align: "center", margin: 0,
  });
  slide3.addText(m.desc, {
    x: x + 0.1, y: 1.95, w: 2.0, h: 0.7,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, align: "center", margin: 0,
  });
});

bottomRow.forEach((m, i) => {
  const x = 1.55 + i * 2.4;
  slide3.addShape(pres.shapes.RECTANGLE, {
    x, y: 3.0, w: 2.2, h: 1.55,
    fill: { color: COLORS.white },
    shadow: mkShadow(),
    line: { color: COLORS.white },
  });
  slide3.addShape(pres.shapes.RECTANGLE, {
    x, y: 3.0, w: 2.2, h: 0.08,
    fill: { color: m.color },
    line: { color: m.color },
  });
  slide3.addText(m.num, {
    x, y: 3.15, w: 2.2, h: 0.32,
    fontSize: 22, fontFace: "Arial", bold: true,
    color: m.color, align: "center", margin: 0,
  });
  slide3.addText(m.title, {
    x, y: 3.5, w: 2.2, h: 0.35,
    fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.darkText, align: "center", margin: 0,
  });
  slide3.addText(m.desc, {
    x: x + 0.1, y: 3.88, w: 2.0, h: 0.6,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, align: "center", margin: 0,
  });
});

// Bottom note
slide3.addShape(pres.shapes.RECTANGLE, {
  x: 0.4, y: 4.75, w: 9.2, h: 0.55,
  fill: { color: COLORS.navy },
  line: { color: COLORS.navy },
});
slide3.addText("核心AI能力：全部本地LLM驱动（Qwen2.5-3B + Gemma4），无需商业API", {
  x: 0.5, y: 4.8, w: 9, h: 0.45,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.white, align: "center", valign: "middle",
});

addSlideNumber(slide3, 3);

// ==============================================================
// SLIDE 4: OCR Recognition
// ==============================================================
let slide4 = pres.addSlide();
slide4.background = { color: COLORS.lightBg };

slide4.addText("功能一：古籍OCR识别", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 30, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Pipeline flow
const pipelineSteps = [
  "上传古籍图片/PDF",
  "预处理\n倾斜校正/灰度增强",
  "双引擎并行识别\nPaddleOCR + EasyOCR",
  "择优录取",
  "避讳字还原",
  "异体字标准化",
  "输出标准化文本",
];

pipelineSteps.forEach((step, i) => {
  const x = 0.35 + i * 1.38;
  slide4.addShape(pres.shapes.RECTANGLE, {
    x, y: 1.0, w: 1.2, h: 0.9,
    fill: { color: i === 0 || i === 6 ? COLORS.navy : (i === 4 || i === 5 ? COLORS.red : COLORS.blueAccent) },
    line: { color: i === 0 || i === 6 ? COLORS.navy : (i === 4 || i === 5 ? COLORS.red : COLORS.blueAccent) },
  });
  slide4.addText(step, {
    x, y: 1.0, w: 1.2, h: 0.9,
    fontSize: 10, fontFace: "Microsoft YaHei",
    color: COLORS.white, align: "center", valign: "middle",
  });
  if (i < pipelineSteps.length - 1) {
    slide4.addText("\u2192", {
      x: x + 1.15, y: 1.25, w: 0.25, h: 0.4,
      fontSize: 18, color: COLORS.grayText, align: "center", valign: "middle",
    });
  }
});

// Taboo table
slide4.addText("避讳字自动还原示例", {
  x: 0.5, y: 2.1, w: 4.3, h: 0.4,
  fontSize: 16, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const tabooData = [
  [{ text: "识别结果", options: { bold: true, fill: { color: COLORS.navy }, color: COLORS.white } },
   { text: "朝代判断", options: { bold: true, fill: { color: COLORS.navy }, color: COLORS.white } },
   { text: "还原后", options: { bold: true, fill: { color: COLORS.navy }, color: COLORS.white } }],
  ["元年", "康熙朝", "玄年"],
  ["张宏", "乾隆朝", "张弘"],
  ["引", "雍正朝", "胤"],
];

slide4.addTable(tabooData, {
  x: 0.5, y: 2.55, w: 4.3, h: 1.3,
  colW: [1.4, 1.45, 1.45],
  fontSize: 13, fontFace: "Microsoft YaHei",
  color: COLORS.darkText,
  border: { pt: 0.5, color: COLORS.mediumGray },
  align: "center", valign: "middle",
});

// Supported formats box
slide4.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 2.1, w: 4.4, h: 2.2,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide4.addText("支持格式与能力", {
  x: 5.3, y: 2.25, w: 4.0, h: 0.4,
  fontSize: 15, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const formatItems = [
  "JPG / PNG / PDF / TIFF",
  "批处理：PDF多页自动批量识别",
  "PaddleOCR + EasyOCR 双引擎并行",
  "2000+ 避讳字规则库",
  "康熙 / 雍正 / 乾隆朝代全覆盖",
];
slide4.addText(
  formatItems.map((item, i) => ({
    text: item,
    options: { bullet: true, breakLine: i < formatItems.length - 1 },
  })),
  { x: 5.3, y: 2.7, w: 4.0, h: 1.5, fontSize: 13, fontFace: "Microsoft YaHei", color: COLORS.grayText }
);

addBottomBar(slide4);
addSlideNumber(slide4, 4);

// ==============================================================
// SLIDE 5: Text Normalization
// ==============================================================
let slide5 = pres.addSlide();
slide5.background = { color: COLORS.lightBg };

slide5.addText("功能一（续）：三级异体字规范化体系", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 28, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Three levels
const levels = [
  {
    level: "第一级",
    title: "繁简转换",
    desc: "OpenCC 0.1.7",
    detail: "支持：简/繁/台繁/港繁",
    color: "3498DB",
  },
  {
    level: "第二级",
    title: "异体字标准化",
    desc: "2000+ 映射对",
    detail: "吳/呉/吴 \u2192 吴\n跡/蹟 \u2192 迹\n並/竝 \u2192 并",
    color: "9B59B6",
  },
  {
    level: "第三级",
    title: "古今字转换",
    desc: "《汉语大字典》对应表",
    detail: "說\u2192说，適\u2192适\n複\u2192复",
    color: "E74C3C",
  },
];

levels.forEach((l, i) => {
  const x = 0.4 + i * 3.1;
  slide5.addShape(pres.shapes.RECTANGLE, {
    x, y: 0.95, w: 2.95, h: 2.1,
    fill: { color: COLORS.white },
    shadow: mkShadow(),
    line: { color: COLORS.white },
  });
  // Left accent
  slide5.addShape(pres.shapes.RECTANGLE, {
    x, y: 0.95, w: 0.08, h: 2.1,
    fill: { color: l.color },
    line: { color: l.color },
  });
  slide5.addText(l.level, {
    x: x + 0.15, y: 1.05, w: 2.7, h: 0.32,
    fontSize: 12, fontFace: "Microsoft YaHei", bold: true,
    color: l.color, margin: 0,
  });
  slide5.addText(l.title, {
    x: x + 0.15, y: 1.4, w: 2.7, h: 0.38,
    fontSize: 16, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.darkText, margin: 0,
  });
  slide5.addText(l.desc, {
    x: x + 0.15, y: 1.82, w: 2.7, h: 0.3,
    fontSize: 12, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, margin: 0,
  });
  slide5.addText(l.detail, {
    x: x + 0.15, y: 2.18, w: 2.7, h: 0.8,
    fontSize: 12, fontFace: "Microsoft YaHei",
    color: COLORS.darkText, margin: 0,
  });
});

// NER section
slide5.addShape(pres.shapes.RECTANGLE, {
  x: 0.4, y: 3.2, w: 9.2, h: 2.1,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide5.addText("BERT NER 实体识别（5类实体）", {
  x: 0.6, y: 3.35, w: 8.8, h: 0.4,
  fontSize: 15, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

// NER example
slide5.addShape(pres.shapes.RECTANGLE, {
  x: 0.6, y: 3.8, w: 4.2, h: 0.55,
  fill: { color: "EBF5FB" },
  line: { color: "D6EAF8" },
});
slide5.addText("输入：张巡，邓州南阳人，天宝十五年见帝于灵武", {
  x: 0.7, y: 3.85, w: 4.0, h: 0.45,
  fontSize: 11, fontFace: "Microsoft YaHei",
  color: COLORS.darkText, valign: "middle",
});

slide5.addShape(pres.shapes.RECTANGLE, {
  x: 0.6, y: 4.45, w: 4.2, h: 0.7,
  fill: { color: "E8F8F5" },
  line: { color: "D5F5E3" },
});
slide5.addText("输出：", {
  x: 0.7, y: 4.5, w: 0.6, h: 0.3,
  fontSize: 11, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText,
});
const nerTags = [
  { label: "PER", val: "张巡", color: "E74C3C" },
  { label: "LOC", val: "邓州南阳", color: "27AE60" },
  { label: "TIME", val: "天宝十五年", color: "3498DB" },
  { label: "LOC", val: "灵武", color: "27AE60" },
];
let nerX = 0.7;
nerTags.forEach((t) => {
  slide5.addShape(pres.shapes.RECTANGLE, {
    x: nerX, y: 4.78, w: 0.85, h: 0.28,
    fill: { color: t.color },
    line: { color: t.color },
  });
  slide5.addText(t.label + ":" + t.val, {
    x: nerX, y: 4.78, w: 0.85, h: 0.28,
    fontSize: 9, fontFace: "Arial", bold: true,
    color: COLORS.white, align: "center", valign: "middle",
  });
  nerX += 0.95;
});

// NER labels
slide5.addText("NER标签体系", {
  x: 5.0, y: 3.8, w: 4.4, h: 0.35,
  fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
const nerLabels = "B-PER / I-PER \u00b7 B-LOC / I-LOC \u00b7 B-TIME / I-TIME\nB-ORG / I-ORG \u00b7 B-WORK / I-WORK";
slide5.addText(nerLabels, {
  x: 5.0, y: 4.2, w: 4.4, h: 0.9,
  fontSize: 12, fontFace: "Microsoft YaHei",
  color: COLORS.grayText, margin: 0,
});

addBottomBar(slide5);
addSlideNumber(slide5, 5);

// ==============================================================
// SLIDE 6: Multi-Version Collation
// ==============================================================
let slide6 = pres.addSlide();
slide6.background = { color: COLORS.lightBg };

slide6.addText("功能二：多版本自动校勘", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 30, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Pipeline
const collSteps = [
  "导入版本A/B\n旧刻本",
  "分章/节/句",
  "BERT [CLS]\n语义编码",
  "Needleman-Wunsch\n全局对齐",
  "差异检测\n与分类",
  "多规则\n差异判决",
  "双栏对照\n结果展示",
];

collSteps.forEach((step, i) => {
  const x = 0.3 + i * 1.38;
  const isKey = (i === 3 || i === 5);
  slide6.addShape(pres.shapes.RECTANGLE, {
    x, y: 0.95, w: 1.2, h: 0.9,
    fill: { color: isKey ? COLORS.red : COLORS.blueAccent },
    line: { color: isKey ? COLORS.red : COLORS.blueAccent },
  });
  slide6.addText(step, {
    x, y: 0.95, w: 1.2, h: 0.9,
    fontSize: 10, fontFace: "Microsoft YaHei",
    color: COLORS.white, align: "center", valign: "middle",
  });
  if (i < collSteps.length - 1) {
    slide6.addText("\u2192", {
      x: x + 1.15, y: 1.2, w: 0.25, h: 0.4,
      fontSize: 18, color: COLORS.grayText, align: "center", valign: "middle",
    });
  }
});

// Algorithm params box
slide6.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 2.05, w: 4.3, h: 1.65,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide6.addText("Needleman-Wunsch 算法参数", {
  x: 0.65, y: 2.15, w: 4.0, h: 0.38,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const algoParams = [
  ["匹配奖励", "+1.0"],
  ["错配惩罚", "-0.5"],
  ["空位惩罚", "-0.5"],
  ["向量相似度阈值", "0.85"],
];
algoParams.forEach((p, i) => {
  const y = 2.6 + i * 0.26;
  slide6.addText(p[0] + "：", {
    x: 0.7, y, w: 2.0, h: 0.25,
    fontSize: 12, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, margin: 0,
  });
  slide6.addText(p[1], {
    x: 2.7, y, w: 1.8, h: 0.25,
    fontSize: 12, fontFace: "Arial", bold: true,
    color: COLORS.navy, margin: 0,
  });
});

// Difference types
slide6.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 2.05, w: 4.4, h: 1.65,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide6.addText("差异类型（6类自动标注）", {
  x: 5.25, y: 2.15, w: 4.1, h: 0.38,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const diffTypes = ["INSERTION 插入", "DELETION 删除", "SUBSTITUTION 替换",
  "VARIANT 异体字", "TABOO 避讳字", "TRANSPOSITION 字序颠倒"];
const diffColors = ["3498DB", "9B59B6", "E74C3C", "27AE60", "F39C12", "1ABC9C"];
diffTypes.forEach((d, i) => {
  const col = i % 2;
  const row = Math.floor(i / 2);
  const x = 5.25 + col * 2.05;
  const y = 2.6 + row * 0.38;
  slide6.addShape(pres.shapes.RECTANGLE, {
    x, y: y, w: 0.12, h: 0.25,
    fill: { color: diffColors[i] },
    line: { color: diffColors[i] },
  });
  slide6.addText(d, {
    x: x + 0.18, y, w: 1.85, h: 0.25,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.darkText, margin: 0,
  });
});

// Two version comparison visualization
slide6.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 3.9, w: 4.3, h: 1.4,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide6.addText("双版本对照示例", {
  x: 0.65, y: 4.0, w: 4.0, h: 0.35,
  fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
slide6.addShape(pres.shapes.RECTANGLE, {
  x: 0.65, y: 4.4, w: 1.9, h: 0.75,
  fill: { color: "FEF9E7" },
  line: { color: "F9E79F" },
});
slide6.addText("版本A\n康熙 元年", {
  x: 0.7, y: 4.45, w: 1.8, h: 0.65,
  fontSize: 12, fontFace: "Microsoft YaHei",
  color: COLORS.darkText, align: "center", valign: "middle",
});
slide6.addShape(pres.shapes.RECTANGLE, {
  x: 2.65, y: 4.4, w: 1.9, h: 0.75,
  fill: { color: "E8F8F5" },
  line: { color: "A3E4D7" },
});
slide6.addText("版本B\n康熙元年", {
  x: 2.7, y: 4.45, w: 1.8, h: 0.65,
  fontSize: 12, fontFace: "Microsoft YaHei",
  color: COLORS.darkText, align: "center", valign: "middle",
});
slide6.addText("\u2192 空格为雕版误差，版本B更优", {
  x: 0.65, y: 5.18, w: 3.9, h: 0.22,
  fontSize: 10, fontFace: "Microsoft YaHei",
  color: COLORS.grayText, margin: 0,
});

// Interface features
slide6.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 3.9, w: 4.4, h: 1.4,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide6.addText("双栏对照界面功能", {
  x: 5.25, y: 4.0, w: 4.1, h: 0.35,
  fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
const uiFeatures = ["差异位置红色高亮", "悬停显示判决理由", "一键采纳版本", "人工修正支持"];
slide6.addText(
  uiFeatures.map((f, i) => ({ text: f, options: { bullet: true, breakLine: i < uiFeatures.length - 1 } })),
  { x: 5.25, y: 4.4, w: 4.1, h: 0.9, fontSize: 12, fontFace: "Microsoft YaHei", color: COLORS.grayText }
);

addBottomBar(slide6);
addSlideNumber(slide6, 6);

// ==============================================================
// SLIDE 7: Collation Judgment Engine
// ==============================================================
let slide7 = pres.addSlide();
slide7.background = { color: COLORS.lightBg };

slide7.addText("功能二（续）：差异判决引擎", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 28, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Priority table
slide7.addText("判决优先级", {
  x: 0.5, y: 0.95, w: 4.3, h: 0.38,
  fontSize: 16, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const priorityData = [
  [{ text: "优先级", options: { bold: true, fill: { color: COLORS.navy }, color: COLORS.white } },
   { text: "规则", options: { bold: true, fill: { color: COLORS.navy }, color: COLORS.white } },
   { text: "得分", options: { bold: true, fill: { color: COLORS.navy }, color: COLORS.white } }],
  [{ text: "1", options: { bold: true } }, "避讳字规则", { text: "0.9", options: { bold: true, color: COLORS.red } }],
  [{ text: "2", options: { bold: true } }, "时间优先（取更早版本）", { text: "0.75", options: { bold: true, color: COLORS.red } }],
  [{ text: "3", options: { bold: true } }, "字形相似度（编辑距离）", { text: "0.3", options: {} }],
  [{ text: "4", options: { bold: true } }, "上下文语义（BERT余弦）", "加权"],
];

slide7.addTable(priorityData, {
  x: 0.5, y: 1.38, w: 4.3, h: 1.65,
  colW: [0.8, 2.4, 1.1],
  fontSize: 12, fontFace: "Microsoft YaHei",
  color: COLORS.darkText,
  border: { pt: 0.5, color: COLORS.mediumGray },
  align: "center", valign: "middle",
});

// Two examples
slide7.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 0.95, w: 4.4, h: 2.08,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide7.addText("判决示例", {
  x: 5.25, y: 1.05, w: 4.1, h: 0.35,
  fontSize: 15, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

// Example 1
slide7.addShape(pres.shapes.RECTANGLE, {
  x: 5.25, y: 1.45, w: 4.1, h: 0.72,
  fill: { color: "FEF9E7" },
  line: { color: "F9E79F" },
});
slide7.addText("例1", {
  x: 5.3, y: 1.48, w: 0.4, h: 0.22,
  fontSize: 9, fontFace: "Arial", bold: true,
  color: COLORS.orange, margin: 0,
});
slide7.addText("「康熙 元年」 vs 「康熙元年」", {
  x: 5.3, y: 1.68, w: 3.9, h: 0.2,
  fontSize: 11, fontFace: "Microsoft YaHei",
  color: COLORS.darkText, margin: 0,
});
slide7.addText("INSERTION \u2192 字形相似 \u2192 版本B更优", {
  x: 5.3, y: 1.88, w: 3.9, h: 0.22,
  fontSize: 10, fontFace: "Microsoft YaHei",
  color: COLORS.grayText, margin: 0,
});

// Example 2
slide7.addShape(pres.shapes.RECTANGLE, {
  x: 5.25, y: 2.22, w: 4.1, h: 0.72,
  fill: { color: "E8F8F5" },
  line: { color: "A3E4D7" },
});
slide7.addText("例2", {
  x: 5.3, y: 2.25, w: 0.4, h: 0.22,
  fontSize: 9, fontFace: "Arial", bold: true,
  color: COLORS.green, margin: 0,
});
slide7.addText("「张宏任县令」 vs 「张弘任县令」", {
  x: 5.3, y: 2.45, w: 3.9, h: 0.2,
  fontSize: 11, fontFace: "Microsoft YaHei",
  color: COLORS.darkText, margin: 0,
});
slide7.addText("SUBSTITUTION \u2192 乾隆避讳 \u2192 版本A更优", {
  x: 5.3, y: 2.65, w: 3.9, h: 0.22,
  fontSize: 10, fontFace: "Microsoft YaHei",
  color: COLORS.grayText, margin: 0,
});

// Judgment flow
slide7.addText("判决流程（伪代码）", {
  x: 0.5, y: 3.2, w: 9, h: 0.38,
  fontSize: 15, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

slide7.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 3.62, w: 9.0, h: 1.7,
  fill: { color: "1E3A5F" },
  line: { color: "1E3A5F" },
});

const pseudoCode = "for each 差异 in 差异列表:\n    if 差异类型 == TABOO:\n        score = 0.9 x taboo_confidence\n    elif 差异.朝代匹配():\n        score = 0.75 x chronology_weight\n    else:\n        score = 0.3 x 字形相似度(差异.字A, 差异.字B)\n                + BERT上下文相似度(前后各5字窗口)\n    差异.判决结果 = argmax(scores)";

slide7.addText(pseudoCode, {
  x: 0.7, y: 3.72, w: 8.6, h: 1.5,
  fontSize: 11, fontFace: "Consolas",
  color: "A9DFBF", margin: 0,
});

addBottomBar(slide7);
addSlideNumber(slide7, 7);

// ==============================================================
// SLIDE 8: Knowledge Graph Construction
// ==============================================================
let slide8 = pres.addSlide();
slide8.background = { color: COLORS.lightBg };

slide8.addText("功能三：知识图谱构建", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 30, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Pipeline
const kgSteps = [
  "输入古籍文本",
  "NER实体识别\n(BERT)",
  "关系抽取\n正则+LLM双轨",
  "实体消解\n(Union-Find)",
  "Neo4j存储",
  "ECharts\n可视化",
];
kgSteps.forEach((step, i) => {
  const x = 0.3 + i * 1.6;
  const isLLM = i === 2;
  slide8.addShape(pres.shapes.RECTANGLE, {
    x, y: 0.95, w: 1.4, h: 0.85,
    fill: { color: isLLM ? COLORS.red : COLORS.blueAccent },
    line: { color: isLLM ? COLORS.red : COLORS.blueAccent },
  });
  slide8.addText(step, {
    x, y: 0.95, w: 1.4, h: 0.85,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.white, align: "center", valign: "middle",
  });
  if (i < kgSteps.length - 1) {
    slide8.addText("\u2192", {
      x: x + 1.35, y: 1.2, w: 0.25, h: 0.35,
      fontSize: 16, color: COLORS.grayText, align: "center", valign: "middle",
    });
  }
});

// NER + Relations
slide8.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 1.95, w: 4.3, h: 2.0,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide8.addText("NER 5类实体类型", {
  x: 0.65, y: 2.08, w: 4.0, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
const nerTypes = ["PER 人物", "LOC 地名", "TIME 时间", "ORG 机构", "WORK 作品"];
nerTypes.forEach((n, i) => {
  const col = i % 3;
  const row = Math.floor(i / 3);
  slide8.addShape(pres.shapes.RECTANGLE, {
    x: 0.65 + col * 1.35, y: 2.5 + row * 0.55, w: 1.25, h: 0.4,
    fill: { color: COLORS.blueAccent },
    line: { color: COLORS.blueAccent },
  });
  slide8.addText(n, {
    x: 0.65 + col * 1.35, y: 2.5 + row * 0.55, w: 1.25, h: 0.4,
    fontSize: 11, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.white, align: "center", valign: "middle",
  });
});

slide8.addText("关系类型（15+种）", {
  x: 0.65, y: 3.45, w: 4.0, h: 0.3,
  fontSize: 12, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
slide8.addText("FATHER / MOTHER / SON / DAUGHTER / WIFE / HUSBAND\nELDER_BROTHER / YOUNGER_BROTHER / OFFICIAL\nSTUDENT_OF / NATIVE_OF / COURTESY_NAME / ...", {
  x: 0.65, y: 3.75, w: 4.0, h: 0.5,
  fontSize: 10, fontFace: "Consolas",
  color: COLORS.grayText, margin: 0,
});

// Extraction example
slide8.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 1.95, w: 4.4, h: 2.0,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide8.addText("抽取示例", {
  x: 5.25, y: 2.08, w: 4.1, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
slide8.addShape(pres.shapes.RECTANGLE, {
  x: 5.25, y: 2.48, w: 4.1, h: 0.5,
  fill: { color: "EBF5FB" },
  line: { color: "D6EAF8" },
});
slide8.addText("原文：张巡，邓州南阳人，睢阳之战守将，事巡守城十月", {
  x: 5.35, y: 2.53, w: 3.9, h: 0.4,
  fontSize: 11, fontFace: "Microsoft YaHei",
  color: COLORS.darkText, valign: "middle",
});
slide8.addShape(pres.shapes.RECTANGLE, {
  x: 5.25, y: 3.05, w: 4.1, h: 0.8,
  fill: { color: "E8F8F5" },
  line: { color: "D5F5E3" },
});
slide8.addText("抽取结果：\n\u2022 张巡 - PER\n\u2022 邓州南阳 - LOC\n\u2022 睢阳之战 - EVENT\n\u2022 守将 - OFFICIAL", {
  x: 5.35, y: 3.1, w: 3.9, h: 0.7,
  fontSize: 11, fontFace: "Microsoft YaHei",
  color: COLORS.darkText,
});

// KG stats
slide8.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 4.15, w: 9.0, h: 1.1,
  fill: { color: COLORS.navy },
  line: { color: COLORS.navy },
});
const kgStats = [
  { val: "1,247", label: "人物节点" },
  { val: "3,582", label: "关系边" },
  { val: "2.87", label: "平均度" },
  { val: "15+", label: "关系类型" },
];
kgStats.forEach((s, i) => {
  const x = 0.7 + i * 2.2;
  slide8.addText(s.val, {
    x, y: 4.22, w: 2.0, h: 0.5,
    fontSize: 28, fontFace: "Arial", bold: true,
    color: COLORS.red, align: "center", margin: 0,
  });
  slide8.addText(s.label, {
    x, y: 4.72, w: 2.0, h: 0.35,
    fontSize: 12, fontFace: "Microsoft YaHei",
    color: COLORS.white, align: "center", margin: 0,
  });
});

addBottomBar(slide8);
addSlideNumber(slide8, 8);

// ==============================================================
// SLIDE 9: KG Query & Visualization
// ==============================================================
let slide9 = pres.addSlide();
slide9.background = { color: COLORS.lightBg };

slide9.addText("功能三（续）：图谱查询与可视化", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 28, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Node types
slide9.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 0.95, w: 4.3, h: 1.2,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide9.addText("节点类型", {
  x: 0.65, y: 1.05, w: 4.0, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
const nodeTypes = [
  { label: "人物", color: "3498DB" },
  { label: "地名", color: "27AE60" },
  { label: "方志", color: "9B59B6" },
];
nodeTypes.forEach((n, i) => {
  slide9.addShape(pres.shapes.OVAL, {
    x: 0.65 + i * 1.4, y: 1.52, w: 0.3, h: 0.3,
    fill: { color: n.color },
    line: { color: n.color },
  });
  slide9.addText(n.label, {
    x: 1.0 + i * 1.4, y: 1.52, w: 0.9, h: 0.3,
    fontSize: 12, fontFace: "Microsoft YaHei",
    color: COLORS.darkText, valign: "middle", margin: 0,
  });
});

// Interactions
slide9.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 0.95, w: 4.4, h: 1.2,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide9.addText("交互操作", {
  x: 5.25, y: 1.05, w: 4.1, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
const interactions = ["悬停显示详情", "点击展开关系", "边类型筛选", "拖拽调整布局", "缩放平移"];
slide9.addText(
  interactions.map((it, i) => ({ text: it, options: { bullet: true, breakLine: i < interactions.length - 1 } })),
  { x: 5.25, y: 1.45, w: 4.1, h: 0.65, fontSize: 12, fontFace: "Microsoft YaHei", color: COLORS.grayText }
);

// Cypher queries
slide9.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 2.3, w: 9.0, h: 2.0,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide9.addText("典型 Cypher 查询示例", {
  x: 0.65, y: 2.42, w: 8.7, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const cypherQueries = [
  'MATCH (p:Person {name:"张巡"})-[r]-(other) RETURN p, r, other',
  'MATCH (p:Person)-[r]-(g:Gazetteer) WHERE g.name CONTAINS "固安" RETURN p, r, g',
  'MATCH (p1:Person)-[r:OFFICIAL]->(p2) WHERE r.title CONTAINS "县令" RETURN p1.name, r.title',
];

cypherQueries.forEach((q, i) => {
  const y = 2.85 + i * 0.48;
  slide9.addShape(pres.shapes.RECTANGLE, {
    x: 0.65, y, w: 8.7, h: 0.4,
    fill: { color: "1E3A5F" },
    line: { color: "1E3A5F" },
  });
  slide9.addText(q, {
    x: 0.75, y, w: 8.5, h: 0.4,
    fontSize: 10, fontFace: "Consolas",
    color: "A9DFBF", valign: "middle",
  });
});

// Stats bar
slide9.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 4.5, w: 9.0, h: 0.8,
  fill: { color: COLORS.navy },
  line: { color: COLORS.navy },
});
const vizStats = [
  { val: "1,247", label: "人物节点" },
  { val: "3,582", label: "关系边" },
  { val: "2.87", label: "平均度" },
];
vizStats.forEach((s, i) => {
  const x = 1.0 + i * 2.8;
  slide9.addText(s.val, {
    x, y: 4.55, w: 2.2, h: 0.4,
    fontSize: 24, fontFace: "Arial", bold: true,
    color: COLORS.red, align: "center", margin: 0,
  });
  slide9.addText(s.label, {
    x, y: 4.95, w: 2.2, h: 0.28,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.white, align: "center", margin: 0,
  });
});

addBottomBar(slide9);
addSlideNumber(slide9, 9);

// ==============================================================
// SLIDE 10: RAG Q&A
// ==============================================================
let slide10 = pres.addSlide();
slide10.background = { color: COLORS.lightBg };

slide10.addText("功能四：RAG智能问答", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 30, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Pipeline
const ragSteps = [
  "用户提问",
  "BGE查询编码\n(768维向量)",
  "混合检索\n向量Top20\n+BM25 Top20",
  "RRF融合\n(k=60,a=0.5)",
  "Top5",
  "Qwen2.5-3B\n生成答案",
];

ragSteps.forEach((step, i) => {
  const x = 0.3 + i * 1.6;
  const isKey = i === 3;
  slide10.addShape(pres.shapes.RECTANGLE, {
    x, y: 0.95, w: 1.4, h: 1.1,
    fill: { color: isKey ? COLORS.red : COLORS.blueAccent },
    line: { color: isKey ? COLORS.red : COLORS.blueAccent },
  });
  slide10.addText(step, {
    x, y: 0.95, w: 1.4, h: 1.1,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.white, align: "center", valign: "middle",
  });
  if (i < ragSteps.length - 1) {
    slide10.addText("\u2192", {
      x: x + 1.35, y: 1.35, w: 0.25, h: 0.35,
      fontSize: 16, color: COLORS.grayText, align: "center", valign: "middle",
    });
  }
});

// Question types
slide10.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 2.25, w: 4.3, h: 2.0,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide10.addText("支持的问题类型", {
  x: 0.65, y: 2.38, w: 4.0, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const qTypes = [
  { type: "事实型", example: "张巡是哪一年去世的？", color: "3498DB" },
  { type: "列表型", example: "列出所有在固安县任职的县令", color: "27AE60" },
  { type: "比较型", example: "新旧版本《固安县志》有何差异？", color: "E74C3C" },
  { type: "解释型", example: "什么是避讳字？为什么会有避讳？", color: "9B59B6" },
];

qTypes.forEach((q, i) => {
  const y = 2.8 + i * 0.55;
  slide10.addShape(pres.shapes.RECTANGLE, {
    x: 0.65, y, w: 0.75, h: 0.38,
    fill: { color: q.color },
    line: { color: q.color },
  });
  slide10.addText(q.type, {
    x: 0.65, y, w: 0.75, h: 0.38,
    fontSize: 10, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.white, align: "center", valign: "middle",
  });
  slide10.addText(q.example, {
    x: 1.5, y, w: 3.1, h: 0.38,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.darkText, valign: "middle", margin: 0,
  });
});

// Knowledge base info
slide10.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 2.25, w: 4.4, h: 2.0,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide10.addText("知识库覆盖", {
  x: 5.25, y: 2.38, w: 4.1, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

slide10.addShape(pres.shapes.RECTANGLE, {
  x: 5.25, y: 2.82, w: 4.1, h: 0.7,
  fill: { color: "EBF5FB" },
  line: { color: "D6EAF8" },
});
slide10.addText("1998年《固安县志》\n已种子填充，共1998条记录", {
  x: 5.35, y: 2.88, w: 3.9, h: 0.58,
  fontSize: 12, fontFace: "Microsoft YaHei",
  color: COLORS.darkText, align: "center",
});

const kbSections = ["建制沿革", "人物传记", "自然灾害", "物产资源", "艺文诗词", "职官表"];
slide10.addText("包含篇章：", {
  x: 5.25, y: 3.6, w: 4.1, h: 0.25,
  fontSize: 11, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
slide10.addText(kbSections.join(" \u00b7 "), {
  x: 5.25, y: 3.88, w: 4.1, h: 0.3,
  fontSize: 11, fontFace: "Microsoft YaHei",
  color: COLORS.grayText, margin: 0,
});

// Example Q&A
slide10.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 4.4, w: 9.0, h: 0.9,
  fill: { color: "FEF9E7" },
  line: { color: "F9E79F" },
});
slide10.addText("示例问答", {
  x: 0.65, y: 4.48, w: 8.7, h: 0.3,
  fontSize: 12, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
slide10.addText("问：固安县历史上发生过哪些重大自然灾害？  \u2192  答：（检索相关段落，LLM生成答案，引用《固安县志》原文）", {
  x: 0.65, y: 4.8, w: 8.7, h: 0.4,
  fontSize: 11, fontFace: "Microsoft YaHei",
  color: COLORS.darkText, margin: 0,
});

addBottomBar(slide10);
addSlideNumber(slide10, 10);

// ==============================================================
// SLIDE 11: RAG Hybrid Retrieval Details
// ==============================================================
let slide11 = pres.addSlide();
slide11.background = { color: COLORS.lightBg };

slide11.addText("功能四（续）：混合检索技术细节", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 28, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Retrieval flow
slide11.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 0.95, w: 9.0, h: 0.7,
  fill: { color: COLORS.navy },
  line: { color: COLORS.navy },
});
slide11.addText("用户查询 Q  \u2192  BGE编码  \u2192  Milvus ANN检索 Top20  \u2192  BM25索引 Top20  \u2192  RRF融合  \u2192  Top5输出", {
  x: 0.6, y: 1.05, w: 8.8, h: 0.5,
  fontSize: 12, fontFace: "Microsoft YaHei",
  color: COLORS.white, align: "center", valign: "middle",
});

// RRF formula
slide11.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 1.8, w: 4.3, h: 1.6,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide11.addText("RRF 融合公式", {
  x: 0.65, y: 1.92, w: 4.0, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

slide11.addShape(pres.shapes.RECTANGLE, {
  x: 0.65, y: 2.32, w: 4.0, h: 0.5,
  fill: { color: "1E3A5F" },
  line: { color: "1E3A5F" },
});
slide11.addText("Score(doc) = a x (1/(k+rank_vec)) + (1-a) x (1/(k+rank_bm25))", {
  x: 0.7, y: 2.35, w: 3.9, h: 0.44,
  fontSize: 10, fontFace: "Consolas",
  color: "A9DFBF", align: "center", valign: "middle",
});

const rrfParams = [
  ["参数", "值", "说明"],
  ["k", "60", "RRF平滑因子"],
  ["a", "0.5", "向量:BM25 = 50%:50%"],
];
rrfParams.forEach((row, ri) => {
  const y = 2.9 + ri * 0.22;
  const isHeader = ri === 0;
  row.forEach((cell, ci) => {
    slide11.addText(cell, {
      x: 0.65 + ci * 1.33, y, w: 1.33, h: 0.22,
      fontSize: 10, fontFace: "Microsoft YaHei",
      color: isHeader ? COLORS.navy : COLORS.darkText,
      bold: isHeader,
    });
  });
});

// Fusion example
slide11.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 1.8, w: 4.4, h: 1.6,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide11.addText("融合计算示例", {
  x: 5.25, y: 1.92, w: 4.1, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
slide11.addText("向量检索: [A:1, B:2, C:3, D:4, E:5]\nBM25检索:  [B:1, F:2, A:3, G:4, H:5]", {
  x: 5.25, y: 2.32, w: 4.1, h: 0.5,
  fontSize: 10, fontFace: "Consolas",
  color: COLORS.grayText, margin: 0,
});

const fusionResults = [
  { doc: "B", score: "0.75", note: "综合最强", color: COLORS.red },
  { doc: "A", score: "0.67", note: "两路都命中", color: "27AE60" },
  { doc: "C", score: "0.17", note: "仅向量命中", color: COLORS.grayText },
];
fusionResults.forEach((r, i) => {
  const y = 2.9 + i * 0.3;
  slide11.addText(r.doc + "  " + r.score, {
    x: 5.25, y, w: 1.5, h: 0.25,
    fontSize: 12, fontFace: "Arial", bold: true,
    color: r.color, margin: 0,
  });
  slide11.addText("\u2190 " + r.note, {
    x: 6.75, y, w: 2.5, h: 0.25,
    fontSize: 10, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, margin: 0,
  });
});

// Chunk strategy
slide11.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 3.55, w: 9.0, h: 1.8,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide11.addText("Chunk 分块策略", {
  x: 0.65, y: 3.68, w: 8.7, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const chunkItems = [
  { label: "分块层级", val: "卷 \u2192 章 \u2192 节 \u2192 段" },
  { label: "最大块大小", val: "256 tokens" },
  { label: "块重叠", val: "50 tokens（保证上下文连续）" },
  { label: "向量维度", val: "768（BAAI/bge-base-chinese-v1.5）" },
  { label: "向量索引", val: "Milvus 2.3.4（ANN检索）" },
];
chunkItems.forEach((c, i) => {
  const col = i % 2;
  const row = Math.floor(i / 2);
  const x = 0.65 + col * 4.5;
  const y = 4.1 + row * 0.4;
  slide11.addText(c.label + "：", {
    x, y, w: 1.5, h: 0.32,
    fontSize: 12, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, margin: 0,
  });
  slide11.addText(c.val, {
    x: x + 1.5, y, w: 2.8, h: 0.32,
    fontSize: 12, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.navy, margin: 0,
  });
});

addBottomBar(slide11);
addSlideNumber(slide11, 11);

// ==============================================================
// SLIDE 12: Map Segmentation
// ==============================================================
let slide12 = pres.addSlide();
slide12.background = { color: COLORS.lightBg };

slide12.addText("功能五：古籍舆图要素分割", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 30, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Pipeline
const mapSteps = [
  "上传古籍\n舆图",
  "预处理\n512x512/归一化",
  "U-Net推理\nResNet34编码",
  "六类要素\n分割掩码",
  "矢量化\nOpenCV轮廓",
  "MapLabel OCR\n文字识别",
  "GeoJSON\n输出",
];
mapSteps.forEach((step, i) => {
  const x = 0.28 + i * 1.38;
  slide12.addShape(pres.shapes.RECTANGLE, {
    x, y: 0.92, w: 1.2, h: 0.88,
    fill: { color: i === 2 ? COLORS.red : COLORS.blueAccent },
    line: { color: i === 2 ? COLORS.red : COLORS.blueAccent },
  });
  slide12.addText(step, {
    x, y: 0.92, w: 1.2, h: 0.88,
    fontSize: 10, fontFace: "Microsoft YaHei",
    color: COLORS.white, align: "center", valign: "middle",
  });
  if (i < mapSteps.length - 1) {
    slide12.addText("\u2192", {
      x: x + 1.15, y: 1.2, w: 0.23, h: 0.32,
      fontSize: 14, color: COLORS.grayText, align: "center", valign: "middle",
    });
  }
});

// 6 element types
slide12.addText("六类要素分类", {
  x: 0.5, y: 1.95, w: 5.0, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const mapElements = [
  { id: "0", name: "background", example: "背景底色", color: "000000", textColor: "FFFFFF" },
  { id: "1", name: "rivers", example: "河流/湖泊", color: "00FFFF", textColor: "000000" },
  { id: "2", name: "mountains", example: "山脉/丘陵", color: "8B5A2B", textColor: "FFFFFF" },
  { id: "3", name: "cities", example: "城池/聚落", color: "FF0000", textColor: "FFFFFF" },
  { id: "4", name: "boundaries", example: "边界/道路", color: "00FF00", textColor: "000000" },
  { id: "5", name: "text_labels", example: "文字标注", color: "FFFF00", textColor: "000000" },
];

mapElements.forEach((el, i) => {
  const col = i % 3;
  const row = Math.floor(i / 3);
  const x = 0.5 + col * 3.0;
  const y = 2.38 + row * 0.75;

  slide12.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.5, h: 0.55,
    fill: { color: el.color },
    line: { color: el.color },
  });
  slide12.addText(el.id, {
    x, y, w: 0.5, h: 0.55,
    fontSize: 14, fontFace: "Arial", bold: true,
    color: el.textColor, align: "center", valign: "middle",
  });
  slide12.addText(el.name + "\n" + el.example, {
    x: x + 0.6, y, w: 2.2, h: 0.55,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.darkText, valign: "middle", margin: 0,
  });
});

// Output info
slide12.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 4.0, w: 4.3, h: 1.3,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide12.addText("模型规格", {
  x: 0.65, y: 4.12, w: 4.0, h: 0.32,
  fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
const modelSpecs = [
  "编码器：ResNet34（ImageNet预训练）",
  "输入尺寸：512 x 512",
  "输出：6类热力图（softmax概率）",
  "支持 NVIDIA RTX 5060 GPU加速",
];
slide12.addText(
  modelSpecs.map((s, i) => ({ text: s, options: { bullet: true, breakLine: i < modelSpecs.length - 1 } })),
  { x: 0.65, y: 4.48, w: 4.0, h: 0.78, fontSize: 11, fontFace: "Microsoft YaHei", color: COLORS.grayText }
);

// GeoJSON output
slide12.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 4.0, w: 4.4, h: 1.3,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide12.addText("输出格式", {
  x: 5.25, y: 4.12, w: 4.1, h: 0.32,
  fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
slide12.addShape(pres.shapes.RECTANGLE, {
  x: 5.25, y: 4.5, w: 4.1, h: 0.7,
  fill: { color: "1E3A5F" },
  line: { color: "1E3A5F" },
});
slide12.addText('{"rivers": [{"polygon": [[x1,y1],...], "area": 1234}], "mountains": [...], "cities": [...]}', {
  x: 5.3, y: 4.53, w: 4.0, h: 0.64,
  fontSize: 9, fontFace: "Consolas",
  color: "A9DFBF", valign: "middle",
});

addBottomBar(slide12);
addSlideNumber(slide12, 12);

// ==============================================================
// SLIDE 13: Punctuation & Compilation
// ==============================================================
let slide13 = pres.addSlide();
slide13.background = { color: COLORS.lightBg };

slide13.addText("功能六：古籍标点与多源编纂", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 30, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Punctuation flow
slide13.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 0.92, w: 9.0, h: 0.75,
  fill: { color: COLORS.navy },
  line: { color: COLORS.navy },
});
slide13.addText("标点补全流程：原始古籍文本（无标点）\u2192 BERT断句模型\u2192句读检测（之/乎/者/也分析）\u2192标点补全（句末：。？！～，句内：、，）\u2192人工校对（可选）", {
  x: 0.6, y: 1.0, w: 8.8, h: 0.6,
  fontSize: 12, fontFace: "Microsoft YaHei",
  color: COLORS.white, valign: "middle",
});

// 5 strategies
slide13.addText("多源编纂融合策略（5种）", {
  x: 0.5, y: 1.85, w: 9.0, h: 0.38,
  fontSize: 16, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const strategies = [
  { name: "PREFER_COMPLETE", zh: "取信息最丰富版本", scene: "版本有残缺", color: "3498DB" },
  { name: "PREFER_QUALITY", zh: "取OCR置信度最高", scene: "图像质量参差", color: "27AE60" },
  { name: "PREFER_ORIGINAL", zh: "取善本/祖本", scene: "学术研究", color: "9B59B6" },
  { name: "VOTE_MERGE", zh: "多版本投票", scene: "多数一致", color: "E74C3C" },
  { name: "STRUCTURAL_MERGE", zh: "按篇章结构拼接", scene: "大规模差异", color: "F39C12" },
];

strategies.forEach((s, i) => {
  const y = 2.3 + i * 0.52;
  slide13.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y, w: 0.08, h: 0.45,
    fill: { color: s.color },
    line: { color: s.color },
  });
  slide13.addShape(pres.shapes.RECTANGLE, {
    x: 0.58, y, w: 2.4, h: 0.45,
    fill: { color: s.color },
    line: { color: s.color },
  });
  slide13.addText(s.name, {
    x: 0.58, y, w: 2.4, h: 0.45,
    fontSize: 10, fontFace: "Consolas", bold: true,
    color: COLORS.white, align: "center", valign: "middle",
  });
  slide13.addText(s.zh, {
    x: 3.1, y, w: 2.8, h: 0.45,
    fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.darkText, valign: "middle", margin: 0,
  });
  slide13.addText(s.scene, {
    x: 5.9, y, w: 1.8, h: 0.45,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, valign: "middle", margin: 0,
  });
});

// Example
slide13.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 4.92, w: 9.0, h: 0.45,
  fill: { color: "FEF9E7" },
  line: { color: "F9E79F" },
});
slide13.addText("融合示例：版本A(5章第5章残缺) + 版本B(4章第5章完整)  \u2192  STRUCTURAL_MERGE  \u2192  各取最优章节拼接", {
  x: 0.6, y: 4.97, w: 8.8, h: 0.35,
  fontSize: 12, fontFace: "Microsoft YaHei",
  color: COLORS.darkText, valign: "middle",
});

addBottomBar(slide13);
addSlideNumber(slide13, 13);

// ==============================================================
// SLIDE 14: Annotation Extraction
// ==============================================================
let slide14 = pres.addSlide();
slide14.background = { color: COLORS.lightBg };

slide14.addText("功能七：古籍标注提取", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 30, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Description
slide14.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 0.92, w: 9.0, h: 0.55,
  fill: { color: "EBF5FB" },
  line: { color: "D6EAF8" },
});
slide14.addText("古人常在书页天头、地脚、栏外批注，包含评点/补充/校正等信息，但位置不固定、字体多样，难以批量提取", {
  x: 0.65, y: 0.97, w: 8.7, h: 0.45,
  fontSize: 12, fontFace: "Microsoft YaHei",
  color: COLORS.darkText, valign: "middle",
});

// Pipeline
const annotSteps = [
  "古籍书页\n图片",
  "Faster R-CNN\n目标检测",
  "MSER+HSV\n文字检测",
  "EasyOCR\n文字识别",
  "AnnotationAligner\n对齐",
  "关联原文\n结构化存储",
];
annotSteps.forEach((step, i) => {
  const x = 0.3 + i * 1.6;
  slide14.addShape(pres.shapes.RECTANGLE, {
    x, y: 1.62, w: 1.4, h: 0.85,
    fill: { color: COLORS.blueAccent },
    line: { color: COLORS.blueAccent },
  });
  slide14.addText(step, {
    x, y: 1.62, w: 1.4, h: 0.85,
    fontSize: 10, fontFace: "Microsoft YaHei",
    color: COLORS.white, align: "center", valign: "middle",
  });
  if (i < annotSteps.length - 1) {
    slide14.addText("\u2192", {
      x: x + 1.35, y: 1.9, w: 0.25, h: 0.3,
      fontSize: 14, color: COLORS.grayText, align: "center", valign: "middle",
    });
  }
});

// 3 annotation types
slide14.addText("批注分类（3类）", {
  x: 0.5, y: 2.65, w: 4.5, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const annotTypes = [
  { type: "评点批", feature: "朱砂红，横写栏外", example: "「妙哉此言」", color: "E74C3C" },
  { type: "补充批", feature: "墨色，与正文同", example: "小字补入", color: "27AE60" },
  { type: "校正批", feature: "删除线/圈标注", example: "「当作○○」", color: "F39C12" },
];

annotTypes.forEach((a, i) => {
  const y = 3.08 + i * 0.72;
  slide14.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y, w: 4.5, h: 0.65,
    fill: { color: COLORS.white },
    shadow: mkShadow(),
    line: { color: COLORS.white },
  });
  slide14.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y, w: 0.08, h: 0.65,
    fill: { color: a.color },
    line: { color: a.color },
  });
  slide14.addText(a.type, {
    x: 0.68, y: y + 0.08, w: 1.0, h: 0.25,
    fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
    color: a.color, margin: 0,
  });
  slide14.addText(a.feature, {
    x: 0.68, y: y + 0.33, w: 2.0, h: 0.22,
    fontSize: 10, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, margin: 0,
  });
  slide14.addText("例：" + a.example, {
    x: 2.7, y: y + 0.15, w: 2.1, h: 0.4,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.darkText, valign: "middle", margin: 0,
  });
});

// Stats
slide14.addShape(pres.shapes.RECTANGLE, {
  x: 5.3, y: 2.65, w: 4.2, h: 2.15,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide14.addText("实测性能指标", {
  x: 5.45, y: 2.78, w: 3.9, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});

const annotStats = [
  { val: "~82%", label: "批注检测召回率" },
  { val: "~88%", label: "文字识别准确率" },
  { val: "~2s", label: "处理速度（单页）" },
];
annotStats.forEach((s, i) => {
  const y = 3.25 + i * 0.55;
  slide14.addText(s.val, {
    x: 5.45, y, w: 1.5, h: 0.4,
    fontSize: 24, fontFace: "Arial", bold: true,
    color: COLORS.red, margin: 0,
  });
  slide14.addText(s.label, {
    x: 7.0, y: y + 0.05, w: 2.3, h: 0.35,
    fontSize: 12, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, valign: "middle", margin: 0,
  });
});

addBottomBar(slide14);
addSlideNumber(slide14, 14);

// ==============================================================
// SLIDE 15: LLM Engine
// ==============================================================
let slide15 = pres.addSlide();
slide15.background = { color: COLORS.lightBg };

slide15.addText("LLM引擎：Qwen2.5-3B + Gemma4 本地部署", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 26, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Two model cards
const llmModels = [
  {
    name: "Qwen2.5-3B",
    spec: "30亿参数 \u00b7 int4量化",
    deploy: "Ollama v0.20.0",
    use: "主引擎：RAG生成/知识抽取/问答",
    color: "2980B9",
  },
  {
    name: "Gemma4-2B",
    spec: "20亿参数 \u00b7 Q4_K_M量化",
    deploy: "llama.cpp",
    use: "备用：轻量推理",
    color: "27AE60",
  },
];

llmModels.forEach((m, i) => {
  const x = 0.5 + i * 4.6;
  slide15.addShape(pres.shapes.RECTANGLE, {
    x, y: 0.95, w: 4.4, h: 1.85,
    fill: { color: COLORS.white },
    shadow: mkShadow(),
    line: { color: COLORS.white },
  });
  slide15.addShape(pres.shapes.RECTANGLE, {
    x, y: 0.95, w: 4.4, h: 0.08,
    fill: { color: m.color },
    line: { color: m.color },
  });
  slide15.addText(m.name, {
    x, y: 1.1, w: 4.4, h: 0.42,
    fontSize: 18, fontFace: "Arial", bold: true,
    color: m.color, align: "center", margin: 0,
  });
  slide15.addText(m.spec, {
    x, y: 1.55, w: 4.4, h: 0.3,
    fontSize: 12, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, align: "center", margin: 0,
  });
  slide15.addText(m.deploy, {
    x, y: 1.88, w: 4.4, h: 0.28,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.darkText, align: "center", margin: 0,
  });
  slide15.addShape(pres.shapes.RECTANGLE, {
    x: x + 0.2, y: 2.2, w: 4.0, h: 0.48,
    fill: { color: "EBF5FB" },
    line: { color: "D6EAF8" },
  });
  slide15.addText(m.use, {
    x: x + 0.3, y: 2.25, w: 3.8, h: 0.38,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.darkText, align: "center", valign: "middle",
  });
});

// Config
slide15.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 2.95, w: 4.4, h: 1.3,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide15.addText("Ollama 配置参数", {
  x: 0.65, y: 3.08, w: 4.1, h: 0.32,
  fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
slide15.addShape(pres.shapes.RECTANGLE, {
  x: 0.65, y: 3.45, w: 4.1, h: 0.7,
  fill: { color: "1E3A5F" },
  line: { color: "1E3A5F" },
});
slide15.addText('base_url: localhost:11434\nmodel: qwen2.5:3b\ntemperature: 0.3 \u00b7 max_tokens: 2048 \u00b7 timeout: 120s', {
  x: 0.75, y: 3.5, w: 3.9, h: 0.6,
  fontSize: 10, fontFace: "Consolas",
  color: "A9DFBF", margin: 0,
});

// Advantages
slide15.addShape(pres.shapes.RECTANGLE, {
  x: 5.1, y: 2.95, w: 4.4, h: 1.3,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide15.addText("核心优势", {
  x: 5.25, y: 3.08, w: 4.1, h: 0.32,
  fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
const llmAdv = ["完全离线运行，无需互联网", "数据不出本地，安全可控", "支持模型热切换", "中文古籍理解专项优化", "支持DeepSeek/Kimi云端API降级"];
slide15.addText(
  llmAdv.map((a, i) => ({ text: a, options: { bullet: true, breakLine: i < llmAdv.length - 1 } })),
  { x: 5.25, y: 3.42, w: 4.1, h: 0.8, fontSize: 11, fontFace: "Microsoft YaHei", color: COLORS.grayText }
);

// LLM-assisted functions
slide15.addShape(pres.shapes.RECTANGLE, {
  x: 0.5, y: 4.4, w: 9.0, h: 0.95,
  fill: { color: COLORS.navy },
  line: { color: COLORS.navy },
});
slide15.addText("LLM 辅助功能", {
  x: 0.65, y: 4.5, w: 8.7, h: 0.3,
  fontSize: 12, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.white, margin: 0,
});
const llmFuncs = ["KG实体抽取", "KG关系推理", "RAG答案生成", "避讳字朝代判断", "异体字语义消歧"];
llmFuncs.forEach((f, i) => {
  const x = 0.65 + i * 1.78;
  slide15.addShape(pres.shapes.RECTANGLE, {
    x, y: 4.85, w: 1.65, h: 0.38,
    fill: { color: COLORS.red },
    line: { color: COLORS.red },
  });
  slide15.addText(f, {
    x, y: 4.85, w: 1.65, h: 0.38,
    fontSize: 11, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.white, align: "center", valign: "middle",
  });
});

addBottomBar(slide15);
addSlideNumber(slide15, 15);

// ==============================================================
// SLIDE 16: System Architecture
// ==============================================================
let slide16 = pres.addSlide();
slide16.background = { color: COLORS.lightBg };

slide16.addText("系统架构与技术栈", {
  x: 0.5, y: 0.25, w: 9, h: 0.55,
  fontSize: 30, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Architecture layers
const archLayers = [
  { label: "前端", content: "Vue 3.4 + Vite + Element Plus 2.5 + ECharts 5.5", detail: "7视图：Home/校勘/知识图谱/问答/地图/编纂/标注", color: "3498DB" },
  { label: "后端", content: "FastAPI 0.109 + Python 3.10+", detail: "20+ RESTful API \u00b7 CORS \u00b7 异步任务", color: "27AE60" },
  { label: "AI模块", content: "OCR识别 \u00b7 规范化 \u00b7 校勘引擎 \u00b7 NER模型", detail: "知识图谱 \u00b7 RAG问答 \u00b7 舆图分割 \u00b7 标注提取", color: "9B59B6" },
  { label: "LLM层", content: "Ollama (Qwen2.5-3B) \u00b7 llama.cpp (Gemma4-2B)", detail: "完全本地运行 \u00b7 无需商业API", color: "E74C3C" },
  { label: "数据库", content: "Neo4j 5.12 \u00b7 Milvus 2.3.4 \u00b7 ChromaDB（备选）", detail: "图数据库 \u00b7 向量数据库", color: "F39C12" },
  { label: "容器", content: "Docker Compose", detail: "Neo4j + Milvus + etcd + MinIO", color: "1ABC9C" },
];

archLayers.forEach((layer, i) => {
  const y = 0.9 + i * 0.72;
  // Label box
  slide16.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y, w: 1.1, h: 0.62,
    fill: { color: layer.color },
    line: { color: layer.color },
  });
  slide16.addText(layer.label, {
    x: 0.5, y, w: 1.1, h: 0.62,
    fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.white, align: "center", valign: "middle",
  });
  // Content
  slide16.addShape(pres.shapes.RECTANGLE, {
    x: 1.6, y, w: 7.9, h: 0.62,
    fill: { color: COLORS.white },
    shadow: mkShadow(),
    line: { color: COLORS.white },
  });
  slide16.addText(layer.content, {
    x: 1.75, y: y + 0.05, w: 7.6, h: 0.32,
    fontSize: 13, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.darkText, margin: 0,
  });
  slide16.addText(layer.detail, {
    x: 1.75, y: y + 0.35, w: 7.6, h: 0.22,
    fontSize: 10, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, margin: 0,
  });
});

addBottomBar(slide16);
addSlideNumber(slide16, 16);

// ==============================================================
// SLIDE 17: Performance Metrics
// ==============================================================
let slide17 = pres.addSlide();
slide17.background = { color: COLORS.lightBg };

slide17.addText("系统性能指标", {
  x: 0.5, y: 0.25, w: 9, h: 0.55,
  fontSize: 30, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

// Performance table
const perfData = [
  [{ text: "模块", options: { bold: true, fill: { color: COLORS.navy }, color: COLORS.white } },
   { text: "指标", options: { bold: true, fill: { color: COLORS.navy }, color: COLORS.white } },
   { text: "实测值", options: { bold: true, fill: { color: COLORS.navy }, color: COLORS.white } }],
  ["OCR", "单页识别速度", "~1.2秒/页"],
  ["OCR", "印刷体字符准确率", ">92%"],
  ["规范化", "异体字识别覆盖率", ">96%"],
  ["NER", "实体识别F1值", ">85%"],
  ["校勘", "差异检测召回率", ">88%"],
  ["校勘", "差异判决准确率", ">82%"],
  ["RAG", "向量检索延迟", "~15ms"],
  ["RAG", "端到端问答延迟", "2-5秒"],
  ["KG", "实体抽取速度", "~50实体/秒"],
  ["舆图分割", "U-Net推理速度", "~30fps"],
  ["标注提取", "批注检测召回率", "~82%"],
  ["LLM", "Qwen首token延迟", "~800ms"],
];

slide17.addTable(perfData, {
  x: 0.5, y: 0.9, w: 5.8, h: 4.35,
  colW: [1.2, 2.4, 2.2],
  fontSize: 12, fontFace: "Microsoft YaHei",
  color: COLORS.darkText,
  border: { pt: 0.5, color: COLORS.mediumGray },
  align: "center", valign: "middle",
});

// Resource usage
slide17.addShape(pres.shapes.RECTANGLE, {
  x: 6.5, y: 0.9, w: 3.0, h: 2.3,
  fill: { color: COLORS.white },
  shadow: mkShadow(),
  line: { color: COLORS.white },
});
slide17.addText("资源占用", {
  x: 6.65, y: 1.02, w: 2.7, h: 0.35,
  fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.darkText, margin: 0,
});
const resItems = [
  { name: "Ollama (Qwen)", val: "~4GB" },
  { name: "Neo4j", val: "~2GB" },
  { name: "Milvus", val: "~1GB" },
  { name: "U-Net GPU", val: "~2GB" },
  { name: "总计", val: "<10GB" },
];
resItems.forEach((r, i) => {
  const y = 1.42 + i * 0.36;
  slide17.addText(r.name, {
    x: 6.65, y, w: 1.8, h: 0.3,
    fontSize: 12, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, margin: 0,
  });
  slide17.addText(r.val, {
    x: 8.45, y, w: 0.9, h: 0.3,
    fontSize: 12, fontFace: "Arial", bold: true,
    color: COLORS.navy, align: "right", margin: 0,
  });
});

// Big stat callouts
slide17.addShape(pres.shapes.RECTANGLE, {
  x: 6.5, y: 3.35, w: 3.0, h: 1.9,
  fill: { color: COLORS.navy },
  line: { color: COLORS.navy },
});
slide17.addText("LLM首token", {
  x: 6.5, y: 3.5, w: 3.0, h: 0.3,
  fontSize: 11, fontFace: "Microsoft YaHei",
  color: COLORS.mediumGray, align: "center", margin: 0,
});
slide17.addText("~800ms", {
  x: 6.5, y: 3.8, w: 3.0, h: 0.7,
  fontSize: 32, fontFace: "Arial", bold: true,
  color: COLORS.red, align: "center", margin: 0,
});
slide17.addText("向量检索延迟 ~15ms", {
  x: 6.5, y: 4.55, w: 3.0, h: 0.28,
  fontSize: 11, fontFace: "Microsoft YaHei",
  color: COLORS.mediumGray, align: "center", margin: 0,
});
slide17.addText("端到端问答 2-5秒", {
  x: 6.5, y: 4.85, w: 3.0, h: 0.28,
  fontSize: 11, fontFace: "Microsoft YaHei",
  color: COLORS.mediumGray, align: "center", margin: 0,
});

addBottomBar(slide17);
addSlideNumber(slide17, 17);

// ==============================================================
// SLIDE 18: Innovation Points
// ==============================================================
let slide18 = pres.addSlide();
slide18.background = { color: COLORS.lightBg };

slide18.addText("五大创新特色", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 32, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

const innovations = [
  {
    num: "01",
    title: "古籍专用OCR + 避讳字智能还原",
    detail: "业界首个内置2000+避讳规则库，自动识别朝代并还原本字，康熙/雍正/乾隆全覆盖",
    color: "3498DB",
  },
  {
    num: "02",
    title: "语义级 Needleman-Wunsch 多版本校勘",
    detail: "引入BERT语义编码，字形不同但语义相近也能正确对齐与判决",
    color: "27AE60",
  },
  {
    num: "03",
    title: "LLM辅助知识图谱双轨抽取",
    detail: "正则模式 + Qwen2.5-3B推理双轨并行，规则保证精确性，LLM保证覆盖面",
    color: "9B59B6",
  },
  {
    num: "04",
    title: "RAG + 本地LLM古籍智能问答",
    detail: "混合检索 + RRF融合 + 本地生成，完全离线，数据不外传",
    color: "E74C3C",
  },
  {
    num: "05",
    title: "古籍灰度舆图离线伪标签生成",
    detail: "基于MSER+HSV离线生成标注，无需SAM等交互工具，批量处理古籍地图",
    color: "F39C12",
  },
];

innovations.forEach((inn, i) => {
  const y = 0.92 + i * 0.88;
  slide18.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y, w: 9.0, h: 0.8,
    fill: { color: COLORS.white },
    shadow: mkShadow(),
    line: { color: COLORS.white },
  });
  slide18.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y, w: 0.75, h: 0.8,
    fill: { color: inn.color },
    line: { color: inn.color },
  });
  slide18.addText(inn.num, {
    x: 0.5, y, w: 0.75, h: 0.8,
    fontSize: 20, fontFace: "Arial", bold: true,
    color: COLORS.white, align: "center", valign: "middle",
  });
  slide18.addText(inn.title, {
    x: 1.4, y: y + 0.1, w: 7.9, h: 0.32,
    fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.darkText, margin: 0,
  });
  slide18.addText(inn.detail, {
    x: 1.4, y: y + 0.44, w: 7.9, h: 0.3,
    fontSize: 11, fontFace: "Microsoft YaHei",
    color: COLORS.grayText, margin: 0,
  });
});

addBottomBar(slide18);
addSlideNumber(slide18, 18);

// ==============================================================
// SLIDE 19: Live Demo
// ==============================================================
let slide19 = pres.addSlide();
slide19.background = { color: COLORS.lightBg };

slide19.addText("现场演示环节", {
  x: 0.5, y: 0.25, w: 9, h: 0.6,
  fontSize: 32, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.navy, margin: 0,
});

const demos = [
  { num: "01", func: "OCR识别", content: "上传古籍页，实时识别+避讳字还原", color: "3498DB" },
  { num: "02", func: "多版本校勘", content: "双版本导入，差异高亮+判决理由", color: "27AE60" },
  { num: "03", func: "知识图谱", content: "构建《张巡传》KG，ECharts可视化", color: "9B59B6" },
  { num: "04", func: "RAG问答", content: "提问「固安县有哪些自然灾害？」", color: "E74C3C" },
  { num: "05", func: "舆图分割", content: "上传古籍舆图，6类要素分割结果", color: "F39C12" },
];

demos.forEach((d, i) => {
  const y = 1.0 + i * 0.88;
  slide19.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y, w: 9.0, h: 0.78,
    fill: { color: COLORS.white },
    shadow: mkShadow(),
    line: { color: COLORS.white },
  });
  slide19.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y, w: 0.75, h: 0.78,
    fill: { color: d.color },
    line: { color: d.color },
  });
  slide19.addText(d.num, {
    x: 0.5, y, w: 0.75, h: 0.78,
    fontSize: 20, fontFace: "Arial", bold: true,
    color: COLORS.white, align: "center", valign: "middle",
  });
  slide19.addShape(pres.shapes.RECTANGLE, {
    x: 1.4, y: y + 0.15, w: 2.0, h: 0.48,
    fill: { color: d.color },
    line: { color: d.color },
  });
  slide19.addText(d.func, {
    x: 1.4, y: y + 0.15, w: 2.0, h: 0.48,
    fontSize: 14, fontFace: "Microsoft YaHei", bold: true,
    color: COLORS.white, align: "center", valign: "middle",
  });
  slide19.addText(d.content, {
    x: 3.6, y: y + 0.15, w: 5.7, h: 0.48,
    fontSize: 14, fontFace: "Microsoft YaHei",
    color: COLORS.darkText, valign: "middle", margin: 0,
  });
});

addBottomBar(slide19);
addSlideNumber(slide19, 19);

// ==============================================================
// SLIDE 20: Thank You
// ==============================================================
let slide20 = pres.addSlide();
slide20.background = { color: COLORS.navy };

slide20.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 0, w: 10, h: 0.08,
  fill: { color: COLORS.red },
  line: { color: COLORS.red },
});

slide20.addText("感谢聆听", {
  x: 0.5, y: 1.6, w: 9, h: 0.9,
  fontSize: 48, fontFace: "Microsoft YaHei", bold: true,
  color: COLORS.white, align: "center",
});

slide20.addText("感谢各位评委老师的指导！", {
  x: 0.5, y: 2.65, w: 9, h: 0.5,
  fontSize: 20, fontFace: "Microsoft YaHei",
  color: COLORS.mediumGray, align: "center",
});

slide20.addShape(pres.shapes.RECTANGLE, {
  x: 3.5, y: 3.3, w: 3, h: 0.04,
  fill: { color: COLORS.red },
  line: { color: COLORS.red },
});

const contactInfo = [
  "团队：志鉴开发团队",
  "赛事：2026中国大学生计算机设计大赛",
  "联系：zhijian@example.com",
];
contactInfo.forEach((info, i) => {
  slide20.addText(info, {
    x: 0.5, y: 3.55 + i * 0.45, w: 9, h: 0.4,
    fontSize: 14, fontFace: "Microsoft YaHei",
    color: COLORS.mediumGray, align: "center",
  });
});

// Write file
pres.writeFile({ fileName: "C:\\Users\\hbusl\\zhijian\\志鉴系统答辩PPT.pptx" })
  .then(() => console.log("PPT created successfully!"))
  .catch(err => console.error("Error:", err));

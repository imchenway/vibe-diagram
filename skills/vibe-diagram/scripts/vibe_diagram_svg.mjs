// 作者 SVG 接入完整原生查看器，不重写图形和关系几何。
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { applyTemplate } from '../assets/archify/renderers/shared/utils.mjs';

// 参数由 Python 入口以独立文件传入，正文仅作为数据处理。
const request = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
// 模板从当前技能包内定位，离开源码仓库仍可运行。
const templatePath = fileURLToPath(new URL('../assets/archify/assets/template.html', import.meta.url));
// 完整原生模板负责语言和交互结构。
const template = fs.readFileSync(templatePath, 'utf8');
fs.writeFileSync(process.argv[3], applyTemplate(template, { ...request, cards: '', sourceEvidence: null }));

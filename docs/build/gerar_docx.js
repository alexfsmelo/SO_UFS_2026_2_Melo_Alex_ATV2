// Gera docs/relatorio_AV2_SO_Alex_Melo.docx a partir de conteudo.json
// Uso: node gerar_docx.js conteudo.json saida.docx
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow,
  TableCell, WidthType, ShadingType, ImageRun, BorderStyle, LevelFormat, Footer, PageNumber,
  TabStopType,
} = require("docx");

const [, , entrada, saida] = process.argv;
const C = JSON.parse(fs.readFileSync(entrada, "utf8"));
const BASE = path.dirname(path.resolve(entrada));

const FONTE = "Calibri";
const TAM = 20.5; // half-points (10,25 pt)
const LARG_UTIL = 9638; // A4 com margens de 2 cm: 11906 - 2*1134

function runs(texto, extra = {}) {
  // **negrito**, `codigo`, _italico_
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|(?<![\w/])_[^_]+_(?![\w]))/g;
  let i = 0, m;
  while ((m = re.exec(texto)) !== null) {
    if (m.index > i) out.push(new TextRun({ text: texto.slice(i, m.index), ...extra }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...extra }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", size: (extra.size || TAM) - 2, ...Object.fromEntries(Object.entries(extra).filter(([k]) => k !== "size")) }));
    else out.push(new TextRun({ text: t.slice(1, -1), italics: true, ...extra }));
    i = m.index + t.length;
  }
  if (i < texto.length) out.push(new TextRun({ text: texto.slice(i), ...extra }));
  return out;
}

function par(texto, opts = {}) {
  return new Paragraph({
    children: runs(texto, opts.run || {}),
    alignment: opts.align || AlignmentType.JUSTIFIED,
    spacing: { after: opts.after ?? 100, before: opts.before ?? 0, line: 264 },
    keepNext: opts.keepNext || false,
  });
}

function legenda(texto) {
  return new Paragraph({
    children: runs(texto, { size: 17, color: "52514E" }),
    alignment: AlignmentType.CENTER, spacing: { before: 40, after: 140 },
  });
}

const borda = { style: BorderStyle.SINGLE, size: 4, color: "BFBDB6" };
const bordas = { top: borda, bottom: borda, left: borda, right: borda };

function tabela(t) {
  const n = t.cols.length;
  const pesos = t.pesos || Array(n).fill(1);
  const soma = pesos.reduce((a, b) => a + b, 0);
  const larg = pesos.map((p) => Math.floor((LARG_UTIL * p) / soma));
  larg[n - 1] += LARG_UTIL - larg.reduce((a, b) => a + b, 0);
  const fs_ = t.fonte || 16;
  const celula = (txt, i, cab) => new TableCell({
    width: { size: larg[i], type: WidthType.DXA },
    borders: bordas,
    shading: cab ? { type: ShadingType.CLEAR, color: "auto", fill: "EEF3FB" } : undefined,
    margins: { top: 30, bottom: 30, left: 70, right: 70 },
    children: [new Paragraph({
      children: runs(String(txt), { size: fs_, bold: cab }),
      alignment: i === 0 || (t.esquerda || []).includes(i) ? AlignmentType.LEFT : AlignmentType.CENTER,
      spacing: { after: 0, line: 240 },
    })],
  });
  const linhas = [new TableRow({ tableHeader: true, children: t.cols.map((c, i) => celula(c, i, true)) })];
  for (const r of t.rows) linhas.push(new TableRow({ children: r.map((c, i) => celula(c, i, false)) }));
  return new Table({ width: { size: LARG_UTIL, type: WidthType.DXA }, columnWidths: larg, rows: linhas });
}

function figura(b) {
  const arq = path.resolve(BASE, b.fig);
  const dados = fs.readFileSync(arq);
  // dimensoes do PNG
  const w = dados.readUInt32BE(16), h = dados.readUInt32BE(20);
  const largPx = Math.round((b.cm || 16.5) / 2.54 * 96);
  const altPx = Math.round(largPx * h / w);
  return [
    new Paragraph({ children: [new ImageRun({ type: "png", data: dados, transformation: { width: largPx, height: altPx } })], alignment: AlignmentType.CENTER, spacing: { before: 60, after: 0 }, keepNext: true }),
    legenda(b.cap),
  ];
}

const filhos = [];
for (const b of C.blocos) {
  if (b.titulo) {
    filhos.push(new Paragraph({ children: [new TextRun({ text: b.titulo, bold: true, size: 30, color: "1F3B63" })], alignment: AlignmentType.CENTER, spacing: { after: 60 } }));
  } else if (b.subtitulo) {
    filhos.push(new Paragraph({ children: runs(b.subtitulo, { size: 20, color: "52514E" }), alignment: AlignmentType.CENTER, spacing: { after: 40 } }));
  } else if (b.h1) {
    filhos.push(new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: b.h1 })], spacing: { before: 200, after: 80 }, keepNext: true }));
  } else if (b.h2) {
    filhos.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: b.h2 })], spacing: { before: 120, after: 60 }, keepNext: true }));
  } else if (b.p) {
    filhos.push(par(b.p));
  } else if (b.bullets) {
    for (const it of b.bullets) filhos.push(new Paragraph({ numbering: { reference: "bol", level: 0 }, children: runs(it), alignment: AlignmentType.JUSTIFIED, spacing: { after: 40, line: 260 } }));
  } else if (b.code) {
    for (const linha of b.code.split("\n")) filhos.push(new Paragraph({ children: [new TextRun({ text: linha || " ", font: "Consolas", size: 15 })], spacing: { after: 0, line: 220 }, shading: { type: ShadingType.CLEAR, color: "auto", fill: "F4F3F0" } }));
    filhos.push(new Paragraph({ children: [], spacing: { after: 80 } }));
  } else if (b.fig) {
    filhos.push(...figura(b));
  } else if (b.table) {
    if (b.cap) filhos.push(new Paragraph({ children: runs(b.cap, { size: 17, color: "52514E" }), alignment: AlignmentType.CENTER, spacing: { before: 60, after: 40 }, keepNext: true }));
    filhos.push(tabela(b.table));
    filhos.push(new Paragraph({ children: [], spacing: { after: 100 } }));
  } else if (b.quebra) {
    filhos.push(new Paragraph({ children: [], pageBreakBefore: true }));
  }
}

const doc = new Document({
  creator: "Álex Felipe Santos Melo",
  title: C.titulo_doc,
  styles: {
    default: { document: { run: { font: FONTE, size: TAM } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 25, bold: true, color: "1F3B63", font: FONTE }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 21.5, bold: true, color: "2A78D6", font: FONTE }, paragraph: { spacing: { before: 120, after: 60 }, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "bol", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 220 } } } }] }] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "AV2 · Sistemas Operacionais · Álex Melo · ", size: 15, color: "8A8883" }), new TextRun({ children: [PageNumber.CURRENT], size: 15, color: "8A8883" })] })] }) },
    children: filhos,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(saida, buf); console.log("ok", saida); });

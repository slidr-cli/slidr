// Package pptx generates OOXML presentation files from the slide AST.
// Produces native PowerPoint shapes — no rasterization.
package pptx

import (
	"archive/zip"
	"bytes"
	"fmt"
	"regexp"
	"strings"

	"github.com/slidr-cli/slidr/internal/parser"
)

// Render produces a .pptx file from parsed slides.
// styleCSS is the raw CSS from frontmatter (used to extract --bg for slide background).
func Render(doc *parser.Document, styleCSS string) ([]byte, error) {
	var buf bytes.Buffer
	w := zip.NewWriter(&buf)

	dims := doc.Meta.Size()
	sw, sh := dims[0], dims[1]

	bgColor := extractVar(styleCSS, "--bg")
	if bgColor == "" {
		bgColor = "07110C"
	}

	// Content types.
	ctBuf := buildContentTypes(len(doc.Slides))
	writeZipEntry(w, "[Content_Types].xml", ctBuf)

	// Relationships.
	writeZipEntry(w, "_rels/.rels", xmlRels)
	writeZipEntry(w, "ppt/slideMasters/_rels/slideMaster1.xml.rels", xmlSMRels)

// Presentation.
	presBuf := buildPresentationXML(len(doc.Slides))
	writeZipEntry(w, "ppt/presentation.xml", presBuf)

	// Update presentation rels with slide references.
	presRels := buildPresRels(len(doc.Slides))
	writeZipEntry(w, "ppt/_rels/presentation.xml.rels", presRels)

	// Slide master and layout.
	writeZipEntry(w, "ppt/slideMasters/slideMaster1.xml", fmt.Sprintf(xmlSlideMaster, bgColor))
	writeZipEntry(w, "ppt/slideLayouts/slideLayout1.xml", xmlSlideLayout)
	writeZipEntry(w, "ppt/theme/theme1.xml", xmlTheme)

	// Slides.
	for i, slide := range doc.Slides {
		name := fmt.Sprintf("ppt/slides/slide%d.xml", i+1)
		writeZipEntry(w, name, renderSlideXML(&slide, sw, sh))
	}

	// Slide relationships.
	for i := range doc.Slides {
		name := fmt.Sprintf("ppt/slides/_rels/slide%d.xml.rels", i+1)
		writeZipEntry(w, name, xmlSlideRels)
	}

	w.Close()
	return buf.Bytes(), nil
}

func writeZipEntry(w *zip.Writer, name, content string) {
	f, _ := w.Create(name)
	f.Write([]byte(content))
}

func renderSlideXML(slide *parser.Slide, sw, sh int) string {
	var shapes []string
	shapeID := 1

	y := slideMarginTop
	contentWidth := sw - 2*slideMarginLeft

	for _, node := range slide.Children {
		s := renderShape(node, slideMarginLeft, &y, contentWidth, sw, sh, &shapeID)
		if s != "" {
			shapes = append(shapes, s)
		}
	}

	shapesXML := strings.Join(shapes, "\n")
	return fmt.Sprintf(xmlSlide, shapesXML)
}

func renderShape(node parser.Node, x int, y *int, contentWidth, sw, sh int, shapeID *int) string {
	switch n := node.(type) {
	case *parser.Heading:
		return renderTextBox(n.Content, x, *y, contentWidth, n.Level, shapeID, y)
	case *parser.Paragraph:
		return renderTextBox(n.Content, x, *y, contentWidth, 0, shapeID, y)
	case *parser.Table:
		return renderTableShape(n, x, *y, contentWidth, shapeID, y)
	case *parser.Grid:
		return renderGridShape(n, x, y, contentWidth, sw, shapeID)
	case *parser.Quote:
		return renderTextBox(n.Text, x, *y, contentWidth, 0, shapeID, y)
	case *parser.ListNode:
		return renderListShape(n, x, *y, contentWidth, shapeID, y)
	case *parser.Kicker:
		return renderTextLine(n.Text, x, *y, contentWidth, 0, shapeID, y)
	case *parser.AttrNode:
		text := n.Value
		if text == "" && n.Attrs != nil {
			parts := make([]string, 0, len(n.Attrs))
			for k, v := range n.Attrs {
				parts = append(parts, k+": "+v)
			}
			text = strings.Join(parts, ", ")
		}
		return renderTextLine(text, x, *y, contentWidth, 0, shapeID, y)
	default:
		return ""
	}
}

// Slide layout constants.
const (
	slideMarginLeft = 64
	slideMarginTop  = 5
	textRowHeight   = 30
	textRowAdvance  = 40
	tableRowHeight  = 30
	tableRowAdvance = 10

	fontH1     = 4400
	fontH2     = 3200
	fontH3     = 1800
	fontBody   = 1800
	fontHeader = 1400
	fontCell   = 1200
)

// EMU helpers. 1 inch = 914400 EMU, 1 px @96dpi = 9525 EMU.
func pxToEMU(px int) int { return px * 9525 }

func renderTextBox(inlines []parser.InlineNode, x int, y, w, level int, shapeID *int, cy *int) string {
	text := renderInline(inlines)
	return renderTextLine(text, x, y, w, level, shapeID, cy)
}

func renderTextLine(text string, x int, y, w, level int, shapeID *int, cy *int) string {
	if text == "" {
		return ""
	}
	id := *shapeID
	*shapeID++

	emoX := pxToEMU(x)
	emoY := pxToEMU(*cy)
	emoW := pxToEMU(w)
	emoH := pxToEMU(textRowHeight)

	size := fontBody
	bold := "0"
	switch level {
	case 1:
		size = fontH1
		bold = "1"
	case 2:
		size = fontH2
		bold = "1"
	case 3:
		size = fontH3
		bold = "1"
	}

	*cy += textRowAdvance

	return fmt.Sprintf(xmlTextBox, id, emoX, emoY, emoW, emoH, size, bold, xmlEscape(text))
}

func renderTableShape(tbl *parser.Table, x int, y, w int, shapeID *int, cy *int) string {
	id := *shapeID
	*shapeID++

	rows := len(tbl.Rows) + 1
	cols := len(tbl.Headers)
	colW := w / cols

	emoX := pxToEMU(x)
	emoY := pxToEMU(*cy)
	emoW := pxToEMU(w)
	emoH := pxToEMU(rows * tableRowHeight)

	*cy += rows*tableRowHeight + tableRowAdvance

	var rowsXML strings.Builder
	// Header
	rowsXML.WriteString("<a:tr>\n")
	for _, h := range tbl.Headers {
		rowsXML.WriteString(fmt.Sprintf(xmlTableCell, fontHeader, "1", xmlEscape(h)))
	}
	rowsXML.WriteString("</a:tr>\n")
	// Body
	for _, row := range tbl.Rows {
		rowsXML.WriteString("<a:tr>\n")
		for _, cell := range row {
			rowsXML.WriteString(fmt.Sprintf(xmlTableCell, fontCell, "0", xmlEscape(cell)))
		}
		rowsXML.WriteString("</a:tr>\n")
	}

	return fmt.Sprintf(xmlTable, id, emoX, emoY, emoW, emoH, xmlTableGrid(colW, cols), rowsXML.String())
}

func renderGridShape(grid *parser.Grid, x int, y *int, contentWidth, sw int, shapeID *int) string {
	var parts []string
	cols := grid.Cols
	if cols < 2 {
		cols = len(grid.Children)
	}
	if cols < 2 {
		cols = 2
	}
	gap := grid.Gap
	if gap == 0 {
		gap = 16
	}
	colW := (contentWidth - (cols-1)*gap) / cols

	saveY := *y
	for i, child := range grid.Children {
		*y = saveY
		cx := x + i*(colW+gap)
		s := renderShape(child, cx, y, colW, sw, 720, shapeID)
		if s != "" {
			parts = append(parts, s)
		}
	}
	// Advance y to max of all columns.
	*y = saveY + 120

	return strings.Join(parts, "\n")
}

func renderListShape(list *parser.ListNode, x int, y, w int, shapeID *int, cy *int) string {
	var parts []string
	for _, item := range list.Items {
		text := "• " + item
		parts = append(parts, renderTextLine(text, x+10, y, w-10, 0, shapeID, cy))
	}
	return strings.Join(parts, "\n")
}

func renderInline(nodes []parser.InlineNode) string {
	var parts []string
	for _, n := range nodes {
		switch v := n.(type) {
		case *parser.Text:
			parts = append(parts, v.Content)
		case *parser.Strong:
			parts = append(parts, renderInline(v.Children))
		case *parser.CodeSpan:
			parts = append(parts, v.Content)
		case *parser.Link:
			parts = append(parts, v.Text)
		case *parser.SoftBreak:
			parts = append(parts, " ")
		}
	}
	return strings.Join(parts, "")
}

func xmlEscape(s string) string {
	s = strings.ReplaceAll(s, "&", "&amp;")
	s = strings.ReplaceAll(s, "<", "&lt;")
	s = strings.ReplaceAll(s, ">", "&gt;")
	s = strings.ReplaceAll(s, "\"", "&quot;")
	return s
}

func extractVar(css, name string) string {
	re := regexp.MustCompile(name + `:\s*([#\w]+)`)
	if m := re.FindStringSubmatch(css); m != nil {
		return strings.TrimPrefix(m[1], "#")
	}
	return ""
}

func xmlTableGrid(colW, cols int) string {
	var b strings.Builder
	w := pxToEMU(colW)
	for i := 0; i < cols; i++ {
		b.WriteString(fmt.Sprintf("<a:gridCol w=\"%d\"/>", w))
	}
	return b.String()
}

func buildPresentationXML(numSlides int) string {
	var slides strings.Builder
	for i := 1; i <= numSlides; i++ {
		slides.WriteString(fmt.Sprintf(`<p:sldId id="%d" r:id="rId%d"/>`, 255+i, i+1))
	}
	return fmt.Sprintf(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>%s</p:sldIdLst>
</p:presentation>`, slides.String())
}

func buildContentTypes(numSlides int) string {
	var slides strings.Builder
	for i := 1; i <= numSlides; i++ {
		slides.WriteString(fmt.Sprintf(`  <Override PartName="/ppt/slides/slide%d.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>`+"\n", i))
	}
	return fmt.Sprintf(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
%s</Types>`, slides.String())
}

func buildPresRels(numSlides int) string {
	var rels strings.Builder
	rels.WriteString(`<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>` + "\n")
	for i := 1; i <= numSlides; i++ {
		rels.WriteString(fmt.Sprintf(`<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide%d.xml"/>`+"\n", i+1, i))
	}
	return fmt.Sprintf(`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
%s</Relationships>`, rels.String())
}

const xmlContentTypes = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
</Types>`

const xmlRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>`

const xmlPresRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
</Relationships>`

const xmlPresentation = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
</p:presentation>`

const xmlSlideMaster = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="%s"/></a:solidFill></p:bgPr></p:bg></p:cSld>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
</p:sldMaster>`

const xmlSMRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>`

const xmlSlideLayout = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld name="Blank"/>
</p:sldLayout>`

const xmlSlideRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>`

const xmlTheme = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Slidr">
  <a:themeElements>
    <a:clrScheme name="Slidr">
      <a:dk1><a:srgbClr val="000000"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="111111"/></a:dk2>
      <a:lt2><a:srgbClr val="EEEEEE"/></a:lt2>
      <a:accent1><a:srgbClr val="0FD05D"/></a:accent1>
      <a:accent2><a:srgbClr val="67D8FF"/></a:accent2>
      <a:accent3><a:srgbClr val="FFD166"/></a:accent3>
      <a:accent4><a:srgbClr val="FF7A7A"/></a:accent4>
      <a:accent5><a:srgbClr val="AEC0B3"/></a:accent5>
      <a:accent6><a:srgbClr val="70F5A2"/></a:accent6>
    </a:clrScheme>
    <a:fontScheme name="Slidr">
      <a:majorFont><a:latin typeface="Arial"/></a:majorFont>
      <a:minorFont><a:latin typeface="Arial"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Slidr"><a:fillStyleLst></a:fillStyleLst><a:lnStyleLst></a:lnStyleLst><a:effectStyleLst></a:effectStyleLst><a:bgFillStyleLst></a:bgFillStyleLst></a:fmtScheme>
  </a:themeElements>
</a:theme>`

const xmlSlide = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr/>
%s
    </p:spTree>
  </p:cSld>
</p:sld>`

const xmlTextBox = `<p:sp>
  <p:nvSpPr><p:cNvPr id="%d" name=""/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr><a:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
  <p:txBody><a:bodyPr/><a:lstStyle/>
    <a:p><a:r><a:rPr sz="%d" b="%s" lang="zh-CN"/><a:t>%s</a:t></a:r></a:p>
  </p:txBody>
</p:sp>`

const xmlTable = `<p:graphicFrame>
  <p:nvGraphicFramePr><p:cNvPr id="%d" name=""/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
  <p:xfrm><a:off x="%d" y="%d"/><a:ext cx="%d" cy="%d"/></p:xfrm>
  <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
    <a:tbl>
      <a:tblGrid>%s</a:tblGrid>
%s
    </a:tbl>
  </a:graphicData></a:graphic>
</p:graphicFrame>`

const xmlTableCell = `<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr sz="%d" b="%s" lang="zh-CN"/><a:t>%s</a:t></a:r></a:p></a:txBody></a:tc>
`

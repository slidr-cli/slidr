package parser

import (
	"bytes"
	"fmt"
	"io"
	"regexp"
	"strings"

	"github.com/yuin/goldmark"
	"github.com/yuin/goldmark/extension"
	extast "github.com/yuin/goldmark/extension/ast"
	gast "github.com/yuin/goldmark/ast"
	"github.com/yuin/goldmark/text"
	"gopkg.in/yaml.v3"
)

var frontmatterRe = regexp.MustCompile(`^---\s*\n((?s:.*?))\n---\s*\n`)
var slideSepRe = regexp.MustCompile(`\n---\s*\n`)

// Parse reads markdown and returns a Document.
func Parse(r io.Reader) (*Document, error) {
	b, err := io.ReadAll(r)
	if err != nil {
		return nil, fmt.Errorf("read: %w", err)
	}

	// Normalize line endings and trim.
	b = bytes.ReplaceAll(b, []byte("\r\n"), []byte("\n"))
	b = bytes.TrimRight(b, "\n")

	doc := &Document{}

	// Extract frontmatter.
	content := b
	if m := frontmatterRe.FindSubmatchIndex(b); m != nil {
		if err := yaml.Unmarshal(b[m[2]:m[3]], &doc.Meta); err != nil {
			return nil, fmt.Errorf("frontmatter: %w", err)
		}
		content = b[m[1]:] // right after closing ---
	}

	// Split into slides at horizontal rules.
	slides := splitSlides(content, doc.Meta)
	doc.Slides = slides

	for i := range doc.Slides {
		doc.Slides[i].Layout = detectLayout(doc.Slides[i])
	}

	return doc, nil
}

// DebugRawSlides returns raw content per slide for debugging.
func DebugRawSlides(r io.Reader) ([]string, error) {
	b, err := io.ReadAll(r)
	if err != nil {
		return nil, err
	}
	b = bytes.ReplaceAll(b, []byte("\r\n"), []byte("\n"))
	b = bytes.TrimRight(b, "\n")

	content := b
	if m := frontmatterRe.FindSubmatchIndex(b); m != nil {
		content = b[m[1]:]
	}

	var slides []string
	for _, part := range slideSepRe.Split(string(content), -1) {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		// Strip per-slide frontmatter.
		if fm := frontmatterRe.FindStringSubmatch(part); fm != nil {
			loc := frontmatterRe.FindStringIndex(part)
			part = strings.TrimSpace(part[loc[1]:])
		}
		slides = append(slides, part)
	}
	return slides, nil
}

// splitSlides splits markdown content at thematic breaks (---).
func splitSlides(content []byte, defaultMeta Meta) []Slide {
	var slides []Slide

	parts := slideSepRe.Split(string(content), -1)
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}

		slide := Slide{Meta: defaultMeta}

		// Check for per-slide frontmatter.
		if fm := frontmatterRe.FindStringSubmatch(part); fm != nil {
			var slideMeta Meta
			if err := yaml.Unmarshal([]byte(fm[1]), &slideMeta); err == nil {
				slide.Meta = mergeMeta(defaultMeta, slideMeta)
			}
			// Remove the frontmatter block from content.
			loc := frontmatterRe.FindStringIndex(part)
			part = strings.TrimSpace(part[loc[1]:])
		}

		// Extract speaker notes.
		noteBytes := []byte(part)
		notes, remainder := extractNotes(noteBytes)
		slide.Notes = notes
		slide.Children = parseSlideContent(string(remainder))
		slides = append(slides, slide)
	}

	return slides
}

var stripTagRe = regexp.MustCompile(`<[^>]*>`)

// stripTags removes HTML tags from a string.
func stripTags(s string) string {
	return strings.TrimSpace(stripTagRe.ReplaceAllString(s, ""))
}

// extractNotes pulls HTML comments from the start of slide content.
func extractNotes(content []byte) (string, []byte) {
	noteRe := regexp.MustCompile(`(?s)^<!--\s*\n?(.*?)\n?\s*-->\s*\n?`)
	if m := noteRe.FindSubmatchIndex(content); m != nil {
		return strings.TrimSpace(string(content[m[2]:m[3]])), content[m[1]:]
	}
	return "", content
}

// newMarkdown creates a goldmark instance with extensions enabled.
func newMarkdown() goldmark.Markdown {
	return goldmark.New(
		goldmark.WithExtensions(
			extension.Table,
		),
	)
}

// parseSlideContent parses a single slide's markdown into AST nodes.
// Nodes appear in markdown source order.
func parseSlideContent(content string) []Node {
	// Extract fenced blocks and directives (they're removed from content).
	content, fencedNodes := extractFencedNodes(content)
	content, directiveNodes := extractDirectives(content)

	// Parse remaining markdown with goldmark.
	md := newMarkdown()
	reader := text.NewReader([]byte(content))
	root := md.Parser().Parse(reader)

	// Goldmark nodes first (headings, quotes, paragraphs -- these appear
	// before fenced/directive blocks in source order for the common case).
	var nodes []Node
	for child := root.FirstChild(); child != nil; child = child.NextSibling() {
		if child.Kind() == extast.KindTable {
			table := convertTable(child, []byte(content))
			if table != nil {
				nodes = append(nodes, table)
			}
			continue
		}
		node := convertNode(child, []byte(content))
		if node != nil {
			nodes = append(nodes, node)
		}
	}

	// Then fenced blocks (grids, cards -- typically after headings/quotes).
	nodes = append(nodes, fencedNodes...)
	// Then directives (@kicker, @tiny, etc. -- typically at start or end).
	nodes = append(nodes, directiveNodes...)

	// Extract HTML patterns last (they're rare in new-format markdown).
	_, htmlNodes := extractKnownHTML(content)
	nodes = append(nodes, htmlNodes...)

	return nodes
}

// convertTable converts a goldmark extension table node to our Table node.
func convertTable(n gast.Node, source []byte) *Table {
	table := &Table{}
	for child := n.FirstChild(); child != nil; child = child.NextSibling() {
		switch child.Kind() {
		case extast.KindTableHeader:
			for cell := child.FirstChild(); cell != nil; cell = cell.NextSibling() {
				if cell.Kind() == extast.KindTableCell {
					table.Headers = append(table.Headers, renderInlineText(extractInline(cell, source)))
				}
			}
		case extast.KindTableRow:
			var row []string
			for cell := child.FirstChild(); cell != nil; cell = cell.NextSibling() {
				if cell.Kind() == extast.KindTableCell {
					row = append(row, renderInlineText(extractInline(cell, source)))
				}
			}
			if len(row) > 0 {
				table.Rows = append(table.Rows, row)
			}
		}
	}
	if len(table.Headers) == 0 && len(table.Rows) == 0 {
		return nil
	}
	return table
}

// extractKnownHTML extracts recognized HTML patterns and returns
// the cleaned content and the extracted nodes.
func extractKnownHTML(content string) (string, []Node) {
	var nodes []Node

	// Extract <div class="kicker">...</div>
	kickerRe := regexp.MustCompile(`<div\s+class="kicker">(.*?)</div>`)
	if m := kickerRe.FindStringSubmatch(content); m != nil {
		nodes = append(nodes, &Kicker{Text: strings.TrimSpace(m[1])})
		content = kickerRe.ReplaceAllString(content, "")
	}

	// Extract <div class="speaker">Name<span>Role</span></div>
	speakerRe := regexp.MustCompile(`<div\s+class="speaker">(.*?)<span>(.*?)</span></div>`)
	if m := speakerRe.FindStringSubmatch(content); m != nil {
		nodes = append(nodes, &Speaker{Name: strings.TrimSpace(m[1]), Role: strings.TrimSpace(m[2])})
		content = speakerRe.ReplaceAllString(content, "")
	}

	// Extract <div class="quote">...</div> blocks.
	quoteRe := regexp.MustCompile(`(?s)<div\s+class="quote[^"]*">(.*?)</div>`)
	for {
		m := quoteRe.FindStringSubmatchIndex(content)
		if m == nil {
			break
		}
		quoteText := strings.TrimSpace(content[m[2]:m[3]])
		quoteText = stripTags(quoteText)
		nodes = append(nodes, &Quote{Text: []InlineNode{&Text{Content: quoteText}}})
		content = content[:m[0]] + content[m[1]:]
	}

	// Extract HTML tables before stripping tags.
	content, tableNodes := extractHTMLTables(content)
	nodes = append(nodes, tableNodes...)

	// Strip remaining HTML tags.
	content = stripTagRe.ReplaceAllString(content, "")

	return strings.TrimSpace(content), nodes
}

// extractDirectives parses @type value directive lines into generic AttrNodes.
// Syntax: @type key=val key2=val2 rest of value
// Examples:
//   @kicker 新员工培训 · 2026-06-24          → AttrNode{Type:"kicker", Value:"新员工培训 · 2026-06-24"}
//   @speaker name=宋净超 role=开源与生态       → AttrNode{Type:"speaker", Attrs:{"name":"宋净超","role":"开源与生态"}}
//   @subtitle HAMi = AI 时代的 GPU Control Plane → AttrNode{Type:"subtitle", Value:"HAMi = AI 时代的..."}
func extractDirectives(content string) (string, []Node) {
	kvRe := regexp.MustCompile(`(\w+)=("[^"]*"|\S+)`)
	var nodes []Node
	lines := strings.Split(content, "\n")
	var result []string

	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if !strings.HasPrefix(trimmed, "@") {
			result = append(result, line)
			continue
		}
		// Skip @@ escaped.
		if strings.HasPrefix(trimmed, "@@") {
			result = append(result, trimmed[1:])
			continue
		}

		// Split into type and rest.
		rest := strings.TrimPrefix(trimmed, "@")
		space := strings.IndexByte(rest, ' ')
		if space < 0 {
			result = append(result, line)
			continue
		}
		typ := rest[:space]
		value := strings.TrimSpace(rest[space+1:])

		// Check for word characters and hyphens in type name.
		if !regexp.MustCompile(`^[\w-]+$`).MatchString(typ) {
			result = append(result, line)
			continue
		}

		node := &AttrNode{Type: typ, Attrs: make(map[string]string)}

		// Extract key=value pairs from the beginning.
		for _, m := range kvRe.FindAllStringSubmatch(value, -1) {
			key := m[1]
			val := strings.Trim(m[2], `"`)
			node.Attrs[key] = val
		}

		// Everything that's not a key=value pair is the plain value.
		node.Value = kvRe.ReplaceAllString(value, "")
		node.Value = strings.TrimSpace(node.Value)

		nodes = append(nodes, node)
	}

	return strings.Join(result, "\n"), nodes
}

// extractFencedNodes parses ::: fence blocks into Grid/Card AST nodes.
func extractFencedNodes(content string) (string, []Node) {
	var nodes []Node
	lines := strings.Split(content, "\n")
	type block struct {
		typ      string
		tag      string
		cols     int
		class    []string
		lines    []string
		children []Node
	}
	var stack []*block
	var result strings.Builder

	flushCard := func(b *block) *Card {
		card := &Card{Class: strings.Join(b.class, " ")}
		if b.tag != "" {
			card.Tag = &Tag{Color: TagColor(b.tag)}
		}
		inner := strings.TrimSpace(strings.Join(b.lines, "\n"))
		h3Re := regexp.MustCompile(`(?m)^###\s+(.*)$`)
		if m := h3Re.FindStringSubmatch(inner); m != nil {
			card.Header = strings.TrimSpace(m[1])
			if card.Tag != nil {
				card.Tag.Text = card.Header
			}
			inner = h3Re.ReplaceAllString(inner, "")
		}
		inner = strings.TrimSpace(inner)
		if inner != "" {
			for _, line := range strings.Split(inner, "\n") {
				line = strings.TrimSpace(line)
				if line != "" {
					card.Body = append(card.Body, &Text{Content: line})
				}
			}
		}
		if card.Header == "" && len(card.Body) == 0 {
			return nil
		}
		return card
	}

	flushGrid := func(b *block) *Grid {
		cols := b.cols
		if cols == 0 {
			cols = len(b.children)
		}
		if cols == 0 {
			cols = 2
		}
		gridNodes := make([]Node, len(b.children))
		for i, c := range b.children {
			gridNodes[i] = c
		}
		return &Grid{Cols: cols, Gap: 16, Class: strings.Join(b.class, " "), Children: gridNodes}
	}

	i := 0
	for i < len(lines) {
		line := lines[i]
		trimmed := strings.TrimSpace(line)

		if strings.HasPrefix(trimmed, ":::") && !strings.HasPrefix(trimmed, "::::") {
			parts := strings.Fields(trimmed)
			if len(parts) >= 2 {
				typ := parts[1]
				attrStr := ""
				// Type may have {attrs} attached without a space: "card{tag=\"green\"}"
				if idx := strings.IndexByte(typ, '{'); idx >= 0 {
					attrStr = typ[idx:]
					typ = typ[:idx]
				}
				// Collect remaining parts as attributes.
				if len(parts) > 2 {
					rest := strings.Join(parts[2:], " ")
					if attrStr != "" {
						attrStr += " " + rest
					} else {
						attrStr = rest
					}
				}
				attrStr = strings.Trim(attrStr, "{}")
				b := &block{typ: typ}
				for _, attr := range splitAttrParts(attrStr) {
					attr = strings.TrimSpace(attr)
					eq := strings.IndexByte(attr, '=')
					if eq < 0 {
						// Bare word → CSS class.
						if attr != "" {
							b.class = append(b.class, attr)
						}
						continue
					}
					key := strings.TrimSpace(attr[:eq])
					val := strings.TrimSpace(attr[eq+1:])
					val = strings.Trim(val, `"`)
					switch key {
					case "tag":
						b.tag = val
					case "cols":
						fmt.Sscanf(val, "%d", &b.cols)
					case "class":
						for _, c := range strings.Fields(val) {
							b.class = append(b.class, c)
						}
					}
				}
				stack = append(stack, b)
				i++
				continue
			}
		}

		if trimmed == ":::" && len(stack) > 0 {
			top := stack[len(stack)-1]
			stack = stack[:len(stack)-1]
			var node Node
			switch top.typ {
			case "card":
				node = flushCard(top)
			case "grid":
				node = flushGrid(top)
			}
			if node != nil {
				if len(stack) > 0 {
					stack[len(stack)-1].children = append(stack[len(stack)-1].children, node)
				} else {
					nodes = append(nodes, node)
				}
			}
			i++
			continue
		}

		if len(stack) > 0 {
			stack[len(stack)-1].lines = append(stack[len(stack)-1].lines, line)
		} else {
			result.WriteString(line)
			result.WriteString("\n")
		}
		i++
	}

	return strings.TrimSpace(result.String()), nodes
}

func splitAttrParts(s string) []string {
	var parts []string
	inQuote := false
	last := 0
	for i := 0; i < len(s); i++ {
		switch s[i] {
		case '"':
			inQuote = !inQuote
		case ',':
			if !inQuote {
				parts = append(parts, s[last:i])
				last = i + 1
			}
		}
	}
	if last < len(s) {
		parts = append(parts, s[last:])
	}
	return parts
}

func extractHTMLTables(content string) (string, []Node) {
	tableOpenRe := regexp.MustCompile("<table[^>]*>")
	trRe := regexp.MustCompile("(?s)<tr[^>]*>(.*?)</tr>")
	cellRe := regexp.MustCompile("(?s)<t[hd][^>]*>(.*?)</t[hd]>")
	var nodes []Node

	for {
		loc := tableOpenRe.FindStringIndex(content)
		if loc == nil {
			break
		}
		end := findMatchingTag(content, loc[1], "table")
		if end < 0 {
			break
		}
		inner := content[loc[1]:end]

		table := &Table{}
		firstRow := true
		for _, trMatch := range trRe.FindAllStringSubmatch(inner, -1) {
			var row []string
			for _, cellMatch := range cellRe.FindAllStringSubmatch(trMatch[1], -1) {
				cellText := strings.TrimSpace(stripTags(cellMatch[1]))
				row = append(row, cellText)
			}
			if len(row) == 0 {
				continue
			}
			if firstRow {
				table.Headers = row
				firstRow = false
			} else {
				table.Rows = append(table.Rows, row)
			}
		}

		if len(table.Headers) > 0 {
			nodes = append(nodes, table)
		}
		content = content[:loc[0]] + content[end+len("</table>"):]
	}
	return content, nodes
}

func findMatchingTag(s string, startPos int, tag string) int {
	depth := 1
	openRe := regexp.MustCompile("<" + tag + "[\\s>]")
	closeRe := regexp.MustCompile("</" + tag + ">")

	pos := startPos
	for pos < len(s) && depth > 0 {
		openLoc := openRe.FindStringIndex(s[pos:])
		closeLoc := closeRe.FindStringIndex(s[pos:])

		if closeLoc == nil {
			return -1
		}
		if openLoc != nil && openLoc[0] < closeLoc[0] {
			depth++
			pos += openLoc[1]
		} else {
			depth--
			if depth == 0 {
				return pos + closeLoc[0]
			}
			pos += closeLoc[1]
		}
	}
	return -1
}

func convertNode(n gast.Node, source []byte) Node {
	switch n.Kind() {
	case gast.KindHeading:
		h := n.(*gast.Heading)
		return &Heading{
			Level:   h.Level,
			Content: extractInline(h, source),
		}
	case gast.KindParagraph:
		p := n.(*gast.Paragraph)
		return &Paragraph{
			Content: extractInline(p, source),
		}
	case gast.KindList:
		return convertList(n, source)
	case gast.KindCodeBlock:
		cb := n.(*gast.CodeBlock)
		var buf bytes.Buffer
		for i := 0; i < cb.Lines().Len(); i++ {
			line := cb.Lines().At(i)
			buf.Write(line.Value(source))
		}
		return &RawHTML{Content: "<pre><code>" + buf.String() + "</code></pre>"}
	case gast.KindBlockquote:
		bq := n.(*gast.Blockquote)
		var lines []InlineNode
		for child := bq.FirstChild(); child != nil; child = child.NextSibling() {
			if p, ok := child.(*gast.Paragraph); ok {
				lines = append(lines, extractInline(p, source)...)
			}
		}
		return &Quote{Text: lines}
	case gast.KindThematicBreak:
		return nil
	default:
		return nil
	}
}

func convertList(n gast.Node, source []byte) Node {
	list := n.(*gast.List)
	var items []string
	for child := list.FirstChild(); child != nil; child = child.NextSibling() {
		if item, ok := child.(*gast.ListItem); ok {
			// Extract all inline content from the list item.
			var itemText string
			for c := item.FirstChild(); c != nil; c = c.NextSibling() {
				switch c.Kind() {
				case gast.KindParagraph:
					itemText += renderInlineText(extractInline(c, source))
				case gast.KindTextBlock:
					itemText += renderInlineText(extractInline(c, source))
				default:
					itemText += renderInlineText(extractInline(c, source))
				}
			}
			itemText = strings.TrimSpace(itemText)
			if itemText != "" {
				items = append(items, itemText)
			}
		}
	}
	if len(items) == 0 {
		return nil
	}
	return &ListNode{Items: items}
}

// extractInline extracts inline content from a goldmark node.
func extractInline(n gast.Node, source []byte) []InlineNode {
	var nodes []InlineNode
	for child := n.FirstChild(); child != nil; child = child.NextSibling() {
		node := convertInline(child, source)
		if node != nil {
			nodes = append(nodes, node)
		}
	}
	return nodes
}

// convertInline translates a goldmark inline node.
func convertInline(n gast.Node, source []byte) InlineNode {
	switch n.Kind() {
	case gast.KindText:
		t := n.(*gast.Text)
		seg := t.Segment
		content := string(seg.Value(source))
		// If this text node ends with a line break, append a space.
		if t.HardLineBreak() || t.SoftLineBreak() {
			content += " "
		}
		return &Text{Content: content}
	case gast.KindString:
		s := n.(*gast.String)
		return &Text{Content: string(s.Value)}
	case gast.KindEmphasis:
		em := n.(*gast.Emphasis)
		children := extractInline(em, source)
		if em.Level == 2 {
			return &Strong{Children: children}
		}
		if len(children) == 1 {
			return children[0]
		}
		return &Text{Content: renderInlineText(children)}
	case gast.KindCodeSpan:
		return &CodeSpan{Content: string(n.Text(source))}
	case gast.KindLink:
		link := n.(*gast.Link)
		return &Link{
			URL:  string(link.Destination),
			Text: string(link.Text(source)),
		}
	case gast.KindImage:
		img := n.(*gast.Image)
		return &ImageNode{
			URL:  string(img.Destination),
			Alt:  string(img.Text(source)),
		}
	default:
		return &Text{Content: string(n.Text(source))}
	}
}

// renderInlineText flattens inline nodes to plain text.
func renderInlineText(nodes []InlineNode) string {
	var b strings.Builder
	for _, n := range nodes {
		switch v := n.(type) {
		case *Text:
			b.WriteString(v.Content)
		case *Strong:
			b.WriteString(renderInlineText(v.Children))
		case *CodeSpan:
			b.WriteString(v.Content)
		case *Link:
			b.WriteString(v.Text)
		case *SoftBreak:
			b.WriteString(" ")
		}
	}
	return b.String()
}

// mergeMeta merges slide-level meta into document-level defaults.
func mergeMeta(base, override Meta) Meta {
	if override.Theme != "" {
		base.Theme = override.Theme
	}
	if override.Title != "" {
		base.Title = override.Title
	}
	if override.Footer != "" {
		base.Footer = override.Footer
	}
	if override.Paginate {
		base.Paginate = override.Paginate
	}
	if override.SizeRaw != "" {
		base.SizeRaw = override.SizeRaw
	}
	if override.Style != "" {
		base.Style = override.Style
	}
	return base
}

// detectLayout auto-detects the layout type from a slide's children.
func detectLayout(slide Slide) LayoutType {
	hasHeading := false
	var gridCols int
	hasTable := false
	hasQuote := false
	hasStack := false
	hasFunnel := false
	hasColumns := false
	hasSpeaker := false
	hasKicker := false
	hasSubtitle := false

	for _, child := range slide.Children {
		switch n := child.(type) {
		case *Heading:
			if n.Level == 1 {
				hasHeading = true
			}
		case *Grid:
			gridCols = n.Cols
		case *Table:
			hasTable = true
		case *Quote:
			hasQuote = true
		case *Stack:
			hasStack = true
		case *Funnel:
			hasFunnel = true
		case *Columns:
			hasColumns = true
			gridCols = n.Cols
		case *AttrNode:
			switch n.Type {
			case "kicker":
				hasKicker = true
			case "speaker":
				hasSpeaker = true
			case "subtitle":
				hasSubtitle = true
			}
		}
	}

	if hasKicker || hasSpeaker || hasSubtitle {
		return LayoutTitle
	}
	if gridCols == 2 {
		return LayoutGrid2
	}
	if gridCols == 3 {
		return LayoutGrid3
	}
	if gridCols == 4 {
		return LayoutGrid4
	}
	if hasColumns {
		return LayoutColumns
	}
	if hasStack || hasFunnel || hasTable || hasQuote || hasHeading {
		return LayoutContent
	}
	return LayoutContent
}

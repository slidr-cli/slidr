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
func parseSlideContent(content string) []Node {
	content, htmlNodes := extractKnownHTML(content)

	md := newMarkdown()
	reader := text.NewReader([]byte(content))
	root := md.Parser().Parse(reader)

	var nodes []Node
	htmlIdx := 0

	for child := root.FirstChild(); child != nil; child = child.NextSibling() {
		for htmlIdx < len(htmlNodes) {
			nodes = append(nodes, htmlNodes[htmlIdx])
			htmlIdx++
		}

		// Detect goldmark extension table nodes.
		if child.Kind() == extast.KindTable {
			table := convertTable(child, []byte(content))
			if table != nil {
				nodes = append(nodes, table)
			}
			continue
		}
		// DEBUG: uncomment to see what goldmark produces
		// fmt.Fprintf(os.Stderr, "  goldmark child kind=%d type=%T\n", child.Kind(), child)

		node := convertNode(child, []byte(content))
		if node != nil {
			nodes = append(nodes, node)
		}
	}

	for htmlIdx < len(htmlNodes) {
		nodes = append(nodes, htmlNodes[htmlIdx])
		htmlIdx++
	}

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

	// Extract grid containers with cards.
	content, gridNodes := extractGrids(content)
	nodes = append(nodes, gridNodes...)

	// Extract HTML tables before stripping tags.
	content, tableNodes := extractHTMLTables(content)
	nodes = append(nodes, tableNodes...)

	// Strip remaining div wrappers: extract text, discard the div structure.
	// This prevents indented HTML from being parsed as code blocks by goldmark.
	content = unwrapDivs(content)

	// Strip remaining HTML tags.
	content = stripTagRe.ReplaceAllString(content, "")

	return strings.TrimSpace(content), nodes
}

// extractGrids finds <div class="grid"> containers and extracts cards.
func extractGrids(content string) (string, []Node) {
	gridStartRe := regexp.MustCompile(`<div\s+class="grid[^"]*">`)
	var nodes []Node

	for {
		loc := gridStartRe.FindStringIndex(content)
		if loc == nil {
			break
		}
		// Find the matching </div> by counting nesting.
		gridEnd := findMatchingTag(content, loc[1], "div")
		if gridEnd < 0 {
			break
		}
		inner := content[loc[1]:gridEnd]
		cards := extractCards(inner)
		if len(cards) > 0 {
			for _, card := range cards {
				card.Body = cleanInlineNodes(card.Body)
			}
			grid := &Grid{
				Cols:     len(cards),
				Gap:      16,
				Children: make([]Node, len(cards)),
			}
			for i, c := range cards {
				grid.Children[i] = c
			}
			nodes = append(nodes, grid)
		}
		content = content[:loc[0]] + content[gridEnd+len("</div>"):]
	}
	return content, nodes
}

// extractHTMLTables finds <table> elements and converts them to Table nodes.
func extractHTMLTables(content string) (string, []Node) {
	tableOpenRe := regexp.MustCompile(`<table[^>]*>`)
	trRe := regexp.MustCompile(`(?s)<tr[^>]*>(.*?)</tr>`)
	cellRe := regexp.MustCompile(`(?s)<t[hd][^>]*>(.*?)</t[hd]>`)
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

// unwrapDivs removes <div> wrappers while preserving inner text content.
// This prevents indented HTML from being parsed as code blocks by goldmark.
func unwrapDivs(content string) string {
	divOpenRe := regexp.MustCompile(`<div[\s>][^>]*>`)
	for {
		loc := divOpenRe.FindStringIndex(content)
		if loc == nil {
			break
		}
		end := findMatchingTag(content, loc[1], "div")
		if end < 0 {
			break
		}
		inner := content[loc[1]:end]
		content = content[:loc[0]] + inner + content[end+len("</div>"):]
	}
	return content
}

// findMatchingTag finds the index of the closing </tag> that balances
// with the opening tag at startPos. Returns -1 if not found.
func findMatchingTag(s string, startPos int, tag string) int {
	depth := 1
	openRe := regexp.MustCompile(`<` + tag + `[\s>]`)
	closeRe := regexp.MustCompile(`</` + tag + `>`)

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

// extractCards finds <div class="card"> blocks and extracts header/body.
func extractCards(content string) []*Card {
	cardRe := regexp.MustCompile(`(?s)<div\s+class="card[^"]*">(.*?)</div>`)
	var cards []*Card

	for _, m := range cardRe.FindAllStringSubmatchIndex(content, -1) {
		inner := content[m[2]:m[3]]
		card := &Card{}

		// Extract h3 as header.
		h3Re := regexp.MustCompile(`(?s)<h3[^>]*>(.*?)</h3>`)
		if hm := h3Re.FindStringSubmatch(inner); hm != nil {
			card.Header = strings.TrimSpace(stripTags(hm[1]))
			inner = h3Re.ReplaceAllString(inner, "")
		}

		// Extract paragraphs.
		pRe := regexp.MustCompile(`(?s)<p[^>]*>(.*?)</p>`)
		for _, pm := range pRe.FindAllStringSubmatch(inner, -1) {
			text := strings.TrimSpace(stripTags(pm[1]))
			if text != "" {
				card.Body = append(card.Body, &Text{Content: text})
			}
		}

		// Remaining text after stripping all tags.
		remaining := strings.TrimSpace(stripTags(inner))
		if remaining != "" && len(card.Body) == 0 {
			card.Body = append(card.Body, &Text{Content: remaining})
		}

		cards = append(cards, card)
	}
	return cards
}

// cleanInlineNodes trims whitespace from inline nodes.
func cleanInlineNodes(nodes []InlineNode) []InlineNode {
	var cleaned []InlineNode
	for _, n := range nodes {
		if t, ok := n.(*Text); ok {
			trimmed := strings.TrimSpace(t.Content)
			if trimmed != "" {
				cleaned = append(cleaned, &Text{Content: trimmed})
			}
		} else {
			cleaned = append(cleaned, n)
		}
	}
	return cleaned
}

// convertNode translates a goldmark AST node into our slide AST node.
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

// convertList converts a goldmark list node.
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
		return nil
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
		case *Speaker:
			hasSpeaker = true
		case *Kicker:
			hasKicker = true
		}
	}

	if hasKicker || hasSpeaker {
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

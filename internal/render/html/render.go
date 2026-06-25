package html

import (
	"bytes"
	_ "embed"
	"fmt"
	"html/template"
	"strings"

	"github.com/slidr-cli/slidr/internal/parser"
	"github.com/slidr-cli/slidr/internal/theme"
)

//go:embed templates/shell.tmpl
var shellTemplate string

//go:embed templates/slide.tmpl
var slideTemplate string

//go:embed templates/card.tmpl
var cardTemplate string

// Render produces a complete HTML document from parsed slides and theme.
func Render(doc *parser.Document, t *theme.Theme) (string, error) {
	var slidesHTML []string
	for i, slide := range doc.Slides {
		html, err := renderSlide(&slide, i+1, t)
		if err != nil {
			return "", fmt.Errorf("slide %d: %w", i+1, err)
		}
		slidesHTML = append(slidesHTML, html)
	}

	tmpl, err := template.New("shell").Funcs(templateFuncs()).Parse(shellTemplate)
	if err != nil {
		return "", err
	}

	dims := doc.Meta.Size()
	w, h := dims[0], dims[1]
	ratio := float64(w) / float64(h)

	var buf bytes.Buffer
	data := map[string]interface{}{
		"Meta":       doc.Meta,
		"SlidesHTML": template.HTML(strings.Join(slidesHTML, "\n")),
		"ThemeCSS":   template.CSS(t.Full()),
		"SlideW":     w,
		"SlideH":     h,
		"Ratio":      fmt.Sprintf("%.4f", ratio),
	}
	if err := tmpl.Execute(&buf, data); err != nil {
		return "", err
	}
	return buf.String(), nil
}

func renderSlide(slide *parser.Slide, num int, t *theme.Theme) (string, error) {
	tmpl, err := template.New("slide").Funcs(templateFuncs()).Parse(slideTemplate)
	if err != nil {
		return "", err
	}

	var childrenHTML []string
	for _, child := range slide.Children {
		html, err := renderNode(child, t)
		if err != nil {
			return "", err
		}
		childrenHTML = append(childrenHTML, html)
	}

	var buf bytes.Buffer
	data := map[string]interface{}{
		"Num":         num,
		"Layout":      string(slide.Layout),
		"Children":    template.HTML(strings.Join(childrenHTML, "\n")),
		"Notes":       slide.Notes,
		"Footer":      slide.Meta.Footer,
		"Paginate":    slide.Meta.Paginate,
	}
	if err := tmpl.Execute(&buf, data); err != nil {
		return "", err
	}
	return buf.String(), nil
}

func renderNode(node parser.Node, t *theme.Theme) (string, error) {
	switch n := node.(type) {
	case *parser.Heading:
		tag := fmt.Sprintf("h%d", n.Level)
		content := renderInlineHTML(n.Content)
		return fmt.Sprintf("<%s>%s</%s>", tag, content, tag), nil
	case *parser.Paragraph:
		content := renderInlineHTML(n.Content)
		return fmt.Sprintf("<p>%s</p>", content), nil
	case *parser.Quote:
		content := renderInlineHTML(n.Text)
		return fmt.Sprintf("<div class=\"quote\">%s</div>", content), nil
	case *parser.Table:
		return renderTableHTML(n), nil
	case *parser.Grid:
		return renderGridHTML(n, t)
	case *parser.ListNode:
		return renderListHTML(n), nil
	case *parser.Kicker:
		return fmt.Sprintf("<div class=\"kicker\">%s</div>", template.HTMLEscapeString(n.Text)), nil
	case *parser.Subtitle:
		return fmt.Sprintf("<p class=\"subtitle\">%s</p>", template.HTMLEscapeString(n.Text)), nil
	case *parser.Speaker:
		return fmt.Sprintf("<div class=\"speaker\">%s<span>%s</span></div>",
			template.HTMLEscapeString(n.Name), template.HTMLEscapeString(n.Role)), nil
	case *parser.RawHTML:
		return n.Content, nil
	case *parser.AttrNode:
		return renderAttrNode(n), nil
	case *parser.Card:
		return renderCardHTML(n), nil
	default:
		return "", nil
	}
}

func renderAttrNode(n *parser.AttrNode) string {
	switch n.Type {
	case "kicker":
		return fmt.Sprintf("<div class=\"kicker\">%s</div>", template.HTMLEscapeString(n.Value))
	case "subtitle":
		return fmt.Sprintf("<p class=\"subtitle\">%s</p>", template.HTMLEscapeString(n.Value))
	case "tiny":
		return fmt.Sprintf("<p class=\"tiny\">%s</p>", template.HTMLEscapeString(n.Value))
	case "muted":
		return fmt.Sprintf("<p class=\"muted\">%s</p>", template.HTMLEscapeString(n.Value))
	case "speaker":
		name := n.Attrs["name"]
		role := n.Attrs["role"]
		if name == "" {
			name = n.Value
		}
		return fmt.Sprintf("<div class=\"speaker\">%s<span>%s</span></div>",
			template.HTMLEscapeString(name), template.HTMLEscapeString(role))
	default:
		// Generic: render as <div class="typename">value</div>
		attrs := ""
		for k, v := range n.Attrs {
			attrs += fmt.Sprintf(" data-%s=\"%s\"", k, template.HTMLEscapeString(v))
		}
		return fmt.Sprintf("<div class=\"%s\"%s>%s</div>",
			template.HTMLEscapeString(n.Type), template.HTMLEscapeString(attrs), template.HTMLEscapeString(n.Value))
	}
}

func renderCardHTML(card *parser.Card) string {
	var b strings.Builder
	cls := "card"
	if card.Class != "" {
		cls += " " + card.Class
	}
	b.WriteString(fmt.Sprintf("<div class=\"%s\">\n", cls))
	if card.Header != "" {
		b.WriteString("<h3>")
		b.WriteString(template.HTMLEscapeString(card.Header))
		b.WriteString("</h3>\n")
	}
	for _, inline := range card.Body {
		b.WriteString("<p>")
		b.WriteString(renderInlineHTML([]parser.InlineNode{inline}))
		b.WriteString("</p>\n")
	}
	b.WriteString("</div>")
	return b.String()
}

func renderGridHTML(grid *parser.Grid, t *theme.Theme) (string, error) {
	cols := grid.Cols
	if cols == 0 {
		cols = len(grid.Children)
	}
	if cols < 2 {
		cols = 2
	}

	cls := "grid"
	// Build column template and gap inline to ensure correct layout.
	style := fmt.Sprintf("grid-template-columns: repeat(%d, 1fr); gap: %dpx;", cols, grid.Gap)
	if grid.Class != "" {
		cls += " " + grid.Class
	}

	var children []string
	for _, child := range grid.Children {
		html, err := renderNode(child, t)
		if err != nil {
			return "", err
		}
		children = append(children, html)
	}
	return fmt.Sprintf("<div class=\"%s\" style=\"%s\">\n%s\n</div>", cls, style, strings.Join(children, "\n")), nil
}

func renderTableHTML(tbl *parser.Table) string {
	var b strings.Builder
	b.WriteString("<table>\n<thead>\n<tr>")
	for _, h := range tbl.Headers {
		b.WriteString("<th>")
		b.WriteString(template.HTMLEscapeString(h))
		b.WriteString("</th>")
	}
	b.WriteString("</tr>\n</thead>\n<tbody>\n")
	for _, row := range tbl.Rows {
		b.WriteString("<tr>")
		for _, cell := range row {
			b.WriteString("<td>")
			b.WriteString(template.HTMLEscapeString(cell))
			b.WriteString("</td>")
		}
		b.WriteString("</tr>\n")
	}
	b.WriteString("</tbody>\n</table>")
	return b.String()
}

func renderListHTML(list *parser.ListNode) string {
	var b strings.Builder
	b.WriteString("<ul>\n")
	for _, item := range list.Items {
		b.WriteString("<li>")
		b.WriteString(template.HTMLEscapeString(item))
		b.WriteString("</li>\n")
	}
	b.WriteString("</ul>")
	return b.String()
}

func renderInlineHTML(nodes []parser.InlineNode) string {
	var parts []string
	for _, n := range nodes {
		switch v := n.(type) {
		case *parser.Text:
			parts = append(parts, template.HTMLEscapeString(v.Content))
		case *parser.Strong:
			parts = append(parts, "<strong>"+renderInlineHTML(v.Children)+"</strong>")
		case *parser.CodeSpan:
			parts = append(parts, "<code>"+template.HTMLEscapeString(v.Content)+"</code>")
		case *parser.Link:
			parts = append(parts, fmt.Sprintf("<a href=\"%s\">%s</a>",
				template.HTMLEscapeString(v.URL), template.HTMLEscapeString(v.Text)))
		case *parser.SoftBreak:
			parts = append(parts, " ")
		case *parser.ImageNode:
			parts = append(parts, fmt.Sprintf("<img src=\"%s\" alt=\"%s\" />",
				template.HTMLEscapeString(v.URL), template.HTMLEscapeString(v.Alt)))
		}
	}
	return strings.Join(parts, "")
}

func templateFuncs() template.FuncMap {
	return template.FuncMap{}
}

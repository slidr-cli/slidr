package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/slidr-cli/slidr/internal/parser"
	"github.com/slidr-cli/slidr/internal/render/html"
	"github.com/slidr-cli/slidr/internal/render/pdf"
	"github.com/slidr-cli/slidr/internal/theme"
)

func main() {
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "slidr - markdown to styled PPTX + PDF\n\n")
		fmt.Fprintf(os.Stderr, "Usage: slidr build <file.md> [flags]\n\n")
		fmt.Fprintf(os.Stderr, "Flags:\n")
		flag.PrintDefaults()
	}

	if len(os.Args) < 2 {
		flag.Usage()
		os.Exit(1)
	}

	switch os.Args[1] {
	case "build":
		buildCmd()
	case "help", "-h", "--help":
		flag.Usage()
	default:
		fmt.Fprintf(os.Stderr, "unknown command: %s\n", os.Args[1])
		flag.Usage()
		os.Exit(1)
	}
}

type buildFlags struct {
	outputDir string
	pdfOnly   bool
	pptxOnly  bool
	theme     string
	debug     bool
}

func buildCmd() {
	flags := buildFlags{}

	fs := flag.NewFlagSet("build", flag.ExitOnError)
	fs.StringVar(&flags.outputDir, "o", "", "output directory (default: <input>/dist/)")
	fs.BoolVar(&flags.pdfOnly, "pdf", false, "generate PDF only")
	fs.BoolVar(&flags.pptxOnly, "pptx", false, "generate PPTX only")
	fs.StringVar(&flags.theme, "theme", "", "theme name (overrides frontmatter)")
	fs.BoolVar(&flags.debug, "debug", false, "dump parsed AST per slide")
	fs.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: slidr build <file.md> [flags]\n\n")
		fmt.Fprintf(os.Stderr, "Flags:\n")
		fs.PrintDefaults()
	}

	if len(os.Args) < 3 {
		fs.Usage()
		os.Exit(1)
	}

	fs.Parse(os.Args[2:])
	args := fs.Args()

	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "error: no input file specified")
		fs.Usage()
		os.Exit(1)
	}

	inputPath := args[0]
	f, err := os.Open(inputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
	defer f.Close()

	doc, err := parser.Parse(f)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	if flags.debug {
		dumpDebug(doc)
		if doc.Meta.Style != "" {
			fmt.Printf("\n=== THEME (raw) ===\n%d bytes\n", len(doc.Meta.Style))
		}
		return
	}

	fmt.Printf("Parsed %d slides\n\n", len(doc.Slides))
	for i, slide := range doc.Slides {
		fmt.Printf("Slide %d: layout=%s children=%d", i+1, slide.Layout, len(slide.Children))
		if slide.Notes != "" {
			notePreview := slide.Notes
			if len(notePreview) > 60 {
				notePreview = notePreview[:57] + "..."
			}
			fmt.Printf(" notes=%q", notePreview)
		}
		fmt.Println()

		for _, child := range slide.Children {
			fmt.Printf("  - %s", child.NodeType())
			switch n := child.(type) {
			case *parser.Heading:
				fmt.Printf(" L%d: %s", n.Level, renderInline(n.Content))
			case *parser.Paragraph:
				fmt.Printf(": %s", renderInline(n.Content))
			case *parser.Quote:
				fmt.Printf(": %s", renderInline(n.Text))
			case *parser.Table:
				fmt.Printf(" (%d cols x %d rows)", len(n.Headers), len(n.Rows))
			case *parser.Grid:
				fmt.Printf(" cols=%d children=%d", n.Cols, len(n.Children))
			case *parser.Kicker:
				fmt.Printf(": %s", n.Text)
			case *parser.Subtitle:
				fmt.Printf(": %s", n.Text)
			case *parser.Speaker:
				fmt.Printf(": %s / %s", n.Name, n.Role)
			case *parser.AttrNode:
				fmt.Printf(" %s: %s", n.Type, n.Value)
			case *parser.ListNode:
				fmt.Printf(" (%d items)", len(n.Items))
			}
			fmt.Println()
		}
		if len(slide.Children) > 0 {
			fmt.Println()
		}
	}

	_ = flags

	// Determine output directory: default to <input_dir>/dist/.
	outputDir := flags.outputDir
	if outputDir == "" {
		outputDir = filepath.Join(filepath.Dir(inputPath), "dist")
	}

	// Determine output name from input file.
	outName := strings.TrimSuffix(filepath.Base(inputPath), filepath.Ext(inputPath))

	// Resolve slide dimensions (pixels to inches at 96 DPI).
	dims := doc.Meta.Size(nil)
	widthIn := float64(dims[0]) / 96.0
	heightIn := float64(dims[1]) / 96.0

	genAll := !flags.pdfOnly && !flags.pptxOnly
	genPDF := genAll || flags.pdfOnly

	// Theme loading.
	t := theme.Load("", doc.Meta.Style)

	// HTML (always generated, needed for PDF).
	htmlStr, err := html.Render(doc, t)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error rendering HTML: %v\n", err)
		os.Exit(1)
	}

	// Ensure output directory exists.
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		fmt.Fprintf(os.Stderr, "error creating output dir: %v\n", err)
		os.Exit(1)
	}

	// Copy assets directory if it exists alongside the input file.
	assetsDir := filepath.Join(filepath.Dir(inputPath), "assets")
	if _, err := os.Stat(assetsDir); err == nil {
		destAssets := filepath.Join(outputDir, "assets")
		if err := copyDir(assetsDir, destAssets); err != nil {
			fmt.Fprintf(os.Stderr, "warning: could not copy assets: %v\n", err)
		}
	}

	if genPDF {
		pdfPath := filepath.Join(outputDir, outName+".pdf")
		pdfBuf, err := pdf.Render(htmlStr, widthIn, heightIn, filepath.Dir(inputPath))
		if err != nil {
			fmt.Fprintf(os.Stderr, "error rendering PDF: %v\n", err)
			os.Exit(1)
		}
		if err := os.WriteFile(pdfPath, pdfBuf, 0644); err != nil {
			fmt.Fprintf(os.Stderr, "error writing %s: %v\n", pdfPath, err)
			os.Exit(1)
		}
		fmt.Printf("Wrote %s (%d bytes)\n", pdfPath, len(pdfBuf))
	}

	// Always write HTML.
	htmlPath := filepath.Join(outputDir, outName+".html")
	if err := os.WriteFile(htmlPath, []byte(htmlStr), 0644); err != nil {
		fmt.Fprintf(os.Stderr, "error writing %s: %v\n", htmlPath, err)
		os.Exit(1)
	}
	fmt.Printf("Wrote %s (%d bytes)\n", htmlPath, len(htmlStr))

	if flags.pptxOnly && !genPDF {
		fmt.Fprintln(os.Stderr, "PPTX output not yet implemented (phase 4)")
		os.Exit(1)
	}

	if doc.Meta.Style != "" {
		fmt.Printf("Theme: style block injected (%d bytes)\n", len(doc.Meta.Style))
	}
}

func dumpDebug(doc *parser.Document) {
	fmt.Printf("=== DEBUG: %d slides ===\n\n", len(doc.Slides))
	for i, slide := range doc.Slides {
		fmt.Printf("--- Slide %d (layout=%s) ---\n", i+1, slide.Layout)
		for _, child := range slide.Children {
			fmt.Printf("  %s: ", child.NodeType())
			switch n := child.(type) {
			case *parser.Heading:
				fmt.Printf("L%d %q\n", n.Level, renderInlineStr(n.Content))
			case *parser.Paragraph:
				fmt.Printf("%q\n", renderInlineStr(n.Content))
			case *parser.Quote:
				fmt.Printf("%q\n", renderInlineStr(n.Text))
			case *parser.Table:
				fmt.Printf("headers=%v rows=%d\n", n.Headers, len(n.Rows))
			case *parser.Kicker:
				fmt.Printf("%q\n", n.Text)
			case *parser.Subtitle:
				fmt.Printf("%q\n", n.Text)
			case *parser.Speaker:
				fmt.Printf("%q / %q\n", n.Name, n.Role)
			case *parser.AttrNode:
				fmt.Printf("type=%q value=%q attrs=%v\n", n.Type, n.Value, n.Attrs)
			case *parser.RawHTML:
				s := n.Content
				if len(s) > 100 {
					s = s[:97] + "..."
				}
				fmt.Printf("%q\n", s)
			case *parser.ListNode:
				fmt.Printf("[%d items]\n", len(n.Items))
				for _, item := range n.Items {
					fmt.Printf("    - %s\n", item)
				}
			case *parser.Grid:
				fmt.Printf("cols=%d gap=%d [%d children]\n", n.Cols, n.Gap, len(n.Children))
				for _, gc := range n.Children {
					if card, ok := gc.(*parser.Card); ok {
						fmt.Printf("    card header=%q body=%q\n", card.Header, renderInlineStr(card.Body))
					}
				}
			default:
				fmt.Printf("\n")
			}
		}
		fmt.Println()
	}
}

func renderInlineStr(nodes []parser.InlineNode) string {
	var s string
	for _, n := range nodes {
		switch v := n.(type) {
		case *parser.Text:
			s += v.Content
		case *parser.Strong:
			s += "**"
			for _, c := range v.Children {
				if t, ok := c.(*parser.Text); ok {
					s += t.Content
				}
			}
			s += "**"
		case *parser.CodeSpan:
			s += "`" + v.Content + "`"
		case *parser.Link:
			s += v.Text
		case *parser.SoftBreak:
			s += " "
		}
	}
	return s
}

func renderInline(nodes []parser.InlineNode) string {
	var s string
	for _, n := range nodes {
		switch v := n.(type) {
		case *parser.Text:
			s += v.Content
		case *parser.Strong:
			s += "**"
			for _, c := range v.Children {
				if t, ok := c.(*parser.Text); ok {
					s += t.Content
				}
			}
			s += "**"
		case *parser.CodeSpan:
			s += "`" + v.Content + "`"
		case *parser.Link:
			s += v.Text
		case *parser.SoftBreak:
			s += " "
		}
	}
	if len(s) > 80 {
		s = s[:77] + "..."
	}
	return s
}

// copyDir recursively copies src to dst.
func copyDir(src, dst string) error {
	return filepath.Walk(src, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(src, path)
		target := filepath.Join(dst, rel)
		if info.IsDir() {
			return os.MkdirAll(target, info.Mode())
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		return os.WriteFile(target, data, info.Mode())
	})
}

package main

import (
	"flag"
	"fmt"
	"os"

	"github.com/slidr-cli/slidr/internal/parser"
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
	fs.StringVar(&flags.outputDir, "o", ".", "output directory")
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
			case *parser.Speaker:
				fmt.Printf(": %s / %s", n.Name, n.Role)
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
	fmt.Println("\nBuild: renderers not yet implemented (PDF + PPTX coming in phase 3-4)")
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
			case *parser.Speaker:
				fmt.Printf("%q / %q\n", n.Name, n.Role)
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

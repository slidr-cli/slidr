package parser

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

// ---- Meta / config ----

// Meta holds document-level frontmatter.
type Meta struct {
	Theme    string `yaml:"theme"`
	Title    string `yaml:"title"`
	Footer   string `yaml:"footer"`
	Paginate bool   `yaml:"paginate"`
	SizeRaw  string `yaml:"size"`  // "1920x1080", "16:9", "4:3", etc.
	Style    string `yaml:"style"` // raw CSS block for document-specific overrides
}

const (
	minSlideDim = 320
	maxSlideDim = 7680
	maxSizeLen  = 32
)

var (
	// All regexes are anchored (^...$) and Go's regexp is RE2-backed (linear time).
	// Combined with the 32-char length limit, these are safe against ReDoS.
	wxHRe   = regexp.MustCompile(`^(\d+)x(\d+)$`)
	arrayRe = regexp.MustCompile(`^\[(\d+),\s*(\d+)\]$`)
)

func clampDim(v int) int {
	if v < minSlideDim {
		return minSlideDim
	}
	if v > maxSlideDim {
		return maxSlideDim
	}
	return v
}

// Size resolves the size field into [width, height] pixels.
//   "1920x1080"  explicit WxH
//   "[1920,1080]" JSON array (legacy)
//   "16:9"  → 1280x720  (Marp default)
//   "4:3"   → 1024x768
//   "16:10" → 1280x800
func (m Meta) Size() [2]int {
	raw := strings.TrimSpace(m.SizeRaw)
	if raw == "" {
		return [2]int{1280, 720}
	}
	if len(raw) > maxSizeLen {
		return [2]int{1280, 720}
	}

	if m := wxHRe.FindStringSubmatch(raw); m != nil {
		w, _ := strconv.Atoi(m[1])
		h, _ := strconv.Atoi(m[2])
		if w > 0 && h > 0 {
			return [2]int{clampDim(w), clampDim(h)}
		}
	}

	if m := arrayRe.FindStringSubmatch(raw); m != nil {
		w, _ := strconv.Atoi(m[1])
		h, _ := strconv.Atoi(m[2])
		if w > 0 && h > 0 {
			return [2]int{clampDim(w), clampDim(h)}
		}
	}

	switch raw {
	case "16:9":
		return [2]int{1280, 720}
	case "4:3":
		return [2]int{1024, 768}
	case "16:10":
		return [2]int{1280, 800}
	}

	return [2]int{1280, 720}
}

// Resolution returns the size as a "WxH" string.
func (m Meta) Resolution() string {
	dims := m.Size()
	return fmt.Sprintf("%dx%d", dims[0], dims[1])
}



// ---- Document / Slide AST ----

// Document is the root node of a parsed markdown file.
type Document struct {
	Meta   Meta
	Slides []Slide
}

// Slide represents one presentation slide.
type Slide struct {
	Meta       Meta
	Layout     LayoutType
	Background Background
	Children   []Node
	Notes      string
}

// LayoutType identifies the slide's structural layout.
type LayoutType string

const (
	LayoutTitle   LayoutType = "title"
	LayoutContent LayoutType = "content"
	LayoutGrid2   LayoutType = "grid-2"
	LayoutGrid3   LayoutType = "grid-3"
	LayoutGrid4   LayoutType = "grid-4"
	LayoutColumns LayoutType = "columns"
	LayoutClosing LayoutType = "closing"
)

// Background defines a slide-level background (fill + optional decorative image).
type Background struct {
	Fill          string
	Image         string
	ImagePosition string
	ImageSize     string
	ImageOffset   string
	Opacity       float64
}

// ---- Block nodes ----

// Node is a block-level element in a slide.
type Node interface {
	NodeType() string
}

// Grid arranges children in n columns.
type Grid struct {
	Cols     int
	Gap      int
	Class    string // additional CSS classes
	Children []Node
}

func (Grid) NodeType() string { return "grid" }

// Card is a bordered container with optional header and tag.
type Card struct {
	Header string
	Body   []InlineNode
	Tag    *Tag
	Class  string // additional CSS classes
}

func (Card) NodeType() string { return "card" }

// Table is a structured table.
type Table struct {
	Headers   []string
	Rows      [][]string
	ColWidths []float64
}

func (Table) NodeType() string { return "table" }

// Stack is a vertical layered diagram.
type Stack struct {
	Layers   []StackLayer
	FocusIdx int
}

func (Stack) NodeType() string { return "stack" }

// StackLayer is one layer in a stack diagram.
type StackLayer struct {
	Name  string
	Desc  string
	Focus bool
}

// Columns arranges children side-by-side.
type Columns struct {
	Cols     int
	Children []Node
}

func (Columns) NodeType() string { return "columns" }

// Funnel is a vertical narrowing funnel diagram.
type Funnel struct {
	Steps []FunnelStep
}

func (Funnel) NodeType() string { return "funnel" }

// FunnelStep is one step in a funnel.
type FunnelStep struct {
	Label  string
	Sub    string
	Width  float64
	Accent bool
}

// Quote is a callout block with a left border.
type Quote struct {
	Text []InlineNode
	Size string
}

func (Quote) NodeType() string { return "quote" }

// Speaker is a name + role pair for title slides.
type Speaker struct {
	Name string
	Role string
}

func (Speaker) NodeType() string { return "speaker" }

// Kicker is a small label above the title.
type Kicker struct {
	Text string
}

func (Kicker) NodeType() string { return "kicker" }

// Subtitle is a secondary title line.
type Subtitle struct {
	Text string
}

func (Subtitle) NodeType() string { return "subtitle" }

// AttrNode is a generic key-value attribute node.
// Used for @-directives like @kicker, @speaker, @subtitle.
// The renderer maps Type to an HTML class or element.
type AttrNode struct {
	Type  string
	Attrs map[string]string
	Value string
	Class string // additional CSS classes from bare-word attributes
}

func (AttrNode) NodeType() string { return "attr" }

// Heading is a slide title or section heading.
type Heading struct {
	Level   int
	Content []InlineNode
}

func (Heading) NodeType() string { return "heading" }

// Paragraph is a block of inline content.
type Paragraph struct {
	Content []InlineNode
}

func (Paragraph) NodeType() string { return "paragraph" }

// RawHTML is pass-through HTML the parser can't classify.
type RawHTML struct {
	Content string
}

func (RawHTML) NodeType() string { return "rawhtml" }

// ListNode is a bullet or ordered list.
type ListNode struct {
	Items []string
}

func (ListNode) NodeType() string { return "list" }

// ---- Inline nodes ----

// InlineNode is inline-level markup.
type InlineNode interface {
	inlineNodeType() string
}

// Text is plain text content.
type Text struct {
	Content string
}

func (Text) inlineNodeType() string { return "text" }

// Strong is bold text.
type Strong struct {
	Children []InlineNode
}

func (Strong) inlineNodeType() string { return "strong" }

// CodeSpan is inline code.
type CodeSpan struct {
	Content string
}

func (CodeSpan) inlineNodeType() string { return "code" }

// Link is an inline hyperlink.
type Link struct {
	URL  string
	Text string
}

func (Link) inlineNodeType() string { return "link" }

// SoftBreak is a line break.
type SoftBreak struct{}

func (SoftBreak) inlineNodeType() string { return "softbreak" }

// ImageNode is an inline image (from markdown ![alt](url)).
type ImageNode struct {
	URL string
	Alt string
}

func (ImageNode) inlineNodeType() string { return "image" }

// Tag is a colored pill badge.
type Tag struct {
	Text  string
	Color TagColor
}

func (Tag) inlineNodeType() string { return "tag" }

// TagColor is a named color for tags.
type TagColor string

const (
	TagGreen  TagColor = "green"
	TagCyan   TagColor = "cyan"
	TagYellow TagColor = "yellow"
	TagRed    TagColor = "red"
)

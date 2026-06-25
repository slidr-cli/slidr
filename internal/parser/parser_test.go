package parser

import (
	"strings"
	"testing"
)

func TestParseTable(t *testing.T) {
	input := `---
theme: test
---

## heading

| a | b | c |
|---|---|---|
| 1 | 2 | 3 |

done`

	// Simulate what parseSlideContent does.
	cleaned, _ := extractKnownHTML(input)
	t.Logf("cleaned content:\n---\n%s\n---", cleaned)

	doc, err := Parse(strings.NewReader(input))
	if err != nil {
		t.Fatal(err)
	}
	if len(doc.Slides) != 1 {
		t.Fatalf("expected 1 slide, got %d", len(doc.Slides))
	}
	slide := doc.Slides[0]
	found := false
	for _, child := range slide.Children {
		t.Logf("  child: %s", child.NodeType())
		if _, ok := child.(*Table); ok {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected a Table node, got: %v", nodeTypes(slide.Children))
	}
}

func TestParseSlides(t *testing.T) {
	input := `---
theme: dynamia
---

# Title Slide

<div class="kicker">test kicker</div>

<div class="speaker">Name<span>Role</span></div>

---

<!--
speaker notes here
-->

## Content Slide

<div class="quote">A quote here</div>

| col1 | col2 |
|------|------|
| a    | b    |

- item 1
- item 2`

	doc, err := Parse(strings.NewReader(input))
	if err != nil {
		t.Fatal(err)
	}
	if len(doc.Slides) != 2 {
		t.Fatalf("expected 2 slides, got %d", len(doc.Slides))
	}

	s1 := doc.Slides[0]
	if s1.Layout != LayoutTitle {
		t.Errorf("slide 1 layout: got %s, want title", s1.Layout)
	}

	s2 := doc.Slides[1]
	if s2.Notes != "speaker notes here" {
		t.Errorf("slide 2 notes: got %q, want 'speaker notes here'", s2.Notes)
	}
	// Verify grid detection from cards.
	hasGrid := false
	for _, c := range s2.Children {
		if c.NodeType() == "grid" {
			hasGrid = true
		}
	}
	if hasGrid {
		t.Log("slide 2 has grid (from cards)")
	}
}

func nodeTypes(nodes []Node) []string {
	var types []string
	for _, n := range nodes {
		types = append(types, n.NodeType())
	}
	return types
}

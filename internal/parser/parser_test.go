package parser

import (
	"strings"
	"testing"
)

func TestFencedGrid(t *testing.T) {
	input := `---
theme: test
---

::: grid {cols=2}
::: card{}
### Card One

Body one.
:::

::: card{tag="green"}
### Card Two

Body two.
:::
:::`

	doc, err := Parse(strings.NewReader(input))
	if err != nil {
		t.Fatal(err)
	}
	if len(doc.Slides) != 1 {
		t.Fatalf("expected 1 slide, got %d", len(doc.Slides))
	}
	slide := doc.Slides[0]

	var grid *Grid
	for _, c := range slide.Children {
		if g, ok := c.(*Grid); ok {
			grid = g
			break
		}
	}
	if grid == nil {
		t.Fatal("no grid found in slide")
	}
	if grid.Cols != 2 {
		t.Errorf("cols = %d, want 2", grid.Cols)
	}
	if len(grid.Children) != 2 {
		t.Fatalf("grid children = %d, want 2", len(grid.Children))
	}

	card1, ok := grid.Children[0].(*Card)
	if !ok {
		t.Fatalf("child 0 is %T, want Card", grid.Children[0])
	}
	if card1.Header != "Card One" {
		t.Errorf("card1 header = %q", card1.Header)
	}
	if len(card1.Body) != 1 || card1.Body[0].(*Text).Content != "Body one." {
		t.Errorf("card1 body = %v", card1.Body)
	}

	card2 := grid.Children[1].(*Card)
	if card2.Tag == nil || card2.Tag.Color != TagGreen {
		t.Errorf("card2 tag = %v", card2.Tag)
	}
	if card2.Header != "Card Two" {
		t.Errorf("card2 header = %q", card2.Header)
	}
}

func TestFencedCardWithoutHeader(t *testing.T) {
	input := `---
theme: test
---

::: card{tag="cyan"}
Just a body with no heading.
:::`

	doc, err := Parse(strings.NewReader(input))
	if err != nil {
		t.Fatal(err)
	}
	slide := doc.Slides[0]
	for _, c := range slide.Children {
		if card, ok := c.(*Card); ok {
			if card.Tag == nil || card.Tag.Color != TagCyan {
				t.Errorf("tag = %v", card.Tag)
			}
			if len(card.Body) != 1 {
				t.Errorf("body len = %d", len(card.Body))
			}
			return
		}
	}
	t.Fatal("no card found")
}

func TestGenericDirective(t *testing.T) {
	input := `---
theme: test
---

@kicker 新员工培训

# Title

@subtitle A subtitle here

@speaker name=John role=Engineer

Some content.`

	doc, err := Parse(strings.NewReader(input))
	if err != nil {
		t.Fatal(err)
	}
	slide := doc.Slides[0]

	var kicker, subtitle, speaker *AttrNode
	for _, c := range slide.Children {
		if a, ok := c.(*AttrNode); ok {
			switch a.Type {
			case "kicker":
				kicker = a
			case "subtitle":
				subtitle = a
			case "speaker":
				speaker = a
			}
		}
	}

	if kicker == nil || kicker.Value != "新员工培训" {
		t.Errorf("kicker = %v", kicker)
	}
	if subtitle == nil || subtitle.Value != "A subtitle here" {
		t.Errorf("subtitle = %v", subtitle)
	}
	if speaker == nil || speaker.Attrs["name"] != "John" || speaker.Attrs["role"] != "Engineer" {
		t.Errorf("speaker = %v", speaker)
	}

	// Generic unknown directive should also parse.
	if slide.Layout != LayoutTitle {
		t.Errorf("layout = %s, want title", slide.Layout)
	}
}

func TestGenericDirectiveUnknown(t *testing.T) {
	input := `---
theme: test
---

@custom-badge label=NEW Some text here

Content.`

	doc, _ := Parse(strings.NewReader(input))
	slide := doc.Slides[0]
	for _, c := range slide.Children {
		if a, ok := c.(*AttrNode); ok {
			if a.Type != "custom-badge" {
				t.Errorf("type = %q", a.Type)
			}
			if a.Attrs["label"] != "NEW" {
				t.Errorf("attrs = %v", a.Attrs)
			}
			if a.Value != "Some text here" {
				t.Errorf("value = %q", a.Value)
			}
			return
		}
	}
	t.Fatal("no AttrNode found")
}

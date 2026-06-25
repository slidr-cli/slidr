// Package theme holds raw CSS for slidr's presentation theme.
// CSS parsing is delegated to the browser (for PDF) or to the PPTX mapper (Phase 4).
package theme

// Theme is a raw CSS block from the frontmatter style: field.
type Theme struct {
	Raw    string // the full style: block as-is
	Base   string // built-in default theme CSS (embedded)
}

// Load returns a Theme from a frontmatter style block.
func Load(baseCSS, overrideCSS string) *Theme {
	return &Theme{
		Base: baseCSS,
		Raw:  overrideCSS,
	}
}

// Full returns base + override CSS concatenated.
func (t *Theme) Full() string {
	return t.Base + "\n" + t.Raw
}

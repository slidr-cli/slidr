// Package pdf renders HTML to PDF via headless Chrome.
package pdf

import (
	"context"
	"encoding/base64"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/chromedp/cdproto/page"
	"github.com/chromedp/chromedp"
)

// Render converts an HTML string to a PDF byte slice.
// baseDir is the directory to resolve relative URLs against.
func Render(htmlStr string, widthIn, heightIn float64, baseDir string) ([]byte, error) {
	ctx, cancel := chromedp.NewContext(context.Background())
	defer cancel()

	ctx, cancel = context.WithTimeout(ctx, 30*time.Second)
	defer cancel()

	// Embed local images as base64 so they work without file:// access.
	if baseDir != "" {
		htmlStr = embedLocalImages(htmlStr, baseDir)
	}

	var buf []byte

	err := chromedp.Run(ctx,
		chromedp.Navigate("about:blank"),
		chromedp.ActionFunc(func(ctx context.Context) error {
			frameTree, err := page.GetFrameTree().Do(ctx)
			if err != nil {
				return err
			}
			return page.SetDocumentContent(frameTree.Frame.ID, htmlStr).Do(ctx)
		}),
		chromedp.Sleep(500*time.Millisecond),
		chromedp.ActionFunc(func(ctx context.Context) error {
			var err error
			buf, _, err = page.PrintToPDF().
				WithPrintBackground(true).
				WithPaperWidth(widthIn).
				WithPaperHeight(heightIn).
				WithMarginTop(0).
				WithMarginBottom(0).
				WithMarginLeft(0).
				WithMarginRight(0).
				Do(ctx)
			return err
		}),
	)
	if err != nil {
		return nil, fmt.Errorf("chromedp: %w", err)
	}

	return buf, nil
}

func injectBaseTag(html, baseURL string) string {
	return strings.Replace(html, "<head>", "<head><base href=\""+baseURL+"\">", 1)
}

func embedLocalImages(html, baseDir string) string {
	re := regexp.MustCompile(`src="(\./[^"]+)"`)
	return re.ReplaceAllStringFunc(html, func(match string) string {
		// Extract the relative path.
		sub := re.FindStringSubmatch(match)
		if sub == nil {
			return match
		}
		relPath := sub[1]
		absPath := filepath.Join(baseDir, relPath)
		data, err := os.ReadFile(absPath)
		if err != nil {
			return match
		}
		ext := strings.ToLower(filepath.Ext(absPath))
		mime := "image/png"
		switch ext {
		case ".jpg", ".jpeg":
			mime = "image/jpeg"
		case ".svg":
			mime = "image/svg+xml"
		case ".gif":
			mime = "image/gif"
		}
		b64 := base64.StdEncoding.EncodeToString(data)
		return fmt.Sprintf("src=\"data:%s;base64,%s\"", mime, b64)
	})
}

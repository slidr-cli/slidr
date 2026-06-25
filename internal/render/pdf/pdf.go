// Package pdf renders HTML to PDF via headless Chrome.
package pdf

import (
	"context"
	"fmt"
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

	var buf []byte

	err := chromedp.Run(ctx,
		chromedp.Navigate("about:blank"),
		chromedp.ActionFunc(func(ctx context.Context) error {
			frameTree, err := page.GetFrameTree().Do(ctx)
			if err != nil {
				return err
			}
			htmlWithBase := htmlStr
			if baseDir != "" {
				htmlWithBase = injectBaseTag(htmlStr, "file://"+baseDir+"/")
			}
			return page.SetDocumentContent(frameTree.Frame.ID, htmlWithBase).Do(ctx)
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

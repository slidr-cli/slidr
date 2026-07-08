use crate::parser::ast::*;
use std::fmt::Write;

pub fn render(doc: &Document, theme_css: &str, logo: Option<&str>) -> String {
    let dims = doc.meta.dimensions();
    let ratio = dims.0 as f64 / dims.1 as f64;

    let mut slides_html = String::new();
    for (i, slide) in doc.slides.iter().enumerate() {
        let num = i + 1;
        let layout = match slide.layout {
            LayoutType::Title => "title",
            LayoutType::Grid2 => "grid-2",
            LayoutType::Grid3 => "grid-3",
            LayoutType::Grid4 => "grid-4",
            LayoutType::Content => "content",
        };
        let children = slide.children.iter()
            .filter_map(|n| render_node(n))
            .collect::<Vec<_>>()
            .join("\n");

        let footer = doc.meta.footer.as_deref().unwrap_or("");
        let paginate = doc.meta.paginate.unwrap_or(false);
        let mut footer_html = String::new();
        if !footer.is_empty() {
            write!(footer_html, "<footer>{}{}</footer>",
                footer,
                if paginate { format!(" &mdash; {}", num) } else { String::new() }
            ).unwrap();
        }

        write!(slides_html, r#"<section class="slide layout-{}"{}>
{}{}
</section>"#,
            layout,
            if slide.notes.is_empty() { String::new() } else { format!(r#" data-notes="{}""#, slide.notes) },
            children,
            footer_html,
        ).unwrap();
    }

    let logo_css = logo.map(|l| format!(
        r#"section::before {{
  content: "";
  position: absolute;
  top: 4%;
  right: 5%;
  width: 14%;
  height: 0;
  padding-bottom: 6%;
  background: url("{}") center / contain no-repeat;
  opacity: 0.92;
}}"#, l
    )).unwrap_or_default();

    let title = doc.meta.title.as_deref().unwrap_or("Presentation");

    format!(include_str!("../../templates/shell.html"),
        title = title,
        ratio = ratio,
        slide_w = dims.0,
        slide_h = dims.1,
        theme_css = theme_css,
        logo_css = logo_css,
        slides = slides_html,
    )
}

fn render_node(node: &Node) -> Option<String> {
    match node {
        Node::Heading(h) => {
            let tag = format!("h{}", h.level);
            let content = render_inline(&h.content);
            Some(format!("<{}>{}</{}>", tag, content, tag))
        }
        Node::Paragraph(inlines) => {
            Some(format!("<p>{}</p>", render_inline(inlines)))
        }
        Node::Quote(inlines) => {
            Some(format!("<div class=\"quote\">{}</div>", render_inline(inlines)))
        }
        Node::Table(t) => {
            let mut s = String::from("<table>\n<thead>\n<tr>");
            for h in &t.headers {
                write!(s, "<th>{}</th>", html_escape(h)).unwrap();
            }
            s.push_str("</tr>\n</thead>\n<tbody>\n");
            for row in &t.rows {
                s.push_str("<tr>");
                for cell in row {
                    write!(s, "<td>{}</td>", html_escape(cell)).unwrap();
                }
                s.push_str("</tr>\n");
            }
            s.push_str("</tbody>\n</table>");
            Some(s)
        }
        Node::Grid(g) => {
            let cols = if g.cols == 0 { g.children.len().max(2) } else { g.cols };
            let mut cls = String::from("grid");
            if !g.class.is_empty() {
                write!(cls, " {}", g.class).unwrap();
            }
            let style = format!("grid-template-columns: repeat({}, 1fr); gap: 16px;", cols);
            let children = g.children.iter()
                .filter_map(|n| render_node(n))
                .collect::<Vec<_>>()
                .join("\n");
            Some(format!(r#"<div class="{}" style="{}">{}</div>"#, cls, style, children))
        }
        Node::Card(c) => {
            let mut cls = String::from("card");
            if !c.class.is_empty() {
                write!(cls, " {}", c.class).unwrap();
            }
            let mut s = format!("<div class=\"{}\">\n", cls);
            if !c.header.is_empty() {
                write!(s, "<h3>{}</h3>\n", c.header).unwrap();
            }
            for line in &c.body {
                write!(s, "<p>{}</p>\n", line).unwrap();
            }
            s.push_str("</div>");
            Some(s)
        }
        Node::List(items) => {
            let mut s = String::from("<ul>\n");
            for item in items {
                write!(s, "<li>{}</li>\n", item).unwrap();
            }
            s.push_str("</ul>");
            Some(s)
        }
        Node::Attr(a) => {
            match a.typ.as_str() {
                "kicker" => Some(format!("<div class=\"kicker\">{}</div>", a.value)),
                "subtitle" => Some(format!("<p class=\"subtitle\">{}</p>", a.value)),
                "speaker" => {
                    let name = a.attrs.iter().find(|(k, _)| k == "name").map(|(_, v)| v.clone()).unwrap_or_default();
                    let role = a.attrs.iter().find(|(k, _)| k == "role").map(|(_, v)| v.clone()).unwrap_or_default();
                    Some(format!("<div class=\"speaker\">{}<span>{}</span></div>", name, role))
                }
                "tiny" => Some(format!("<p class=\"tiny\">{}</p>", a.value)),
                "muted" => Some(format!("<p class=\"muted\">{}</p>", a.value)),
                _ => Some(format!("<div class=\"{}\">{}</div>", a.typ, a.value)),
            }
        }
    }
}

fn render_inline(nodes: &[Inline]) -> String {
    let mut s = String::new();
    for n in nodes {
        match n {
            Inline::Text(t) => s.push_str(&html_escape(t)),
            Inline::Strong(children) => {
                write!(s, "<strong>{}</strong>", render_inline(children)).unwrap();
            }
            Inline::Code(c) => write!(s, "<code>{}</code>", html_escape(c)).unwrap(),
            Inline::SoftBreak => s.push(' '),
            _ => {}
        }
    }
    s
}

fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

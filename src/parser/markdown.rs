use pulldown_cmark::{Event, Options, Parser, Tag, TagEnd};
use crate::parser::ast::*;

pub fn parse_markdown(input: &str) -> Document {
    let (fm, body) = split_frontmatter(input);
    let meta: Meta = serde_yaml::from_str(&fm).unwrap_or_default();
    let slides = split_slides(&body);
    Document { meta, slides }
}

fn split_frontmatter(input: &str) -> (String, String) {
    let t = input.trim_start();
    if !t.starts_with("---") { return (String::new(), input.to_string()); }
    let after = &t[3..];
    if let Some(end) = after.find("\n---") {
        (after[..end].trim().to_string(), after[end + 4..].to_string())
    } else {
        (String::new(), input.to_string())
    }
}

fn split_slides(body: &str) -> Vec<Slide> {
    body.split("\n---\n")
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(parse_slide)
        .collect()
}

fn parse_slide(content: &str) -> Slide {
    let (notes, content) = extract_notes(content);
    let opts = Options::ENABLE_TABLES;
    let parser = Parser::new_ext(&content, opts);

    let mut nodes: Vec<Node> = Vec::new();
    let mut buf = String::new();
    let mut h_level = 0u8;
    let mut in_quote = false;
    let mut hdrs: Vec<String> = Vec::new();
    let mut rows: Vec<Vec<String>> = Vec::new();
    let mut cells: Vec<String> = Vec::new();
    let mut is_hdr = true;
    let mut list: Vec<String> = Vec::new();
    let mut in_table = false;

    for ev in parser { let _ = std::fs::write("/tmp/pd_log", format!("EVT: {:?}\n", ev));
        match ev {
            Event::Start(t) => match t {
                Tag::Heading { level, .. } => h_level = level as u8,
                Tag::BlockQuote(..) => in_quote = true,
                Tag::Table(_) => { let _ = std::fs::write("/tmp/pd_log", "TABLE_START\n"); in_table = true; is_hdr = true; }
                Tag::TableHead => is_hdr = true,
                Tag::TableRow => cells.clear(),
                _ => {}
            },
            Event::End(t) => match t {
                TagEnd::Heading(..) => { push_h(&mut nodes, h_level, &mut buf); h_level = 0; }
                TagEnd::Paragraph => { push_pq(&mut nodes, in_quote, &mut buf); }
                TagEnd::BlockQuote(_) => in_quote = false,
                TagEnd::Table => { let _ = std::fs::write("/tmp/pd_log", "TABLE_END\n"); if !hdrs.is_empty() { nodes.push(Node::Table(Table { headers: std::mem::take(&mut hdrs), rows: std::mem::take(&mut rows) })); } in_table = false; }
                TagEnd::TableHead => is_hdr = false,
                TagEnd::TableRow => { if !cells.is_empty() { if is_hdr { hdrs = std::mem::take(&mut cells); } else { rows.push(std::mem::take(&mut cells)); } } }
                TagEnd::List(..) => { if !list.is_empty() { nodes.push(Node::List(std::mem::take(&mut list))); } }
                TagEnd::Item => { let s = trim(&buf); buf.clear(); if !s.is_empty() { list.push(s); } }
                _ => {}
            },
            Event::Text(t) => { if in_table { let _ = std::fs::write("/tmp/pd_log", format!("TABLE_TEXT: {}\n", t)); cells.push(t.to_string()); } else { buf.push_str(&t); } }
            Event::Code(c) => { if in_table { if let Some(last) = cells.last_mut() { last.push('`'); last.push_str(&c); last.push('`'); } } else { buf.push('`'); buf.push_str(&c); buf.push('`'); } }
            Event::SoftBreak | Event::HardBreak => { if !in_table { buf.push(' '); } }
            _ => {}
        }
    }

    let s = trim(&buf);
    if !s.is_empty() { nodes.push(Node::Paragraph(vec![Inline::Text(s)])); }

    let layout = detect(&nodes);
    Slide { layout, children: nodes, notes }
}

fn push_h(nodes: &mut Vec<Node>, level: u8, buf: &mut String) {
    let s = trim(buf); buf.clear();
    if !s.is_empty() { nodes.push(Node::Heading(Heading { level, content: vec![Inline::Text(s)] })); }
}

fn push_pq(nodes: &mut Vec<Node>, in_quote: bool, buf: &mut String) {
    let s = trim(buf); buf.clear();
    if !s.is_empty() {
        nodes.push(if in_quote { Node::Quote(vec![Inline::Text(s)]) } else { Node::Paragraph(vec![Inline::Text(s)]) });
    }
}

fn trim(s: &str) -> String { s.trim().to_string() }

fn extract_notes(content: &str) -> (String, String) {
    let t = content.trim_start();
    if let Some(start) = t.find("<!--") {
        if t[..start].trim().is_empty() {
            let rest = &t[start + 4..];
            if let Some(end) = rest.find("-->") {
                return (rest[..end].trim().to_string(), rest[end + 3..].trim().to_string());
            }
        }
    }
    (String::new(), content.to_string())
}

fn detect(ns: &[Node]) -> LayoutType {
    for n in ns { if let Node::Heading(h) = n { if h.level == 1 { return LayoutType::Title; } } }
    LayoutType::Content
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_heading() {
        let d = parse_markdown("---\ntheme:t\n---\n\n# Title\n\ntext");
        assert_eq!(d.slides.len(), 1);
        assert!(d.slides[0].children.iter().any(|n| matches!(n, Node::Heading(_))));
    }

    #[test]
    fn test_table() {
        let d = parse_markdown("---\ntheme:t\n---\n\n|a|b|\n|---|---|\n|1|2|");
        assert_eq!(d.slides.len(), 1);
        assert!(d.slides[0].children.iter().any(|n| matches!(n, Node::Table(_))));
    }

    #[test]
    fn test_quote() {
        let d = parse_markdown("---\ntheme:t\n---\n\n> quoted");
        assert_eq!(d.slides.len(), 1);
        assert!(d.slides[0].children.iter().any(|n| matches!(n, Node::Quote(_))));
    }
}

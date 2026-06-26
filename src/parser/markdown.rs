use comrak::{
    Arena, Options,
    arena_tree::NodeEdge,
    nodes::{AstNode as CNode, NodeValue},
    parse_document,
};
use crate::parser::ast::*;

pub fn parse_markdown(input: &str) -> Document {
    let (frontmatter, body) = split_frontmatter(input);
    let meta: Meta = serde_yaml::from_str(&frontmatter).unwrap_or_default();
    let slides = split_slides(&body, &meta);
    Document { meta, slides }
}

fn split_frontmatter(input: &str) -> (String, String) {
    let trimmed = input.trim_start();
    if !trimmed.starts_with("---") {
        return (String::new(), input.to_string());
    }
    let after = &trimmed[3..];
    if let Some(end) = after.find("\n---") {
        let fm = after[..end].trim().to_string();
        let body = after[end + 4..].to_string();
        (fm, body)
    } else {
        (String::new(), input.to_string())
    }
}

fn split_slides(body: &str, _meta: &Meta) -> Vec<Slide> {
    body.split("\n---\n")
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|content| parse_slide(content))
        .collect()
}

fn parse_slide(content: &str) -> Slide {
    let (notes, content) = extract_notes(content);
    let (content, directives) = extract_directives(&content);
    let (content, fenced) = extract_fenced(&content);

    let arena = Arena::new();
    let mut opts = Options::default();
    opts.extension.table = true;
    let root = parse_document(&arena, &content, &opts);

    // Single ordered list: comrak first (headings/quotes/tables/paragraphs),
    // then fenced blocks (grids/cards), then directives (@kicker/@tiny/etc).
    // This preserves the common case: content → structure → annotations.
    let mut nodes = comrak_nodes(&arena, root);
    nodes.extend(fenced);
    nodes.extend(directives);

    let layout = detect_layout(&nodes);
    Slide { layout, children: nodes, notes }
}

fn comrak_nodes<'a>(_arena: &'a Arena, root: &'a CNode<'a>) -> Vec<Node> {
    let mut nodes = Vec::new();
    for edge in root.traverse() {
        if let NodeEdge::Start(node) = edge {
            let data = node.data();
            match &data.value {
                NodeValue::Heading(h) => {
                    nodes.push(Node::Heading(Heading {
                        level: u8::try_from(h.level).unwrap_or(1),
                        content: vec![Inline::Text(node_text(&node))],
                    }));
                }
                NodeValue::Paragraph => {
                    let text = node_text(&node);
                    if !text.is_empty() && !text.starts_with('<') {
                        nodes.push(Node::Paragraph(vec![Inline::Text(text)]));
                    }
                }
                NodeValue::BlockQuote => {
                    let text = node_text(&node);
                    if !text.is_empty() {
                        nodes.push(Node::Quote(vec![Inline::Text(text)]));
                    }
                }
                NodeValue::Table(_) => {
                    nodes.push(extract_table(&node));
                }
                NodeValue::List(_) => {
                    let items = extract_list(&node);
                    if !items.is_empty() {
                        nodes.push(Node::List(items));
                    }
                }
                _ => {}
            }
        }
    }
    nodes
}

fn node_text<'a>(node: &'a CNode<'a>) -> String {
    let mut s = String::new();
    for edge in node.traverse() {
        if let NodeEdge::Start(child) = edge {
            if let NodeValue::Text(t) = &child.data().value {
                s.push_str(t);
            }
        }
    }
    s.trim().to_string()
}

fn extract_table<'a>(node: &'a CNode<'a>) -> Node {
    let mut headers = Vec::new();
    let mut rows = Vec::new();
    let mut first = true;

    for edge in node.traverse() {
        if let NodeEdge::Start(child) = edge {
            match &child.data().value {
                NodeValue::TableRow(_) => {
                    let mut cells = Vec::new();
                    for ce in child.traverse() {
                        if let NodeEdge::Start(cell) = ce {
                            if let NodeValue::TableCell = cell.data().value {
                                cells.push(node_text(&cell));
                            }
                        }
                    }
                    if !cells.is_empty() {
                        if first { headers = cells; first = false; }
                        else { rows.push(cells); }
                    }
                }
                _ => {}
            }
        }
    }

    Node::Table(Table { headers, rows })
}

fn extract_list<'a>(node: &'a CNode<'a>) -> Vec<String> {
    let mut items = Vec::new();
    for edge in node.traverse() {
        if let NodeEdge::Start(child) = edge {
            if let NodeValue::Item(_) = &child.data().value {
                let text = node_text(&child);
                if !text.is_empty() {
                    items.push(text);
                }
            }
        }
    }
    items
}

fn extract_notes(content: &str) -> (String, String) {
    let trimmed = content.trim_start();
    if trimmed.starts_with("<!--") {
        if let Some(end) = trimmed.find("-->") {
            let notes = trimmed[4..end].trim().to_string();
            let rest = trimmed[end + 3..].trim().to_string();
            return (notes, rest);
        }
    }
    (String::new(), content.to_string())
}

fn extract_directives(content: &str) -> (String, Vec<Node>) {
    let mut nodes = Vec::new();
    let mut result = String::new();

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('@') && !trimmed.starts_with("@@") {
            let rest = &trimmed[1..];
            if let Some(space) = rest.find(' ') {
                let typ = &rest[..space];
                let value = rest[space + 1..].trim();
                let mut attrs = Vec::new();
                let mut remaining = String::new();
                for word in value.split_whitespace() {
                    if let Some(eq) = word.find('=') {
                        attrs.push((word[..eq].to_string(), word[eq + 1..].trim_matches('"').to_string()));
                    }
                }
                if attrs.is_empty() { remaining = value.to_string(); }
                nodes.push(Node::Attr(AttrNode { typ: typ.to_string(), value: remaining, attrs }));
                continue;
            }
        }
        result.push_str(line);
        result.push('\n');
    }
    (result, nodes)
}

fn extract_fenced(content: &str) -> (String, Vec<Node>) {
    let mut nodes = Vec::new();
    let mut result = String::new();
    let mut lines_buf: Vec<String> = Vec::new();
    let mut stack: Vec<(String, Vec<Node>, Vec<(String, String)>)> = Vec::new();

    for line in content.lines() {
        let t = line.trim();
        if t.starts_with(":::") && !t.starts_with("::::") {
            if t == ":::" {
                if let Some((ftype, mut children, attrs)) = stack.pop() {
                    let node = build_fenced(&ftype, &lines_buf, &mut children, &attrs);
                    if let Some(n) = node {
                        if let Some(top) = stack.last_mut() { top.1.push(n); }
                        else { nodes.push(n); }
                    }
                }
                lines_buf.clear();
                continue;
            }
            let rest = t[3..].trim_start();
            let parts: Vec<&str> = rest.splitn(2, ' ').collect();
            if parts.is_empty() || parts[0].is_empty() { continue; }
            let typ = parts[0].trim_end_matches('{');
            let raw = parts.get(1).unwrap_or(&"").trim_matches(|c: char| c == '{' || c == '}');
            let attrs = parse_attrs(raw);
            lines_buf.clear();
            stack.push((typ.to_string(), Vec::new(), attrs));
            continue;
        }
        if stack.is_empty() {
            result.push_str(line);
            result.push('\n');
        } else {
            lines_buf.push(line.to_string());
        }
    }
    (result, nodes)
}

fn build_fenced(typ: &str, lines: &[String], children: &mut Vec<Node>, attrs: &[(String, String)]) -> Option<Node> {
    match typ {
        "card" => {
            let (header, body) = parse_card_body(lines);
            let mut class = String::new();
            for (k, v) in attrs {
                if k == "class" { class = v.clone(); }
                else if k != "tag" { if !class.is_empty() { class.push(' '); } class.push_str(k); }
            }
            Some(Node::Card(Card { header, body, tag: None, class }))
        }
        "grid" => {
            let cols = attrs.iter().find(|(k,_)| k == "cols").and_then(|(_,v)| v.parse().ok()).unwrap_or(children.len().max(2));
            let class = attrs.iter().find(|(k,_)| k == "class").map(|(_,v)| v.clone()).unwrap_or_default();
            Some(Node::Grid(Grid { cols, class, children: std::mem::take(children) }))
        }
        _ => None,
    }
}

fn parse_card_body(lines: &[String]) -> (String, Vec<String>) {
    let mut header = String::new();
    let mut body = Vec::new();
    for line in lines {
        let t = line.trim();
        if t.starts_with("### ") { header = t[4..].to_string(); }
        else if !t.is_empty() { body.push(t.to_string()); }
    }
    (header, body)
}

fn parse_attrs(raw: &str) -> Vec<(String, String)> {
    let mut v = Vec::new();
    for p in raw.split(',') {
        let p = p.trim();
        if let Some(eq) = p.find('=') {
            v.push((p[..eq].trim().to_string(), p[eq+1..].trim().trim_matches('"').to_string()));
        } else if !p.is_empty() { v.push((p.to_string(), String::new())); }
    }
    v
}

fn detect_layout(nodes: &[Node]) -> LayoutType {
    let (mut h1, mut kicker, mut speaker, mut cols) = (false, false, false, 0);
    for n in nodes {
        match n {
            Node::Heading(h) if h.level == 1 => h1 = true,
            Node::Attr(a) => match a.typ.as_str() {
                "kicker" => kicker = true,
                "speaker" => speaker = true,
                _ => {}
            },
            Node::Grid(g) => cols = g.cols,
            _ => {}
        }
    }
    if h1 || kicker || speaker { LayoutType::Title }
    else { match cols { 2 => LayoutType::Grid2, 3 => LayoutType::Grid3, 4 => LayoutType::Grid4, _ => LayoutType::Content } }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_simple() {
        let doc = parse_markdown("---\ntheme: t\n---\n\n# Title\n\ntext");
        assert_eq!(doc.slides.len(), 1);
    }

    #[test]
    fn test_table() {
        let doc = parse_markdown("---\ntheme: t\n---\n\n## h\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\ntext");
        assert_eq!(doc.slides.len(), 1);
        assert!(doc.slides[0].children.iter().any(|n| matches!(n, Node::Table(_))));
    }
}

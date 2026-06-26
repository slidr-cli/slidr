use pulldown_cmark::{Event, Options, Parser, Tag, TagEnd};
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
    let after_first = &trimmed[3..];
    if let Some(end) = after_first.find("\n---") {
        let fm = after_first[..end].trim().to_string();
        let body = after_first[end + 4..].to_string();
        (fm, body)
    } else {
        (String::new(), input.to_string())
    }
}

fn split_slides(body: &str, meta: &Meta) -> Vec<Slide> {
    let separator = "\n---\n";
    body.split(separator)
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .map(|content| parse_slide(content, meta))
        .collect()
}

fn parse_slide(content: &str, _meta: &Meta) -> Slide {
    let (notes, content) = extract_notes(content);
    let (content, directives) = extract_directives(&content);
    let (content, fenced) = extract_fenced(&content);

    // Parse remaining markdown.
    let mut opts = Options::empty();
    opts.insert(Options::ENABLE_TABLES);
    let parser = Parser::new_ext(&content, opts);

    let mut children: Vec<Node> = Vec::new();
    let mut current_inline: Vec<Inline> = Vec::new();
    let mut in_heading: Option<u8> = None;
    let mut in_table = false;
    let mut table_headers: Vec<String> = Vec::new();
    let mut table_rows: Vec<Vec<String>> = Vec::new();
    let mut table_cells: Vec<String> = Vec::new();
    let mut table_header_row = true;

    for event in parser {
        match event {
            Event::Start(tag) => match tag {
                Tag::Heading { level, .. } => in_heading = Some(level as u8),
                Tag::Paragraph => {}
                Tag::Table(_) => in_table = true,
                Tag::TableHead => table_header_row = true,
                Tag::TableRow => table_cells.clear(),
                Tag::TableCell => {}
                Tag::BlockQuote(_) => {}
                Tag::List(_) => {}
                Tag::Item => {}
                Tag::CodeBlock(_) => {}
                _ => {}
            },
            Event::End(tag) => match tag {
                TagEnd::Heading(_) => {
                    if let Some(level) = in_heading.take() {
                        children.push(Node::Heading(Heading { level, content: std::mem::take(&mut current_inline) }));
                    }
                }
                TagEnd::Paragraph => {
                    if !current_inline.is_empty() {
                        children.push(Node::Paragraph(std::mem::take(&mut current_inline)));
                    }
                }
                TagEnd::Table => {
                    if !table_headers.is_empty() {
                        children.push(Node::Table(Table {
                            headers: std::mem::take(&mut table_headers),
                            rows: std::mem::take(&mut table_rows),
                        }));
                    }
                    in_table = false;
                }
                TagEnd::TableHead => table_header_row = false,
                TagEnd::TableRow => {
                    if !table_cells.is_empty() {
                        if table_header_row {
                            table_headers = std::mem::take(&mut table_cells);
                        } else {
                            table_rows.push(std::mem::take(&mut table_cells));
                        }
                    }
                }
                TagEnd::TableCell => {}
                TagEnd::BlockQuote(_) => {
                    if !current_inline.is_empty() {
                        children.push(Node::Quote(std::mem::take(&mut current_inline)));
                    }
                }
                TagEnd::List(_) => {}
                TagEnd::Item => {}
                TagEnd::CodeBlock => {}
                _ => {}
            },
            Event::Text(text) => {
                if in_heading.is_some() || !in_table {
                    current_inline.push(Inline::Text(text.to_string()));
                } else {
                    table_cells.push(text.to_string());
                }
            }
            Event::Code(code) => current_inline.push(Inline::Code(code.to_string())),
            Event::SoftBreak => current_inline.push(Inline::SoftBreak),
            Event::HardBreak => current_inline.push(Inline::SoftBreak),
            _ => {}
        }
    }

    // Merge: goldmark nodes first, then fenced, then directives.
    let mut nodes = children;
    nodes.extend(fenced);
    nodes.extend(directives);

    let layout = detect_layout(&nodes);
    Slide { layout, children: nodes, notes }
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
                // Parse key=value pairs.
                let mut attrs = Vec::new();
                let mut remaining = value.to_string();
                for word in value.split_whitespace() {
                    if let Some(eq) = word.find('=') {
                        let k = word[..eq].to_string();
                        let v = word[eq + 1..].trim_matches('"').to_string();
                        attrs.push((k, v));
                    }
                }
                if !attrs.is_empty() {
                    remaining = value.split_whitespace()
                        .filter(|w| !w.contains('='))
                        .collect::<Vec<_>>()
                        .join(" ");
                }
                nodes.push(Node::Attr(AttrNode {
                    typ: typ.to_string(),
                    value: remaining,
                    attrs,
                }));
                continue;
            }
        }
        result.push_str(line);
        result.push('\n');
    }
    (result, nodes)
}

fn extract_fenced(content: &str) -> (String, Vec<Node>) {
    // Simple fenced block parser: ::: type {attrs} ... :::
    let mut nodes = Vec::new();
    let mut result = String::new();
    let mut fence_lines: Vec<String> = Vec::new();
    let mut fence_stack: Vec<(String, Vec<Node>, Vec<(String, String)>)> = Vec::new();

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with(":::") && !trimmed.starts_with("::::") {
            // Opening or closing.
            if trimmed == ":::" {
                // Closing.
                if let Some((ftype, mut children, attrs)) = fence_stack.pop() {
                    if !fence_lines.is_empty() || !children.is_empty() {
                        let node = build_fenced_node(&ftype, &fence_lines, &mut children, &attrs);
                        if let Some(n) = node {
                            if let Some(last) = fence_stack.last_mut() {
                                last.1.push(n);
                            } else {
                                nodes.push(n);
                            }
                        }
                    }
                }
                fence_lines.clear();
                continue;
            }
            // Opening: "::: type {attrs}"
            let rest = trimmed[3..].trim_start();
            let parts: Vec<&str> = rest.splitn(2, ' ').collect();
            if parts.is_empty() || parts[0].is_empty() { continue; }
            let typ = parts[0].trim_end_matches('{');
            let attrs_raw = parts.get(1).unwrap_or(&"").trim_matches(|c| c == '{' || c == '}');
            let attrs = parse_fence_attrs(attrs_raw);
            fence_lines.clear();
            fence_stack.push((typ.to_string(), Vec::new(), attrs));
            continue;
        }

        if !fence_stack.is_empty() {
            fence_lines.push(line.to_string());
        } else {
            result.push_str(line);
            result.push('\n');
        }
    }

    (result, nodes)
}

fn build_fenced_node(typ: &str, lines: &[String], children: &mut Vec<Node>, attrs: &[(String, String)]) -> Option<Node> {
    match typ {
        "card" => {
            let (header, body) = parse_card_body(lines);
            let mut class = String::new();
            let mut tag = None;
            for (k, v) in attrs {
                match k.as_str() {
                    "tag" => tag = Some((header.clone(), v.clone())),
                    "class" => class = v.clone(),
                    _ => { if !class.is_empty() { class.push(' '); } class.push_str(k); }
                }
            }
            Some(Node::Card(Card { header, body, tag, class }))
        }
        "grid" => {
            let cols = attrs.iter().find(|(k, _)| k == "cols")
                .and_then(|(_, v)| v.parse().ok()).unwrap_or(children.len().max(2));
            let class = attrs.iter().find(|(k, _)| k == "class")
                .map(|(_, v)| v.clone()).unwrap_or_default();
            Some(Node::Grid(Grid { cols, class, children: std::mem::take(children) }))
        }
        _ => None,
    }
}

fn parse_card_body(lines: &[String]) -> (String, Vec<String>) {
    let mut header = String::new();
    let mut body = Vec::new();
    let text = lines.join("\n").trim().to_string();

    for line in text.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with("### ") {
            header = trimmed[4..].to_string();
        } else if !trimmed.is_empty() {
            body.push(trimmed.to_string());
        }
    }
    (header, body)
}

fn parse_fence_attrs(raw: &str) -> Vec<(String, String)> {
    let mut attrs = Vec::new();
    for part in raw.split(',') {
        let part = part.trim();
        if let Some(eq) = part.find('=') {
            let k = part[..eq].trim().to_string();
            let v = part[eq + 1..].trim().trim_matches('"').to_string();
            attrs.push((k, v));
        } else if !part.is_empty() {
            attrs.push((part.to_string(), String::new()));
        }
    }
    attrs
}

fn detect_layout(nodes: &[Node]) -> LayoutType {
    let mut has_h1 = false;
    let mut has_kicker = false;
    let mut has_speaker = false;
    let mut grid_cols = 0;

    for n in nodes {
        match n {
            Node::Heading(h) if h.level == 1 => has_h1 = true,
            Node::Attr(a) => match a.typ.as_str() {
                "kicker" => has_kicker = true,
                "speaker" => has_speaker = true,
                _ => {}
            },
            Node::Grid(g) => grid_cols = g.cols,
            _ => {}
        }
    }

    if has_kicker || has_speaker || has_h1 {
        LayoutType::Title
    } else {
        match grid_cols {
            2 => LayoutType::Grid2,
            3 => LayoutType::Grid3,
            4 => LayoutType::Grid4,
            _ => LayoutType::Content,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_simple() {
        let input = "---\ntheme: test\n---\n\n# Title\n\nContent here.";
        let doc = parse_markdown(input);
        assert_eq!(doc.slides.len(), 1);
    }
}

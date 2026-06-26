use serde::Deserialize;

#[derive(Debug, Deserialize, Default)]
pub struct Meta {
    pub theme: Option<String>,
    pub title: Option<String>,
    pub footer: Option<String>,
    pub paginate: Option<bool>,
    #[serde(default)]
    pub size: String,
    #[serde(default)]
    pub style: String,
    pub logo: Option<String>,
}

impl Meta {
    pub fn dimensions(&self) -> (u32, u32) {
        if self.size.is_empty() {
            return (1280, 720);
        }
        if let Some((w, h)) = self.size.split_once('x') {
            if let (Ok(w), Ok(h)) = (w.parse::<u32>(), h.parse::<u32>()) {
                return (w.min(7680).max(320), h.min(7680).max(320));
            }
        }
        match self.size.as_str() {
            "16:9" => (1280, 720),
            "4:3" => (1024, 768),
            "16:10" => (1280, 800),
            _ => (1280, 720),
        }
    }
}

#[derive(Debug)]
pub struct Document {
    pub meta: Meta,
    pub slides: Vec<Slide>,
}

#[derive(Debug)]
pub struct Slide {
    pub layout: LayoutType,
    pub children: Vec<Node>,
    pub notes: String,
}

#[derive(Debug, PartialEq)]
pub enum LayoutType {
    Title,
    Grid2,
    Grid3,
    Grid4,
    Content,
}

#[derive(Debug)]
pub enum Node {
    Heading(Heading),
    Paragraph(Vec<Inline>),
    Grid(Grid),
    Card(Card),
    Table(Table),
    Quote(Vec<Inline>),
    List(Vec<String>),
    Attr(AttrNode),
    Image(String, String),
    RawHtml(String),
}

#[derive(Debug)]
pub struct Heading {
    pub level: u8,
    pub content: Vec<Inline>,
}

#[derive(Debug)]
pub struct Grid {
    pub cols: usize,
    pub class: String,
    pub children: Vec<Node>,
}

#[derive(Debug)]
pub struct Card {
    pub header: String,
    pub body: Vec<String>,
    pub tag: Option<(String, String)>, // (text, color)
    pub class: String,
}

#[derive(Debug)]
pub struct Table {
    pub headers: Vec<String>,
    pub rows: Vec<Vec<String>>,
}

#[derive(Debug)]
pub struct AttrNode {
    pub typ: String,
    pub value: String,
    pub attrs: Vec<(String, String)>,
}

#[derive(Debug)]
pub enum Inline {
    Text(String),
    Strong(Vec<Inline>),
    Code(String),
    Link(String, String),
    SoftBreak,
    Image(String, String),
}

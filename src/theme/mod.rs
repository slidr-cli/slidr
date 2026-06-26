pub struct Theme {
    pub raw: String,
}

impl Theme {
    pub fn new(raw: String) -> Self {
        Self { raw }
    }

    pub fn var(&self, name: &str) -> Option<String> {
        let prefix = format!("{}:", name);
        let mut in_comment = false;
        let mut chars = self.raw.chars().peekable();

        while let Some(&c) = chars.peek() {
            match c {
                '/' => {
                    chars.next();
                    if chars.peek() == Some(&'*') {
                        chars.next();
                        in_comment = true;
                    }
                }
                '*' => {
                    chars.next();
                    if in_comment && chars.peek() == Some(&'/') {
                        chars.next();
                        in_comment = false;
                    }
                }
                _ if !in_comment => {
                    // Check if this position starts our variable.
                    let rest: String = chars.clone().take(prefix.len()).collect();
                    if rest == prefix {
                        // Skip the prefix.
                        for _ in 0..prefix.len() {
                            chars.next();
                        }
                        // Collect value until ; or }
                        let mut value = String::new();
                        while let Some(&vc) = chars.peek() {
                            if vc == ';' || vc == '}' {
                                break;
                            }
                            value.push(vc);
                            chars.next();
                        }
                        let value = value.trim().to_string();
                        if !value.is_empty() {
                            return Some(value);
                        }
                    } else {
                        chars.next();
                    }
                }
                _ => {
                    chars.next();
                }
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_var() {
        let css = ":root { --bg: #07110c; --ink: #eef7f0; }";
        let t = Theme::new(css.into());
        assert_eq!(t.var("--bg"), Some("#07110c".into()));
        assert_eq!(t.var("--ink"), Some("#eef7f0".into()));
        assert_eq!(t.var("--nope"), None);
    }

    #[test]
    fn test_comment_skipped() {
        let css = "/* --bg: red; */ :root { --bg: #07110c; }";
        let t = Theme::new(css.into());
        assert_eq!(t.var("--bg"), Some("#07110c".into()));
    }

    #[test]
    fn test_multiline_value() {
        let css = ":root { --gradient: linear-gradient(120deg, rgba(15, 208, 93, 0.10), transparent 42%); }";
        let t = Theme::new(css.into());
        assert_eq!(t.var("--gradient"), Some("linear-gradient(120deg, rgba(15, 208, 93, 0.10), transparent 42%)".into()));
    }
}

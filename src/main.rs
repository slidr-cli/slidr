use clap::Parser;
use std::path::Path;

mod parser;
mod theme;
mod render;

#[derive(Parser)]
#[command(name = "slidr", about = "Markdown to styled PPTX + PDF")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(clap::Subcommand)]
enum Commands {
    Build {
        file: String,
        #[arg(short = 'o', long, default_value = "")]
        output_dir: String,
        #[arg(long)]
        pdf: bool,
        #[arg(long)]
        pptx: bool,
    },
}

fn main() {
    let cli = Cli::parse();
    match cli.command {
        Commands::Build { file, output_dir, pdf, pptx } => {
            let input = std::fs::read_to_string(&file).expect("cannot read input file");
            let doc = parser::markdown::parse_markdown(&input);
            let t = theme::Theme::new(doc.meta.style.clone().unwrap_or_default());

            let gen_all = !pdf && !pptx;
            let gen_pdf = gen_all || pdf;

            let out_dir = if output_dir.is_empty() {
                let parent = Path::new(&file).parent().unwrap_or(Path::new("."));
                parent.join("dist")
            } else {
                Path::new(&output_dir).to_path_buf()
            };
            std::fs::create_dir_all(&out_dir).ok();

            let stem = Path::new(&file).file_stem().unwrap().to_str().unwrap();

            // HTML
            let html = render::html::render(&doc, doc.meta.style.as_deref().unwrap_or_default(), doc.meta.logo.as_deref());
            let html_path = out_dir.join(format!("{}.html", stem));
            std::fs::write(&html_path, &html).unwrap();
            println!("Wrote {} ({} bytes)", html_path.display(), html.len());

            println!("Parsed {} slides", doc.slides.len());
            for (i, slide) in doc.slides.iter().enumerate() {
                println!("  Slide {}: {:?} ({} children)", i + 1, slide.layout, slide.children.len());
            }

            let _ = (gen_pdf, t);
        }
    }
}

use std::{
    env,
    error::Error,
    io::{self, Cursor},
    process::Command,
    time::{Duration, Instant},
};

use base64::{engine::general_purpose, Engine as _};
use crossterm::{
    event::{self, Event, KeyCode, KeyEventKind},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use image::ImageReader;
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout},
    style::{Color, Style, Stylize},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Terminal,
};
use ratatui_image::{picker::Picker, protocol::StatefulProtocol, StatefulImage};
use serde::Deserialize;

#[derive(Deserialize, Debug, Default, Clone)]
struct StockStats {
    symbol: String,
    price: f64,
    open: f64,
    high: f64,
    low: f64,
    volume: u64,
    change: f64,
    pct_change: f64,
    image_data: Option<String>,
    #[serde(default)]
    error: Option<String>,
}

fn fetch_stock_data(symbol: &str, width: u16, height: u16) -> Result<StockStats, Box<dyn Error>> {
    let output = Command::new("python3")
        .arg("fetch_stock.py")
        .arg(symbol)
        .arg(width.to_string())
        .arg(height.to_string())
        .output()?;

    if !output.status.success() {
        let err_msg = String::from_utf8_lossy(&output.stderr);
        return Err(format!("Python script failed: {}", err_msg).into());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let json_start = stdout.find('{').unwrap_or(0);
    let json_str = &stdout[json_start..];
    
    let stats: StockStats = serde_json::from_str(json_str)?;
    Ok(stats)
}

fn decode_image(b64_data: &str) -> Option<image::DynamicImage> {
    let bytes = general_purpose::STANDARD.decode(b64_data).ok()?;
    let reader = ImageReader::new(Cursor::new(bytes)).with_guessed_format().ok()?;
    reader.decode().ok()
}

fn main() -> Result<(), Box<dyn Error>> {
    // Parse arguments
    let args: Vec<String> = env::args().collect();
    let default_ticker = "AAPL".to_string();
    let ticker = if args.len() > 1 { &args[1] } else { &default_ticker };

    // Initial fetch with default size
    let mut stats = match fetch_stock_data(ticker, 100, 40) {
        Ok(s) => s,
        Err(e) => StockStats {
            error: Some(e.to_string()),
            ..Default::default()
        },
    };

    let mut current_img = if let Some(ref data) = stats.image_data {
        decode_image(data)
    } else {
        None
    };

    enable_raw_mode()?;
    let mut stdout = io::stdout();

    let mut picker = Picker::from_query_stdio()?;

    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut image_protocol = if let Some(img) = current_img {
        Some(picker.new_resize_protocol(img))
    } else {
        None
    };

    let res = run_app(
        &mut terminal,
        &mut image_protocol,
        &mut picker,
        ticker,
        &mut stats,
    );

    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;

    if let Err(err) = res {
        println!("Error: {:?}", err);
    }

    Ok(())
}

fn run_app(
    terminal: &mut Terminal<CrosstermBackend<io::Stdout>>,
    image_protocol: &mut Option<StatefulProtocol>,
    picker: &mut Picker,
    ticker: &str,
    stats: &mut StockStats,
) -> io::Result<()> {
    let mut last_fetch_time = Instant::now();
    let tick_rate = Duration::from_secs(60); 
    
    // State for resizing
    let mut last_fetched_size = (0u16, 0u16);
    let mut current_image_area_size = (0u16, 0u16);
    let mut last_size_change_time = Instant::now();
    let resize_debounce = Duration::from_millis(1500); // Wait 1.5s after resize to fetch

    loop {
        terminal.draw(|f| {
            let chunks = Layout::default()
                .direction(Direction::Vertical)
                .constraints([Constraint::Length(5), Constraint::Min(0)])
                .split(f.area());

            // Header Stats
            let header_block = Block::default()
                .borders(Borders::ALL)
                .title(format!("Stock Stats: {}", ticker.to_uppercase()));

            let stats_text = if let Some(err) = &stats.error {
                vec![Line::from(Span::styled(
                    format!("Error: {}", err),
                    Style::default().fg(Color::Red),
                ))]
            } else {
                let color = if stats.change >= 0.0 {
                    Color::Green
                } else {
                    Color::Red
                };
                
                vec![
                    Line::from(vec![
                        Span::raw("Symbol: "),
                        Span::styled(stats.symbol.clone(), Style::default().bold()),
                        Span::raw(" | Price: "),
                        Span::styled(format!("${:.2}", stats.price), Style::default().bold()),
                    ]),
                    Line::from(vec![
                        Span::raw("Change: "),
                        Span::styled(
                            format!("{:.2} ({:.2}%)", stats.change, stats.pct_change),
                            Style::default().fg(color).bold(),
                        ),
                    ]),
                    Line::from(format!(
                        "O: {:.2} | H: {:.2} | L: {:.2} | Vol: {}",
                        stats.open, stats.high, stats.low, stats.volume
                    )),
                ]
            };

            let paragraph = Paragraph::new(stats_text).block(header_block);
            f.render_widget(paragraph, chunks[0]);

            // Image Area
            let image_block = Block::default().borders(Borders::ALL).title("Intraday % Change (1m)");
            let inner_image_area = image_block.inner(chunks[1]);
            f.render_widget(image_block, chunks[1]);
            
            // Capture size for resizing logic
            let new_size = (inner_image_area.width, inner_image_area.height);
            if new_size != current_image_area_size {
                current_image_area_size = new_size;
                last_size_change_time = Instant::now();
            }

            if let Some(protocol) = image_protocol {
                let image_widget = StatefulImage::default();
                f.render_stateful_widget(image_widget, inner_image_area, protocol);
            }
        })?;

        let timeout = Duration::from_millis(200);
        if event::poll(timeout)? {
            if let Event::Key(key) = event::read()? {
                if key.kind == KeyEventKind::Press {
                    if let KeyCode::Char('q') | KeyCode::Esc = key.code {
                        break;
                    }
                }
            }
        }

        let time_since_fetch = last_fetch_time.elapsed();
        let time_since_resize = last_size_change_time.elapsed();
        let size_changed = current_image_area_size != last_fetched_size && current_image_area_size.0 > 0;
        
        let should_fetch = 
            time_since_fetch >= tick_rate || 
            (size_changed && time_since_resize >= resize_debounce);

        if should_fetch {
            let (w, h) = current_image_area_size;
            // Use current size, or default if not yet captured (should be captured by draw)
            let w_arg = if w > 0 { w } else { 100 };
            let h_arg = if h > 0 { h } else { 40 };

            if let Ok(new_stats) = fetch_stock_data(ticker, w_arg, h_arg) {
                *stats = new_stats;
                
                if let Some(ref data) = stats.image_data {
                    if let Some(img) = decode_image(data) {
                        *image_protocol = Some(picker.new_resize_protocol(img));
                    }
                }
                last_fetched_size = (w, h);
                last_fetch_time = Instant::now();
            }
        }
    }
    Ok(())
}

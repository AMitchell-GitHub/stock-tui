use std::{
    env,
    error::Error,
    fs::File,
    io::{self, Cursor},
    process::Command,
    time::{Duration, Instant},
};

use base64::{engine::general_purpose, Engine as _};
use crossterm::{
    event::{self, Event, KeyCode, KeyEventKind, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use image::ImageReader;
use ratatui::{
    backend::CrosstermBackend,
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style, Stylize},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, List, ListItem, ListState, Paragraph},
    Frame, Terminal,
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

#[derive(Debug, Deserialize, Clone)]
struct TickerRecord {
    #[serde(rename = "Ticker")]
    ticker: String,
    #[serde(rename = "Name")]
    name: String,
    #[serde(rename = "Type")]
    kind: String,
}

#[derive(PartialEq)]
enum InputMode {
    Normal,
    Editing,
}

struct App {
    ticker: String,
    stats: StockStats,
    input_mode: InputMode,
    input: String,
    character_index: usize,
    tickers_db: Vec<TickerRecord>,
    filtered_tickers: Vec<TickerRecord>,
    list_state: ListState,
    image_protocol: Option<StatefulProtocol>,
    picker: Picker,
    last_fetched_size: (u16, u16),
    current_image_area_size: (u16, u16),
    last_size_change_time: Instant,
    last_fetch_time: Instant,
}

impl App {
    fn new(ticker: String, tickers_db: Vec<TickerRecord>, picker: Picker) -> App {
        App {
            ticker,
            stats: StockStats::default(),
            input_mode: InputMode::Normal,
            input: String::new(),
            character_index: 0,
            tickers_db,
            filtered_tickers: Vec::new(),
            list_state: ListState::default(),
            image_protocol: None,
            picker,
            last_fetched_size: (0, 0),
            current_image_area_size: (0, 0),
            last_size_change_time: Instant::now(),
            last_fetch_time: Instant::now(), // force initial fetch
        }
    }

    fn update_filtered_tickers(&mut self) {
        if self.input.is_empty() {
            self.filtered_tickers = self.tickers_db.clone();
        } else {
            let query = self.input.to_lowercase();
            self.filtered_tickers = self.tickers_db
                .iter()
                .filter(|t| {
                    t.ticker.to_lowercase().contains(&query) || 
                    t.name.to_lowercase().contains(&query)
                })
                .cloned()
                .collect();
        }
        self.list_state.select(Some(0));
    }
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

fn load_tickers() -> Result<Vec<TickerRecord>, Box<dyn Error>> {
    let file = File::open("top-tickers.csv")?;
    let mut rdr = csv::Reader::from_reader(file);
    let mut tickers = Vec::new();
    for result in rdr.deserialize() {
        let record: TickerRecord = result?;
        tickers.push(record);
    }
    Ok(tickers)
}

fn main() -> Result<(), Box<dyn Error>> {
    // Parse arguments
    let args: Vec<String> = env::args().collect();
    let default_ticker = "AAPL".to_string();
    let start_ticker = if args.len() > 1 { args[1].clone() } else { default_ticker };

    // Load tickers first
    let tickers_db = load_tickers().unwrap_or_else(|_| Vec::new());

    // Setup terminal
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    let picker = Picker::from_query_stdio()?;
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let mut app = App::new(start_ticker, tickers_db, picker);
    
    // Initial fetch
    if let Ok(stats) = fetch_stock_data(&app.ticker, 100, 40) {
        app.stats = stats;
        if let Some(ref data) = app.stats.image_data {
            if let Some(img) = decode_image(data) {
                app.image_protocol = Some(app.picker.new_resize_protocol(img));
            }
        }
    }

    let res = run_app(&mut terminal, &mut app);

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
    app: &mut App,
) -> io::Result<()> {
    let tick_rate = Duration::from_secs(60); 
    let resize_debounce = Duration::from_millis(1500);

    loop {
        terminal.draw(|f| ui(f, app))?;

        let timeout = Duration::from_millis(200);
        if event::poll(timeout)? {
            if let Event::Key(key) = event::read()? {
                if key.kind == KeyEventKind::Press {
                    match app.input_mode {
                        InputMode::Normal => match key.code {
                            KeyCode::Char('q') | KeyCode::Esc => return Ok(()),
                            KeyCode::Char('o') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                                app.input_mode = InputMode::Editing;
                                app.input.clear();
                                app.character_index = 0;
                                app.update_filtered_tickers();
                            }
                            _ => {}
                        },
                        InputMode::Editing => match key.code {
                            KeyCode::Esc => {
                                app.input_mode = InputMode::Normal;
                            }
                            KeyCode::Enter => {
                                if let Some(selected_idx) = app.list_state.selected() {
                                    if let Some(ticker) = app.filtered_tickers.get(selected_idx) {
                                        app.ticker = ticker.ticker.clone();
                                        // Trigger fetch immediately
                                        // We set last_fetch_time to a long time ago to trigger update
                                        app.last_fetch_time = Instant::now().checked_sub(tick_rate * 2).unwrap_or(Instant::now());
                                        app.input_mode = InputMode::Normal;
                                    }
                                }
                            }
                            KeyCode::Char(c) => {
                                app.input.insert(app.character_index, c);
                                app.character_index += 1;
                                app.update_filtered_tickers();
                            }
                            KeyCode::Backspace => {
                                if app.character_index > 0 {
                                    app.character_index -= 1;
                                    app.input.remove(app.character_index);
                                    app.update_filtered_tickers();
                                }
                            }
                            KeyCode::Down => {
                                let i = match app.list_state.selected() {
                                    Some(i) => {
                                        if i >= app.filtered_tickers.len().saturating_sub(1) {
                                            0
                                        } else {
                                            i + 1
                                        }
                                    }
                                    None => 0,
                                };
                                app.list_state.select(Some(i));
                            }
                            KeyCode::Up => {
                                let i = match app.list_state.selected() {
                                    Some(i) => {
                                        if i == 0 {
                                            app.filtered_tickers.len().saturating_sub(1)
                                        } else {
                                            i - 1
                                        }
                                    }
                                    None => 0,
                                };
                                app.list_state.select(Some(i));
                            }
                            _ => {}
                        }
                    }
                }
            }
        }

        let time_since_fetch = app.last_fetch_time.elapsed();
        let time_since_resize = app.last_size_change_time.elapsed();
        let size_changed = app.current_image_area_size != app.last_fetched_size && app.current_image_area_size.0 > 0;
        
        let should_fetch = match app.input_mode {
            InputMode::Normal => {
                time_since_fetch >= tick_rate || 
                (size_changed && time_since_resize >= resize_debounce)
            },
            InputMode::Editing => false,
        };

        if should_fetch {
            // Need to handle fetch here
            let (w, h) = app.current_image_area_size;
            let w_arg = if w > 0 { w } else { 100 };
            let h_arg = if h > 0 { h } else { 40 };

            if let Ok(new_stats) = fetch_stock_data(&app.ticker, w_arg, h_arg) {
                app.stats = new_stats;
                if let Some(ref data) = app.stats.image_data {
                    if let Some(img) = decode_image(data) {
                        app.image_protocol = Some(app.picker.new_resize_protocol(img));
                    }
                }
                app.last_fetched_size = (w, h);
                app.last_fetch_time = Instant::now();
            }
        }
    }
}

fn centered_rect(percent_x: u16, percent_y: u16, r: Rect) -> Rect {
    let popup_layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Percentage((100 - percent_y) / 2),
            Constraint::Percentage(percent_y),
            Constraint::Percentage((100 - percent_y) / 2),
        ])
        .split(r);

    let layout = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage((100 - percent_x) / 2),
            Constraint::Percentage(percent_x),
            Constraint::Percentage((100 - percent_x) / 2),
        ])
        .split(popup_layout[1]);

    layout[1]
}

fn ui(f: &mut Frame, app: &mut App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(5), Constraint::Min(0)])
        .split(f.area());

    // Find ticker info
    let ticker_info = app.tickers_db.iter().find(|t| t.ticker == app.stats.symbol);
    let (name, kind) = if let Some(info) = ticker_info {
        (info.name.as_str(), info.kind.as_str())
    } else {
        ("Unknown", "Unknown")
    };

    // Header Stats
    let header_block = Block::default()
        .borders(Borders::ALL)
        .title(format!("Stock Stats: {} | {} ({})", app.stats.symbol, name, kind));

    let stats_text = if let Some(err) = &app.stats.error {
        vec![Line::from(Span::styled(
            format!("Error: {}", err),
            Style::default().fg(Color::Red),
        ))]
    } else {
        let color = if app.stats.change >= 0.0 {
            Color::Green
        } else {
            Color::Red
        };
        
        vec![
            Line::from(vec![
                Span::raw("Price: "),
                Span::styled(format!("${:.2}", app.stats.price), Style::default().bold()),
                Span::raw(" | Change: "),
                Span::styled(
                    format!("{:.2} ({:.2}%)", app.stats.change, app.stats.pct_change),
                    Style::default().fg(color).bold(),
                ),
            ]),
            Line::from(format!(
                "O: {:.2} | H: {:.2} | L: {:.2} | Vol: {}",
                app.stats.open, app.stats.high, app.stats.low, app.stats.volume
            )),
            Line::from(vec![
                Span::raw("Type: "),
                Span::styled(kind, Style::default().fg(Color::Cyan)),
            ]),
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
    if new_size != app.current_image_area_size {
        app.current_image_area_size = new_size;
        app.last_size_change_time = Instant::now();
    }

    if let Some(protocol) = &mut app.image_protocol {
        let image_widget = StatefulImage::default();
        f.render_stateful_widget(image_widget, inner_image_area, protocol);
    }

    // Popup Logic
    if app.input_mode == InputMode::Editing {
        let popup_area = centered_rect(60, 50, f.area());
        f.render_widget(Clear, popup_area); // clear background
        
        // Popup block with borders
        let popup_block = Block::default().borders(Borders::ALL).title("Select Ticker");
        f.render_widget(popup_block.clone(), popup_area);
        
        let popup_layout = Layout::default()
            .direction(Direction::Vertical)
            .constraints([Constraint::Length(3), Constraint::Min(1)])
            .margin(1) // margin inside the borders
            .split(popup_area);

        let input_block = Block::default().borders(Borders::ALL).title("Search");
        let input_paragraph = Paragraph::new(app.input.as_str())
            .style(Style::default().fg(Color::Yellow))
            .block(input_block);
        f.render_widget(input_paragraph, popup_layout[0]);

        // Suggestions List
        let items: Vec<ListItem> = app.filtered_tickers
            .iter()
            .map(|t| {
                ListItem::new(Line::from(vec![
                    Span::styled(format!("{: <6}", t.ticker), Style::default().bold()),
                    Span::raw(format!(" {} ({})", t.name, t.kind)),
                ]))
            })
            .collect();

        // Use a stateful widget for the list to handle selection highlighting
        let list = List::new(items)
            .block(Block::default().borders(Borders::ALL).title("Results"))
            .highlight_style(Style::default().add_modifier(Modifier::REVERSED))
            .highlight_symbol(">> ");
        
        f.render_stateful_widget(list, popup_layout[1], &mut app.list_state);
        
        // Ensure cursor is visible in input (optional, can be tricky with layout)
    }
}

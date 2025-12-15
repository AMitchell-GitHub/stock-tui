use std::{
    error::Error,
    io,
    time::Duration,
};
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{backend::CrosstermBackend, Terminal};
use std::env;
use tokio::time;

mod app;
mod ui;

use app::App;

#[tokio::main]
async fn main() -> Result<(), Box<dyn Error>> {
    // Args
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("Usage: stock_tui <TICKER>");
        return Ok(());
    }
    let ticker = args[1].to_uppercase();

    // Setup Terminal
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    // App State
    let mut app = App::new(ticker);
    
    // Initial fetch
    let _ = app.fetch_data().await; // Ignore initial error, will retry on tick

    // Event Loop
    let tick_rate = Duration::from_secs(1);
    let fetch_rate = Duration::from_secs(10);
    // Use app's own timer state if preferred, or keep local
    let mut last_tick = time::Instant::now();
    let mut last_fetch = time::Instant::now(); // Corresponds to app.fetch_data calls

    loop {
        // Update countdown
        let elapsed = last_fetch.elapsed();
        if elapsed < fetch_rate {
            app.next_update_secs = (fetch_rate - elapsed).as_secs();
        } else {
            app.next_update_secs = 0;
        }

        terminal.draw(|f| ui::draw(f, &app))?;

        let timeout = tick_rate
            .checked_sub(last_tick.elapsed())
            .unwrap_or_else(|| Duration::from_secs(0));

        if crossterm::event::poll(timeout)? {
            if let Event::Key(key) = event::read()? {
                match key.code {
                    KeyCode::Char('q') => {
                         app.should_quit = true;
                    }
                    KeyCode::Esc => {
                        app.should_quit = true;
                    }
                    KeyCode::Char('p') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                        app.toggle_pre_market();
                    }
                    KeyCode::Char('h') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                        app.show_help = !app.show_help;
                    }
                    _ => {}
                }
            }
        }

        if last_tick.elapsed() >= tick_rate {
            // UI Tick 
            last_tick = time::Instant::now();
        }
        
        if last_fetch.elapsed() >= fetch_rate {
            // Fetch Data
            let res = app.fetch_data().await;
            if let Err(_e) = res {
                // Log error potentially, or just ignore transient network issues
            }
            last_fetch = time::Instant::now();
        }

        if app.should_quit {
            break;
        }
    }

    // Restore Terminal
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    Ok(())
}

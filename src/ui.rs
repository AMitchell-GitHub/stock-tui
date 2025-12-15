use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    symbols,
    text::{Line, Span},
    widgets::{Axis, Block, Borders, Chart, Dataset, GraphType, Paragraph},
    Frame,
};
use chrono::{TimeZone, Utc, Timelike};
use chrono_tz::US::Eastern;
use crate::app::App;

pub fn draw(f: &mut Frame, app: &App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(3), Constraint::Min(0)])
        .split(f.area());

    draw_header(f, app, chunks[0]);
    draw_chart(f, app, chunks[1]);
}

fn draw_header(f: &mut Frame, app: &App, area: Rect) {
    let data = &app.data;
    
    let color = if data.change_percent >= 0.0 {
        Color::Green
    } else {
        Color::Red
    };

    let icon = if data.change_percent >= 0.0 { "▲" } else { "▼" };

    // Format Volume
    let vol_str = if data.volume >= 1_000_000 {
        format!("{:.2}M", data.volume as f64 / 1_000_000.0)
    } else if data.volume >= 1_000 {
        format!("{:.2}K", data.volume as f64 / 1_000.0)
    } else {
        data.volume.to_string()
    };

    let text = vec![Line::from(vec![
        Span::styled(format!("{} ", data.symbol), Style::default().add_modifier(Modifier::BOLD)),
        Span::styled(format!("{:.2} {} ", data.price, data.currency), Style::default().add_modifier(Modifier::BOLD)),
        Span::styled(format!("{} {:.2}% ", icon, data.change_percent.abs()), Style::default().fg(color).add_modifier(Modifier::BOLD)),
        Span::styled(" | ", Style::default().fg(Color::DarkGray)),
        Span::styled(format!("O: {:.2} ", data.open), Style::default().fg(Color::Gray)),
        Span::styled(format!("H: {:.2} ", data.high), Style::default().fg(Color::Gray)),
        Span::styled(format!("L: {:.2} ", data.low), Style::default().fg(Color::Gray)),
        Span::styled(format!("Vol: {} ", vol_str), Style::default().fg(Color::Gray)),
        Span::styled(format!("| {}", app.next_update_secs), Style::default().fg(Color::DarkGray)),
    ])];

    let header = Paragraph::new(text)
        .block(Block::default().borders(Borders::ALL).title("Stock Tracker").border_style(Style::default().fg(Color::Blue)));
    
    f.render_widget(header, area);
}

fn draw_chart(f: &mut Frame, app: &App, area: Rect) {
    let data = &app.data;
    
    if data.prices.is_empty() {
        let block = Block::default().title("Live Chart").borders(Borders::ALL).border_style(Style::default().fg(Color::Blue));
        let text = Paragraph::new("Loading data...").block(block);
        f.render_widget(text, area);
        return;
    }

    // Determine bounds based on pre-market setting
    let (x_min, x_max, x_labels) = if app.show_pre_market {
        // 04:00 to 16:00
        (240.0, 960.0, vec![
            Span::styled("04:00", Style::default().add_modifier(Modifier::BOLD)),
            Span::styled("09:30", Style::default().add_modifier(Modifier::BOLD)),
            Span::styled("16:00", Style::default().add_modifier(Modifier::BOLD)),
        ])
    } else {
        // 09:30 to 16:00
        (570.0, 960.0, vec![
            Span::styled("09:30", Style::default().add_modifier(Modifier::BOLD)),
            Span::styled("13:00", Style::default().add_modifier(Modifier::BOLD)),
            Span::styled("16:00", Style::default().add_modifier(Modifier::BOLD)),
        ])
    };

    let mut points: Vec<(f64, f64)> = vec![];
    let mut min_y = 0.0; // Include 0
    let mut max_y = 0.0;
    
    for (i, &ts) in data.timestamps.iter().enumerate() {
        if let Some(&price) = data.prices.get(i) {
            // Convert to Eastern time
            let dt = Utc.timestamp_opt(ts, 0).unwrap().with_timezone(&Eastern);
            let minutes = (dt.hour() * 60 + dt.minute()) as f64;
            
            // Filter points if pre-market is hidden
            if !app.show_pre_market && minutes < 570.0 {
                continue;
            }
            
            // Calculate pct change
            let pct = if data.previous_close != 0.0 {
                ((price - data.previous_close) / data.previous_close) * 100.0
            } else {
                0.0
            };
            
            points.push((minutes, pct));
            
            if pct < min_y { min_y = pct; }
            if pct > max_y { max_y = pct; }
        }
    }



    let baseline_data = vec![(x_min, 0.0), (x_max, 0.0)];

    let datasets = vec![
        // Baseline at 0%
         Dataset::default()
            // No name to avoid legend
            .marker(symbols::Marker::Braille)
            .graph_type(GraphType::Line)
            .style(Style::default().fg(Color::DarkGray))
            .data(&baseline_data), 
        // Price Line
        Dataset::default()
             // No name to avoid legend
            .marker(symbols::Marker::Braille)
            .graph_type(GraphType::Line)
            .style(Style::default().fg(if data.change_percent >= 0.0 { Color::Green } else { Color::Red }))
            .data(&points),
    ];
    
    // Smart Bounds: Ensure 0 is included, but don't force symmetry
    let y_min_val = min_y.min(0.0);
    let y_max_val = max_y.max(0.0);
    
    // Add small padding to prevent line hugging the border
    let y_span = (y_max_val - y_min_val).abs();
    let pad = if y_span == 0.0 { 0.05 } else { y_span * 0.05 };
    
    let y_min_bound = y_min_val - pad;
    let y_max_bound = y_max_val + pad;
    
    // Calculate accurate labels for Bottom, Middle, Top
    let y_mid_bound = (y_min_bound + y_max_bound) / 2.0;

    let chart = Chart::new(datasets)
        .block(Block::default().title("Live Chart (Ctrl+H: Help)").borders(Borders::ALL).border_style(Style::default().fg(Color::Blue)))
        .x_axis(Axis::default()
            .title("Time (ET)")
            .style(Style::default().fg(Color::Gray))
            .bounds([x_min, x_max])
            .labels(x_labels))
        .y_axis(Axis::default()
            .title("Return %")
            .style(Style::default().fg(Color::Gray))
            .bounds([y_min_bound, y_max_bound])
            .labels(vec![
                Span::raw(format!("{:.2}%", y_min_bound)),
                Span::raw(format!("{:.2}%", y_mid_bound)),
                Span::raw(format!("{:.2}%", y_max_bound)),
            ]));

    f.render_widget(chart, area);
    
    if app.show_help {
        draw_help(f);
    }
}

fn draw_help(f: &mut Frame) {
    let area = f.area();
    // Center popup
    let popup_layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Percentage(35),
            Constraint::Percentage(30), // Popup height
            Constraint::Percentage(35),
        ])
        .split(area);

    let popup_area = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage(30),
            Constraint::Percentage(40), // Popup width
            Constraint::Percentage(30),
        ])
        .split(popup_layout[1])[1];

    let text = vec![
        Line::from("Stock TUI Help"),
        Line::from(""),
        Line::from(vec![Span::styled("Ctrl + P", Style::default().add_modifier(Modifier::BOLD)), Span::raw(": Toggle Pre-market")]),
        Line::from(vec![Span::styled("Ctrl + H", Style::default().add_modifier(Modifier::BOLD)), Span::raw(": Toggle Help")]),
        Line::from(vec![Span::styled("Ctrl + Q", Style::default().add_modifier(Modifier::BOLD)), Span::raw(": Quit")]),
        Line::from(vec![Span::styled("Esc     ", Style::default().add_modifier(Modifier::BOLD)), Span::raw(": Quit")]),
    ];

    let p = Paragraph::new(text)
        .block(Block::default().borders(Borders::ALL).title("Help").border_style(Style::default().fg(Color::Yellow)))
        .style(Style::default().bg(Color::Reset)) // Ensure opaque if backend supports, but ratatui layers usually work
        .alignment(ratatui::layout::Alignment::Center);

    // Clear background for popup (simple way is to render a clear block first)
    f.render_widget(ratatui::widgets::Clear, popup_area);
    f.render_widget(p, popup_area);
}

use std::error::Error;
use reqwest::Client;
use serde::Deserialize;
use chrono::{DateTime, Utc, Timelike, TimeZone};
use chrono_tz::US::Eastern;

#[derive(Debug, Clone)]
pub struct StockData {
    pub symbol: String,
    pub price: f64,
    pub previous_close: f64,
    pub change_percent: f64,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub volume: u64,
    pub timestamps: Vec<i64>,
    pub prices: Vec<f64>,
    pub currency: String,
}

impl Default for StockData {
    fn default() -> Self {
        Self {
            symbol: String::new(),
            price: 0.0,
            previous_close: 0.0,
            change_percent: 0.0,
            open: 0.0,
            high: 0.0,
            low: 0.0,
            volume: 0,
            timestamps: vec![],
            prices: vec![],
            currency: "USD".to_string(),
        }
    }
}

pub struct App {
    pub ticker: String,
    pub data: StockData,
    pub should_quit: bool,
    pub last_fetch_time: std::time::Instant,
    pub next_update_secs: u64,
    pub show_pre_market: bool,
    pub show_help: bool,
    pub client: Client,
}

impl App {
    pub fn new(ticker: String) -> Self {
        Self {
            ticker,
            data: StockData::default(),
            should_quit: false,
            last_fetch_time: std::time::Instant::now(),
            next_update_secs: 0,
            show_pre_market: false, // Default to false per user request
            show_help: false,
            client: Client::new(),
        }
    }

    pub async fn fetch_data(&mut self) -> Result<(), Box<dyn Error>> {
        let url = format!(
            "https://query2.finance.yahoo.com/v8/finance/chart/{}?interval=1m&range=1d&includePrePost=true",
            self.ticker
        );

        let resp = self.client.get(&url)
            .header("User-Agent", "Mozilla/5.0")
            .send()
            .await?
            .json::<YFResponse>()
            .await?;

        self.update_from_response(resp);
        // Reset fetch timer reference if needed, but main loop handles timing.
        // We just update the data here.
        Ok(())
    }

    pub fn update_from_response(&mut self, resp: YFResponse) {
        if let Some(result) = resp.chart.result.first() {
            let meta = &result.meta;
            self.data.symbol = meta.symbol.clone();
            self.data.currency = meta.currency.clone();
            self.data.price = meta.regular_market_price;
            self.data.previous_close = meta.chart_previous_close;
            self.data.open = meta.regular_market_open;
            self.data.high = meta.regular_market_day_high;
            self.data.low = meta.regular_market_day_low;
            self.data.volume = meta.regular_market_volume;
            
            // Fallback for open if 0 (sometimes pre-market it's 0)
            if self.data.open == 0.0 && self.data.previous_close != 0.0 {
                 // self.data.open = self.data.previous_close; // Optional: Keep 0 if truly 0?
            }
            
            // Calculate change
            if self.data.previous_close != 0.0 {
                 self.data.change_percent = ((self.data.price - self.data.previous_close) / self.data.previous_close) * 100.0;
            }

            if let Some(timestamps) = &result.timestamp {
                if let Some(indicators) = &result.indicators.quote.first() {
                    if let Some(closes) = &indicators.close {
                        let mut clean_timestamps = vec![];
                        let mut clean_prices = vec![];
                        
                        for (i, price_opt) in closes.iter().enumerate() {
                            if let Some(p) = price_opt {
                                clean_timestamps.push(timestamps[i]);
                                clean_prices.push(*p);
                                
                                // Fallback for Open Price logic:
                                // If meta.regularMarketOpen is 0, try to find the price at 09:30 ET
                                // 09:30 ET is roughly the start of regular trading.
                                // We check if this timestamp corresponds to ~09:30
                                if self.data.open == 0.0 {
                                    let dt = Utc.timestamp_opt(timestamps[i], 0).unwrap().with_timezone(&Eastern);
                                    let t = dt.time();
                                    // If time is >= 09:30:00, take this as open
                                    if t.hour() > 9 || (t.hour() == 9 && t.minute() >= 30) {
                                         self.data.open = *p;
                                    }
                                }
                            }
                        }
                        self.data.timestamps = clean_timestamps;
                        self.data.prices = clean_prices;
                    }
                }
            }
            // Final fallback: if still 0, use first available price?
            if self.data.open == 0.0 && !self.data.prices.is_empty() {
                self.data.open = self.data.prices[0];
            }
        }
     }
    
    pub fn toggle_pre_market(&mut self) {
        self.show_pre_market = !self.show_pre_market;
    }
}

// Yahoo Finance API Response Structs
#[derive(Deserialize, Debug)]
pub struct YFResponse {
    chart: ChartContent,
}

#[derive(Deserialize, Debug)]
struct ChartContent {
    result: Vec<ChartResult>,
}

#[derive(Deserialize, Debug)]
struct ChartResult {
    meta: ChartMeta,
    timestamp: Option<Vec<i64>>,
    indicators: ChartIndicators,
}

#[derive(Deserialize, Debug)]
struct ChartMeta {
    currency: String,
    symbol: String,
    #[serde(rename = "regularMarketPrice")]
    regular_market_price: f64,
    #[serde(rename = "chartPreviousClose")]
    #[serde(default)]
    chart_previous_close: f64,
    #[serde(rename = "regularMarketDayHigh")]
    #[serde(default)]
    regular_market_day_high: f64,
    #[serde(rename = "regularMarketDayLow")]
    #[serde(default)]
    regular_market_day_low: f64,
    #[serde(rename = "regularMarketVolume")]
    #[serde(default)]
    regular_market_volume: u64,
    #[serde(rename = "regularMarketOpen")]
    #[serde(default)]
    regular_market_open: f64,
}

#[derive(Deserialize, Debug)]
struct ChartIndicators {
    quote: Vec<ChartQuote>,
}

#[derive(Deserialize, Debug)]
struct ChartQuote {
    close: Option<Vec<Option<f64>>>,
}

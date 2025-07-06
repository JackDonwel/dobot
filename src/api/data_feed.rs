

// src/api/data_feed.rs
// This file will manage real-time market data streams (e.g., WebSocket connections).
// It will be responsible for connecting to the exchange's data feed,
// processing incoming messages, and potentially pushing them to the core engine.

use futures_util::{StreamExt, SinkExt}; // For async streams and sinks
use tokio_tungstenite::{connect_async, tungstenite::protocol::Message}; // For WebSocket client
use url::Url; // For parsing URLs
use serde::{Deserialize, Serialize}; // For JSON serialization/deserialization

// --- Configuration ---
// Binance WebSocket Stream Base URL
const BINANCE_WS_BASE_URL: &str = "wss://stream.binance.com:9443/ws";
const BINANCE_WS_TESTNET_URL: &str = "wss://testnet.binance.vision/ws";

// --- Data Structures ---
// Example struct for a WebSocket Ticker message
#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")] // Map JSON camelCase to Rust snake_case
pub struct WebSocketTickerMessage {
    #[serde(rename = "e")] // Event type
    pub event_type: String,
    #[serde(rename = "E")] // Event time
    pub event_time: u64,
    #[serde(rename = "s")] // Symbol
    pub symbol: String,
    #[serde(rename = "p")] // Price change
    pub price_change: String,
    #[serde(rename = "P")] // Price change percent
    pub price_change_percent: String,
    #[serde(rename = "w")] // Weighted average price
    pub weighted_avg_price: String,
    #[serde(rename = "x")] // First trade price
    pub first_trade_price: String,
    #[serde(rename = "c")] // Last price
    pub last_price: String,
    #[serde(rename = "Q")] // Last quantity
    pub last_quantity: String,
    #[serde(rename = "b")] // Best bid price
    pub best_bid_price: String,
    #[serde(rename = "B")] // Best bid quantity
    pub best_bid_quantity: String,
    #[serde(rename = "a")] // Best ask price
    pub best_ask_price: String,
    #[serde(rename = "A")] // Best ask quantity
    pub best_ask_quantity: String,
    #[serde(rename = "o")] // Open price
    pub open_price: String,
    #[serde(rename = "h")] // High price
    pub high_price: String,
    #[serde(rename = "l")] // Low price
    pub low_price: String,
    #[serde(rename = "v")] // Total traded base asset volume
    pub total_traded_base_asset_volume: String,
    #[serde(rename = "q")] // Total traded quote asset volume
    pub total_traded_quote_asset_volume: String,
    #[serde(rename = "O")] // Statistics open time
    pub statistics_open_time: u64,
    #[serde(rename = "C")] // Statistics close time
    pub statistics_close_time: u64,
    #[serde(rename = "F")] // First trade ID
    pub first_trade_id: u64,
    #[serde(rename = "L")] // Last trade ID
    pub last_trade_id: u64,
    #[serde(rename = "n")] // Total number of trades
    pub total_number_of_trades: u64,
}


/// Manages real-time market data streams from an exchange.
pub struct MarketDataFeed {
    ws_url: String,
    // You might want to add a channel here to send parsed data to the engine
    // e.g., `tokio::sync::mpsc::Sender<MarketDataEvent>`
}

impl MarketDataFeed {
    /// Creates a new MarketDataFeed instance.
    ///
    /// # Arguments
    /// * `use_testnet` - If true, connects to the Binance testnet WebSocket.
    pub fn new(use_testnet: bool) -> Self {
        let ws_url = if use_testnet {
            BINANCE_WS_TESTNET_URL.to_string()
        } else {
            BINANCE_WS_BASE_URL.to_string()
        };
        MarketDataFeed { ws_url }
    }

    /// Connects to the WebSocket data stream for a given symbol and stream type.
    /// This function will continuously listen for messages.
    ///
    /// # Arguments
    /// * `symbol` - The trading pair symbol (e.g., "btcusdt").
    /// * `stream_type` - The type of stream (e.g., "@miniTicker", "@depth").
    /// * `data_sender` - A channel sender to send parsed market data to the core engine.
    pub async fn connect_and_listen<T>(
        &self,
        symbol: &str,
        stream_type: &str,
        // In a real scenario, `data_sender` would be a channel to send data to the engine
        // data_sender: tokio::sync::mpsc::Sender<T>,
    ) -> Result<(), Box<dyn std::error::Error + Send + Sync>>
    where
        T: for<'de> Deserialize<'de> + std::fmt::Debug + Send + 'static, // Ensure T can be deserialized and debug printed
    {
        let url = Url::parse(&format!("{}/{}", self.ws_url, format!("{}{}", symbol.to_lowercase(), stream_type)))?;
        println!("Connecting to WebSocket: {}", url);

        let (ws_stream, _) = connect_async(url).await?;
        println!("WebSocket connected for {}!", symbol);

        let (mut write, mut read) = ws_stream.split();

        // Example: Send a subscription message (if required by the API, e.g., for combined streams)
        // let subscribe_message = r#"{
        //     "method": "SUBSCRIBE",
        //     "params": [
        //         "btcusdt@miniTicker"
        //     ],
        //     "id": 1
        // }"#;
        // write.send(Message::Text(subscribe_message.to_string())).await?;

        while let Some(message) = read.next().await {
            match message {
                Ok(msg) => {
                    match msg {
                        Message::Text(text) => {
                            // println!("Received: {}", text);
                            // Parse the JSON message into the appropriate data structure
                            match serde_json::from_str::<T>(&text) {
                                Ok(data) => {
                                    // In a real application, you would send this data
                                    // to the core engine via a channel.
                                    // For now, just print it.
                                    println!("Parsed data: {:?}", data);
                                    // data_sender.send(data).await?;
                                }
                                Err(e) => {
                                    eprintln!("Failed to parse WebSocket message: {:?} - {}", text, e);
                                }
                            }
                        }
                        Message::Ping(pong) => {
                            write.send(Message::Pong(pong)).await?;
                        }
                        Message::Close(close_frame) => {
                            println!("WebSocket closed: {:?}", close_frame);
                            break;
                        }
                        _ => {} // Ignore other message types like Binary, Frame, etc.
                    }
                }
                Err(e) => {
                    eprintln!("WebSocket error: {}", e);
                    break;
                }
            }
        }
        Ok(())
    }
}
// Example usage of MarketDataFeed

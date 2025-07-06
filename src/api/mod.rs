pub mod binance;
pub mod data_feed;

// You can add common API-related structs or traits here if needed.
// For example, a generic `ExchangeClient` trait that `binance` can implement.
pub trait ExchangeClient {
    // Define common methods for interacting with an exchange, e.g.,
    // fn get_order_book(&self, symbol: &str) -> Result<OrderBook, ApiError>;
    // fn place_order(&self, order: Order) -> Result<OrderConfirmation, ApiError>;
}

// A simple error type for API operations
#[derive(Debug)]
pub enum ApiError {
    NetworkError(String),
    ParseError(String),
    ExchangeError(String),
    // Add more specific error types as needed
}
impl std::fmt::Display for ApiError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            ApiError::NetworkError(e) => write!(f, "Network error: {}", e),
            ApiError::ParseError(e) => write!(f, "Parsing error: {}", e),
            ApiError::ExchangeError(e) => write!(f, "Exchange error: {}", e),
        }
    }
}

impl std::error::Error for ApiError {}

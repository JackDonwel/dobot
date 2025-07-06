mod engine;
mod strategy;
mod risk_firewall;
mod ui;
mod api;

#[tokio::main]
async fn main() {
    // Initialize trading core
    let mut engine = engine::TradingEngine::new();
    
    // Start UI in separate thread
    let ui_handle = tokio::spawn(async {
        ui::start_web_ui().await.expect("UI failed to start");
    });
    
    // Start trading loop
    let trading_handle = tokio::spawn(async move {
        engine.run().await.expect("Trading engine failed");
    });
    
    tokio::try_join!(ui_handle, trading_handle).unwrap();
}

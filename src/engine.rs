
pub struct TradingEngine {
    strategy: Box<dyn Strategy>,
    risk: RiskFirewall,
    ui_sender: Option<Sender<UiEvent>>,  // Channel to UI
}

impl TradingEngine {
    pub fn new() -> Self {
        Self {
            strategy: BinanceScalper::new(),
            risk: RiskFirewall::with_thresholds(0.9, 0.02), // 90% win rate, 2% DD
            ui_sender: None,
        }
    }
    
    pub fn attach_ui(&mut self, sender: Sender<UiEvent>) {
        self.ui_sender = Some(sender);
    }
    
    async fn send_ui_update(&mut self, event: UiEvent) {
        if let Some(sender) = &self.ui_sender {
            sender.send(event).await.unwrap();
        }
    }
    
    pub async fn run(&mut self) -> Result<()> {
        while let Some(tick) = data_feed::next_tick().await {
            let signal = self.strategy.analyze(&tick);
            
            if self.risk.approve(&signal) {
                let trade = self.execute(signal).await?;
                self.send_ui_update(UiEvent::TradeExecuted(trade.clone())).await;
                
                if trade.is_win() {
                    self.risk.record_win();
                } else {
                    self.risk.record_loss();
                }
            }
            
            self.send_ui_update(UiEvent::MarketUpdate(tick)).await;
        }
        Ok(())
    }
}
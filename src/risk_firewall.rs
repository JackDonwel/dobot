
pub struct RiskFirewall {
    win_rate_target: f64,
    max_drawdown: f64,
    wins: usize,
    losses: usize,
}

impl RiskFirewall {
    pub fn with_thresholds(win_rate: f64, drawdown: f64) -> Self {
        Self {
            win_rate_target: win_rate,
            max_drawdown: drawdown,
            wins: 0,
            losses: 0,
        }
    }
    
    pub fn current_win_rate(&self) -> f64 {
        if self.wins + self.losses == 0 { 0.0 } 
        else { self.wins as f64 / (self.wins + self.losses) as f64 }
    }
    
    pub fn approve(&mut self, signal: &Signal) -> bool {
        // Reject if below win rate threshold
        if self.current_win_rate() < self.win_rate_target - 0.05 {
            return false;
        }
        
        // Position sizing based on performance
        let risk_factor = (self.current_win_rate() / self.win_rate_target).min(1.0);
        signal.position_size *= risk_factor;
        
        true
    }
    
    pub fn record_win(&mut self) {
        self.wins += 1;
    }
    
    pub fn record_loss(&mut self) {
        self.losses += 1;
        // Implement circuit breaker
        if self.losses >= 3 && self.current_win_rate() < 0.85 {
            panic!("Risk circuit breaker triggered!");
        }
    }
}
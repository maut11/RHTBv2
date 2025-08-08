# config.py
MAX_PCT_PORTFOLIO = 0.05
MAX_DOLLAR_AMOUNT = 20000
MIN_TRADE_QUANTITY = 1
BUY_PRICE_PADDING = 0.02

POSITION_SIZE_MULTIPLIERS = { "lotto": 0.10, "small": 0.25, "half": 0.50, "full": 1.00 }

CHANNELS_CONFIG = {
    # --- LIVE CHANNELS ---
    1396011198343811102: { # Ryan's Live ID
        "name": "Ryan", "mode": "live", "multiplier": 1.0,
        "initial_stop_loss": 0.35, "trailing_stop_loss_pct": 0.20,
    },
    1399289540484530247: { # Eva's Live ID
        "name": "Eva", "mode": "live", "multiplier": 0.7,
        "initial_stop_loss": 0.35, "trailing_stop_loss_pct": 0.20,
    },

    # --- TEST CHANNELS ---
    1398585430617886720: { # Will's Live ID (set to test mode)
        "name": "Will", "mode": "test", "multiplier": 1.0,
        "initial_stop_loss": 0.35, "trailing_stop_loss_pct": 0.20,
    },
    1398211580470235176: { # Sean's Live ID (set to test mode)
        "name": "Sean", "mode": "test", "multiplier": 1.0,
        "initial_stop_loss": 0.35, "trailing_stop_loss_pct": 0.20,
    },
    1402850612995031090: { # FiFi's Live ID (set to test mode)
        "name": "FiFi", "mode": "test", "multiplier": 1.0,
        "initial_stop_loss": 0.30, "trailing_stop_loss_pct": 0.15,
    },
}
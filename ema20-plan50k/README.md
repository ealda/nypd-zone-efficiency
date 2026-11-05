# EMA 20 · Plan 50K: TradingView strategy + NinjaTrader 8 bot

This folder implements the rule from abel.nq's guide *"La EMA en la 50K"* (LucidFlex 50K, no DLL). The signal logic copies his published TradingView indicator (`indicador-ema-50k.txt`, linked from page 10 of the guide).

| File | What it is |
|---|---|
| `EMA20_Plan50K_Strategy.pine` | TradingView Pine v6 **strategy**: LONG/SHORT signals, orders, TP/SL, session flatten, alerts, backtest |
| `EMA20Plan50K.cs` | NinjaTrader 8 **strategy** with an Evaluation / Funded switch |

## The rule (5-minute NQ / MNQ)

1. **Direction.** If the EMA 20 is rising (`EMA > EMA[1]`), take longs only. If it is falling, take shorts only.
2. **Touch.** Long: the bar's low reaches the previous EMA value (`Low <= EMA[1]`). Short: the bar's high reaches it (`High >= EMA[1]`).
3. **Close in favour.** The same bar closes back on the trend side (`Close > EMA[1]` for longs, `Close < EMA[1]` for shorts). Enter at market on the **next bar's open**.
4. The signal bar must **open** inside the NY window. Take at most one signal per day (the first one), then stop trading for the day.

## Plans

| Plan | Size | $/pt | TP | SL | Window (NY) |
|---|---|---|---|---|---|
| Evaluation | 1 NQ (= 10 MNQ) | 20 | 75 pts = +$1,500 | 100 pts = −$2,000 (whole cushion) | 9:00–15:00 |
| Funded · big day (first day) | 2 NQ (= 20 MNQ) | 40 | 100 pts = +$4,000 | 50 pts = −$2,000 | 9:00–15:00 |
| Funded · small days | 3 MNQ | 6 | 25 pts = +$150 | remaining cushion, in points | 3:00–15:00 |

Two winning days of $1,500 pass the $3,000 evaluation target and keep the consistency rule at exactly 50%. The guide's payout routine: after 5 days of at least $150, request half the profit (cap $2,000) at a 90% split, up to 4 payouts. **The bots do not request payouts.** You do that by hand.

## TradingView

1. Open **MNQ1!** on a **5-minute** chart. MNQ sizes every plan in whole contracts (10 / 20 / 3). On NQ1! the small day would be 0.3 contracts.
2. Open Pine Editor, paste `EMA20_Plan50K_Strategy.pine`, and click **Add to chart**.
3. In Settings → Inputs, pick the **Plan**. For small days, enter **Small-day stop (points)** as your remaining cushion ÷ 6.
4. Settings → Properties: add commissions and slippage. The script leaves both at zero, as the guide's numbers do.
5. Alerts: Create alert → Condition: *EMA 20 · Plan 50K Strategy* → **"alert() function calls only"** for readable text, or **"Order fills only"** for JSON webhook messages (`{"action":"buy","plan":...,"qty":...,"tp_pts":...,"sl_pts":...}`).

The panel in the top-right corner shows contracts, TP and SL in dollars, and the window. It turns orange if the chart is not on 5 minutes or the size comes out fractional.

## NinjaTrader 8

1. **Tools → NinjaScript Editor → Strategies → New**. Replace the contents with `EMA20Plan50K.cs` and press **F5** to compile.
2. Add the strategy to a **5-minute NQ or MNQ chart** and pick your prop account in the strategy dialog.
3. Set **Account mode**:
   - **Evaluation**: $20/pt, TP 75, SL 100. With *Use account rules* on, the bot stops trading once `cash − Starting balance ≥ Eval profit target` (default $3,000) and prints a message telling you to switch to Funded.
   - **Funded**: choose **Funded day**:
     - **Auto** (default): big day while account profit ≤ 0, small days once profit > 0.
     - **BigDay**: trades the big-day plan once, then switches itself to small days for the rest of that run. If you restart the bot, set it to SmallDay or Auto.
     - **SmallDay**: always 3 MNQ / TP 25.
4. **Small-day stop.** *ManualPoints* uses *Small day stop (pts)*. *AccountCushion* computes `(cash − Liquidation threshold − buffer) ÷ 6` live. Copy the liquidation threshold from the Lucid dashboard and update it when it trails.
5. If you set *Liquidation threshold*, no stop (eval, big or small) can be larger than the real cushion. The bot skips the trade if the cushion is below *Min small-day stop*.

**Sizing.** Contracts = plan $/pt ÷ instrument point value. Eval and big day work on NQ or MNQ. Small day needs **MNQ**. On NQ the bot refuses the trade and prints why.

**Backtests.** Account rules apply only in real time. In Strategy Analyzer the bot trades the fixed plan, and *Auto* uses the strategy's own cumulative P&L as "account profit".

## Choices and assumptions to check

- **Window start uses the signal bar's open time**, as in the published indicator. The guide's 4 August example (touch at 8:55, entry at 9:00) would be **filtered out** by that code. If you want that trade, set *From hour* to 8.
- **Session flatten at 16:45 NY** is my addition. The guide shows a trade "closed at the end of the session" (6 August, −$528) without giving a time. Set it to your firm's flat-by time.
- Lucid's rules (drawdown type, flat-by time, payout terms) change. Confirm them before trading live.
- The performance numbers in the guide (35.5% pass rate, +$101k over 2 years) are the author's simulation. Neither script reproduces or verifies them.
- Neither file has been compiled. No Pine or NinjaTrader compiler was available when they were written. Compile both, then run them on a **sim account** before connecting a funded account.

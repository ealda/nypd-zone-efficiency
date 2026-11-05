// EMA20Plan50K: NinjaTrader 8 strategy
// Port of abel.nq's "EMA 20 · Plan 50K" rule (LucidFlex 50K, no DLL) with separate behaviour for
// EVALUATION and FUNDED accounts.
//
// Signal (5-minute NQ / MNQ, identical to the author's TradingView indicator):
//   Long : EMA[0] > EMA[1]  and  Low[0]  <= EMA[1]  and  Close[0] > EMA[1]
//   Short: EMA[0] < EMA[1]  and  High[0] >= EMA[1]  and  Close[0] < EMA[1]
//   Signal bar must OPEN inside the NY window. Entry = market at the next bar's open. Max N signals per day.
//
// Account modes:
//   Evaluation  -> $20/pt (1 NQ or 10 MNQ), TP 75 pts, SL 100 pts, window 9-15 NY.
//                  With account rules on: stops trading once the profit target is reached,
//                  and never risks more than the cushion above the liquidation threshold.
//   Funded      -> Big day (first day): $40/pt (2 NQ or 20 MNQ), TP 100, SL 50, window 9-15 NY.
//                  Small days: $6/pt (3 MNQ), TP 25, SL = remaining cushion, window 3-15 NY.
//                  FundedDay = Auto picks Big day while account profit <= 0, Small day once profit > 0.
//                  FundedDay = BigDay switches itself to Small day after the big-day trade closes.
//
// Install: NinjaScript Editor > New Strategy (or Tools > Import) > paste this file > F5 to compile.
// Apply to a 5-minute NQ or MNQ chart. Check the Account selected in the strategy dialog.

#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using NinjaTrader.NinjaScript.Indicators;
#endregion

public enum Ema20AccountMode { Evaluation, Funded }
public enum Ema20FundedDay { Auto, BigDay, SmallDay }
public enum Ema20SmallStopMode { ManualPoints, AccountCushion }

namespace NinjaTrader.NinjaScript.Strategies
{
    public class EMA20Plan50K : Strategy
    {
        private enum DayType { Eval, Big, Small }

        private const string LongName  = "EMA20 Long";
        private const string ShortName = "EMA20 Short";

        private EMA ema;
        private TimeZoneInfo nyTz;

        private DateTime currentNyDate = DateTime.MinValue;
        private int signalsToday;
        private bool evalPassed;
        private bool bigDayDone;

        // Trade being drawn / tracked
        private DayType tradeDayType;
        private double tradeTpPts, tradeSlPts;
        private int entryBar = -1;
        private double entryPx, tpPx, slPx;
        private string lineTag;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "EMA 20 touch-and-close rule with separate Evaluation / Funded sizing (Plan 50K).";
                Name = "EMA20Plan50K";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                IsFillLimitOnTouch = false;
                MaximumBarsLookBack = MaximumBarsLookBack.TwoHundredFiftySix;
                OrderFillResolution = OrderFillResolution.Standard;
                Slippage = 0;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                TraceOrders = false;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 20;
                IsInstantiatedOnEachOptimizationIteration = true;

                // 1. Mode
                AccountMode = Ema20AccountMode.Evaluation;
                FundedDay = Ema20FundedDay.Auto;

                // 2. Signal
                EmaPeriod = 20;
                StartHour = 9;
                SmallDayStartHour = 3;
                EndHour = 15;
                SignalsPerDay = 1;
                FlattenHour = 16;
                FlattenMinute = 45;

                // 3. Evaluation plan
                EvalUsdPerPoint = 20;
                EvalTpPoints = 75;
                EvalSlPoints = 100;

                // 4. Funded plan
                BigUsdPerPoint = 40;
                BigTpPoints = 100;
                BigSlPoints = 50;
                SmallUsdPerPoint = 6;
                SmallTpPoints = 25;
                SmallStopMode = Ema20SmallStopMode.ManualPoints;
                SmallSlPoints = 300;
                MinSmallSlPoints = 25;

                // 5. Account rules (real-time only)
                UseAccountRules = true;
                StartingBalance = 50000;
                EvalProfitTarget = 3000;
                LiquidationThreshold = 0;
                CushionBufferUsd = 50;
            }
            else if (State == State.DataLoaded)
            {
                ema = EMA(EmaPeriod);
                ema.Plots[0].Brush = Brushes.RoyalBlue;
                ema.Plots[0].Width = 3;
                AddChartIndicator(ema);

                nyTz = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");

                if (BarsPeriod.BarsPeriodType != BarsPeriodType.Minute || BarsPeriod.Value != 5)
                    Print(Name + ": WARNING, the rule was designed for 5-minute bars. Current: " + BarsPeriod);
            }
        }

        // ───────────────────────── Main loop ─────────────────────────
        protected override void OnBarUpdate()
        {
            if (BarsInProgress != 0 || CurrentBar < Math.Max(BarsRequiredToTrade, 2))
                return;

            DateTime nyClose = ToNy(Time[0]);
            DateTime nyOpen  = ToNy(BarOpenTime());

            // New NY calendar day -> reset the daily counter (same as the indicator).
            if (nyOpen.Date != currentNyDate)
            {
                currentNyDate = nyOpen.Date;
                signalsToday = 0;
            }

            UpdateTradeLines();

            // Flatten anything still open at the flat-by time (before the 18:00 reopen).
            TimeSpan flatAt = new TimeSpan(FlattenHour, FlattenMinute, 0);
            if (Position.MarketPosition != MarketPosition.Flat
                && nyClose.TimeOfDay >= flatAt && nyClose.TimeOfDay < new TimeSpan(18, 0, 0))
            {
                if (Position.MarketPosition == MarketPosition.Long)  ExitLong("Session flat", LongName);
                if (Position.MarketPosition == MarketPosition.Short) ExitShort("Session flat", ShortName);
                return;
            }

            DayType dayType = CurrentDayType();
            int startHr = dayType == DayType.Small ? SmallDayStartHour : StartHour;
            bool inWindow = nyOpen.Hour >= startHr && nyOpen.Hour < EndHour;

            double e0 = ema[0], e1 = ema[1];
            bool longSig  = inWindow && signalsToday < SignalsPerDay && e0 > e1 && Low[0]  <= e1 && Close[0] > e1;
            bool shortSig = inWindow && signalsToday < SignalsPerDay && e0 < e1 && High[0] >= e1 && Close[0] < e1;

            if (!longSig && !shortSig)
                return;

            signalsToday++;
            DrawSignal(longSig);

            if (Position.MarketPosition != MarketPosition.Flat)
                return;

            int qty; double tpPts, slPts; string why;
            if (!ResolvePlan(dayType, out qty, out tpPts, out slPts, out why))
            {
                Print(string.Format("{0} {1}: signal skipped: {2}", Name, nyClose, why));
                return;
            }

            tradeDayType = dayType;
            tradeTpPts = tpPts;
            tradeSlPts = slPts;

            int tpTicks = (int)Math.Round(tpPts / TickSize);
            int slTicks = (int)Math.Round(slPts / TickSize);
            string sigName = longSig ? LongName : ShortName;

            SetProfitTarget(sigName, CalculationMode.Ticks, tpTicks);
            SetStopLoss(sigName, CalculationMode.Ticks, slTicks, false);

            if (longSig) EnterLong(qty, LongName);
            else         EnterShort(qty, ShortName);

            Print(string.Format("{0} {1}: {2} {3} x{4} | plan {5} | TP {6} pts / SL {7} pts",
                Name, nyClose, longSig ? "BUY" : "SELL", Instrument.FullName, qty, dayType, tpPts, slPts));
        }

        // ───────────────────────── Plan logic ─────────────────────────
        private DayType CurrentDayType()
        {
            if (AccountMode == Ema20AccountMode.Evaluation)
                return DayType.Eval;

            switch (FundedDay)
            {
                case Ema20FundedDay.BigDay:
                    return bigDayDone ? DayType.Small : DayType.Big;
                case Ema20FundedDay.SmallDay:
                    return DayType.Small;
                default: // Auto: big day until the account is in profit, then small days.
                    return AccountProfit() > 0 ? DayType.Small : DayType.Big;
            }
        }

        private bool ResolvePlan(DayType dayType, out int qty, out double tpPts, out double slPts, out string why)
        {
            qty = 0; tpPts = 0; slPts = 0; why = null;
            double usdPerPt;

            switch (dayType)
            {
                case DayType.Eval:
                    usdPerPt = EvalUsdPerPoint; tpPts = EvalTpPoints; slPts = EvalSlPoints;
                    if (AccountRulesActive())
                    {
                        if (evalPassed || AccountProfit() >= EvalProfitTarget)
                        {
                            evalPassed = true;
                            why = "evaluation profit target reached. Switch AccountMode to Funded once the account is funded.";
                            return false;
                        }
                        double cushionPts = CushionPoints(usdPerPt);
                        if (!double.IsNaN(cushionPts) && cushionPts < slPts)
                            slPts = Math.Floor(cushionPts); // the stop is "all the cushion", never more
                    }
                    break;

                case DayType.Big:
                    usdPerPt = BigUsdPerPoint; tpPts = BigTpPoints; slPts = BigSlPoints;
                    if (AccountRulesActive())
                    {
                        double cushionPts = CushionPoints(usdPerPt);
                        if (!double.IsNaN(cushionPts) && cushionPts < slPts)
                            slPts = Math.Floor(cushionPts);
                    }
                    break;

                default: // Small
                    usdPerPt = SmallUsdPerPoint; tpPts = SmallTpPoints; slPts = SmallSlPoints;
                    if (AccountRulesActive())
                    {
                        double cushionPts = CushionPoints(usdPerPt);
                        if (SmallStopMode == Ema20SmallStopMode.AccountCushion)
                        {
                            if (double.IsNaN(cushionPts))
                            {
                                why = "SmallStopMode = AccountCushion needs LiquidationThreshold > 0.";
                                return false;
                            }
                            slPts = Math.Floor(cushionPts);
                        }
                        else if (!double.IsNaN(cushionPts) && cushionPts < slPts)
                            slPts = Math.Floor(cushionPts); // manual stop never larger than the real cushion
                    }
                    break;
            }

            if (slPts < (dayType == DayType.Small ? MinSmallSlPoints : 1))
            {
                why = string.Format("cushion too small (stop would be {0} pts).", slPts);
                return false;
            }

            double pointValue = Instrument.MasterInstrument.PointValue;
            double raw = usdPerPt / pointValue;
            qty = (int)Math.Round(raw);
            if (qty < 1 || Math.Abs(raw - qty) > 1e-6)
            {
                why = string.Format("plan needs ${0}/pt = {1:0.##} contracts of {2} (${3}/pt). Use MNQ for this plan.",
                    usdPerPt, raw, Instrument.MasterInstrument.Name, pointValue);
                return false;
            }
            return true;
        }

        private bool AccountRulesActive()
        {
            return UseAccountRules && State == State.Realtime && Account != null;
        }

        // Real time with account rules: real account balance. Otherwise (backtest / historical): strategy P&L.
        private double AccountProfit()
        {
            if (AccountRulesActive())
                return Account.Get(AccountItem.CashValue, Currency.UsDollar) - StartingBalance;
            return SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
        }

        // Distance to the liquidation threshold, in points for the given $/pt. NaN if no threshold set.
        private double CushionPoints(double usdPerPt)
        {
            if (LiquidationThreshold <= 0)
                return double.NaN;
            double cash = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            double cushionUsd = cash - LiquidationThreshold - CushionBufferUsd;
            return Math.Max(0, cushionUsd / usdPerPt);
        }

        // ───────────────────────── Execution tracking ─────────────────────────
        protected override void OnExecutionUpdate(Execution execution, string executionId, double price, int quantity,
            MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution.Order == null || execution.Order.OrderState != OrderState.Filled)
                return;

            string n = execution.Order.Name;
            if (n == LongName || n == ShortName)
            {
                int dir = n == LongName ? 1 : -1;
                entryBar = CurrentBar;
                entryPx = execution.Order.AverageFillPrice;
                tpPx = entryPx + dir * tradeTpPts;
                slPx = entryPx - dir * tradeSlPts;
                lineTag = "trade" + CurrentBar;
                UpdateTradeLines();
            }
        }

        protected override void OnPositionUpdate(Position position, double averagePrice, int quantity, MarketPosition marketPosition)
        {
            if (marketPosition != MarketPosition.Flat)
                return;

            UpdateTradeLines();
            entryBar = -1;

            if (tradeDayType == DayType.Big && AccountMode == Ema20AccountMode.Funded && !bigDayDone)
            {
                bigDayDone = true;
                Print(Name + ": big-day trade closed. Next trades use the SMALL-DAY plan. "
                    + "If you restart the strategy, set FundedDay = SmallDay (or Auto).");
            }
        }

        // ───────────────────────── Drawing ─────────────────────────
        private void DrawSignal(bool isLong)
        {
            string tag = "sig" + CurrentBar;
            if (isLong)
            {
                Draw.ArrowUp(this, tag, false, 0, Low[0] - 4 * TickSize, Brushes.SeaGreen);
                Draw.Text(this, tag + "t", "LONG", 0, Low[0] - 16 * TickSize, Brushes.SeaGreen);
            }
            else
            {
                Draw.ArrowDown(this, tag, false, 0, High[0] + 4 * TickSize, Brushes.Crimson);
                Draw.Text(this, tag + "t", "SHORT", 0, High[0] + 16 * TickSize, Brushes.Crimson);
            }
        }

        // Entry / TP / SL segments that grow while the trade is open.
        private void UpdateTradeLines()
        {
            if (entryBar < 0 || lineTag == null || CurrentBar < entryBar)
                return;
            int ago = CurrentBar - entryBar;
            Draw.Line(this, lineTag + "e", false, ago, entryPx, 0, entryPx, Brushes.Gray, DashStyleHelper.Dash, 2);
            Draw.Line(this, lineTag + "tp", false, ago, tpPx, 0, tpPx, Brushes.SeaGreen, DashStyleHelper.Solid, 3);
            Draw.Line(this, lineTag + "sl", false, ago, slPx, 0, slPx, Brushes.Crimson, DashStyleHelper.Solid, 3);
        }

        // ───────────────────────── Time helpers ─────────────────────────
        // NinjaTrader time stamps bars at their CLOSE; the rule uses the bar's OPEN hour.
        private DateTime BarOpenTime()
        {
            if (BarsPeriod.BarsPeriodType == BarsPeriodType.Minute)
                return Time[0].AddMinutes(-BarsPeriod.Value);
            return Time[1];
        }

        private DateTime ToNy(DateTime t)
        {
            return TimeZoneInfo.ConvertTime(DateTime.SpecifyKind(t, DateTimeKind.Unspecified),
                NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo, nyTz);
        }

        // ───────────────────────── Properties ─────────────────────────
        #region Properties
        [NinjaScriptProperty]
        [Display(Name = "Account mode", Description = "Evaluation or Funded", Order = 1, GroupName = "1. Mode")]
        public Ema20AccountMode AccountMode { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Funded day", Description = "Auto: big day while account profit <= 0, then small days. BigDay switches to SmallDay after its trade closes.", Order = 2, GroupName = "1. Mode")]
        public Ema20FundedDay FundedDay { get; set; }

        [NinjaScriptProperty]
        [Range(2, int.MaxValue)]
        [Display(Name = "EMA period", Order = 1, GroupName = "2. Signal")]
        public int EmaPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "From hour (NY), eval / big day", Order = 2, GroupName = "2. Signal")]
        public int StartHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "From hour (NY), small day", Order = 3, GroupName = "2. Signal")]
        public int SmallDayStartHour { get; set; }

        [NinjaScriptProperty]
        [Range(1, 24)]
        [Display(Name = "Until hour (NY)", Order = 4, GroupName = "2. Signal")]
        public int EndHour { get; set; }

        [NinjaScriptProperty]
        [Range(1, int.MaxValue)]
        [Display(Name = "Signals per day", Order = 5, GroupName = "2. Signal")]
        public int SignalsPerDay { get; set; }

        [NinjaScriptProperty]
        [Range(0, 23)]
        [Display(Name = "Flatten hour (NY)", Order = 6, GroupName = "2. Signal")]
        public int FlattenHour { get; set; }

        [NinjaScriptProperty]
        [Range(0, 59)]
        [Display(Name = "Flatten minute", Order = 7, GroupName = "2. Signal")]
        public int FlattenMinute { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "$ per point", Description = "20 = 1 NQ or 10 MNQ", Order = 1, GroupName = "3. Evaluation plan")]
        public double EvalUsdPerPoint { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Take profit (pts)", Order = 2, GroupName = "3. Evaluation plan")]
        public double EvalTpPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Stop loss (pts)", Order = 3, GroupName = "3. Evaluation plan")]
        public double EvalSlPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Big day $ per point", Description = "40 = 2 NQ or 20 MNQ", Order = 1, GroupName = "4. Funded plan")]
        public double BigUsdPerPoint { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Big day take profit (pts)", Order = 2, GroupName = "4. Funded plan")]
        public double BigTpPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Big day stop loss (pts)", Order = 3, GroupName = "4. Funded plan")]
        public double BigSlPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Small day $ per point", Description = "6 = 3 MNQ", Order = 4, GroupName = "4. Funded plan")]
        public double SmallUsdPerPoint { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Small day take profit (pts)", Order = 5, GroupName = "4. Funded plan")]
        public double SmallTpPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Small day stop mode", Description = "ManualPoints: use the value below. AccountCushion: (cash - liquidation threshold - buffer) / $ per point, real time only.", Order = 6, GroupName = "4. Funded plan")]
        public Ema20SmallStopMode SmallStopMode { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Small day stop (pts)", Description = "Remaining cushion in points (cushion $ / 6).", Order = 7, GroupName = "4. Funded plan")]
        public double SmallSlPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Min small-day stop (pts)", Description = "Skip trading if the cushion-based stop is smaller than this.", Order = 8, GroupName = "4. Funded plan")]
        public double MinSmallSlPoints { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Use account rules (real time)", Description = "Read the live account balance for eval target, cushion caps and Auto funded day.", Order = 1, GroupName = "5. Account rules")]
        public bool UseAccountRules { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Starting balance", Order = 2, GroupName = "5. Account rules")]
        public double StartingBalance { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Eval profit target ($)", Order = 3, GroupName = "5. Account rules")]
        public double EvalProfitTarget { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Liquidation threshold ($)", Description = "Balance at which the prop firm closes the account (from its dashboard). 0 = not used.", Order = 4, GroupName = "5. Account rules")]
        public double LiquidationThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Cushion buffer ($)", Description = "Keep the stop this many dollars above the threshold.", Order = 5, GroupName = "5. Account rules")]
        public double CushionBufferUsd { get; set; }
        #endregion
    }
}

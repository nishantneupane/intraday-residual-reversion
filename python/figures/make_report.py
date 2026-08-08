"""Generate the project research report PDF (Residual_Reversion_Report.pdf)."""
import os
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, Image, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIG = os.path.join(ROOT, "docs", "figures")
OUT = os.path.join(ROOT, "Residual_Reversion_Report.pdf")

INK = colors.HexColor("#2c2c2a")
MUTED = colors.HexColor("#5f5e5a")
ACCENT = colors.HexColor("#184f95")
RULE = colors.HexColor("#d3d1c7")

ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold",
                            fontSize=22, leading=27, textColor=INK, spaceAfter=6),
    "subtitle": ParagraphStyle("st", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=12.5, leading=17, textColor=MUTED,
                               spaceAfter=18),
    "meta": ParagraphStyle("m", parent=ss["Normal"], fontSize=9.5, leading=14,
                           textColor=MUTED),
    "h1": ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                         fontSize=14.5, leading=18, textColor=ACCENT,
                         spaceBefore=18, spaceAfter=8),
    "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                         fontSize=11.5, leading=15, textColor=INK,
                         spaceBefore=12, spaceAfter=5),
    "body": ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica",
                           fontSize=10, leading=14.5, textColor=INK,
                           spaceAfter=7, alignment=4),  # justified
    "abstract": ParagraphStyle("ab", parent=ss["Normal"], fontName="Helvetica",
                               fontSize=10, leading=15, textColor=INK,
                               leftIndent=24, rightIndent=24, spaceAfter=7,
                               alignment=4),
    "caption": ParagraphStyle("cap", parent=ss["Normal"], fontSize=8.5,
                              leading=11.5, textColor=MUTED, spaceBefore=3,
                              spaceAfter=12),
    "eq": ParagraphStyle("eq", parent=ss["Normal"], fontName="Times-Italic",
                         fontSize=10.5, leading=15, textColor=INK,
                         alignment=1, spaceBefore=5, spaceAfter=8),
    "bullet": ParagraphStyle("bl", parent=ss["Normal"], fontSize=10,
                             leading=14.5, textColor=INK, leftIndent=16,
                             bulletIndent=4, spaceAfter=4),
}

def fig(path, width, caption):
    with PILImage.open(path) as im:
        w, h = im.size
    height = width * h / w
    return [Image(path, width=width, height=height),
            Paragraph(caption, S["caption"])]

CELL = ParagraphStyle("cell", parent=ss["Normal"], fontName="Helvetica",
                      fontSize=8.5, leading=10.5, textColor=INK)
CELL_R = ParagraphStyle("cellr", parent=CELL, alignment=2)
CELL_H = ParagraphStyle("cellh", parent=CELL, fontName="Helvetica-Bold",
                        textColor=ACCENT)
CELL_HR = ParagraphStyle("cellhr", parent=CELL_H, alignment=2)

def tbl(data, widths, aligns=None):
    # wrap every cell in a Paragraph so text WRAPS inside its column instead
    # of overflowing across neighbors (plain strings never wrap in reportlab)
    wrapped = []
    for r, row in enumerate(data):
        out_row = []
        for c, cell in enumerate(row):
            right = aligns and c < len(aligns) and aligns[c] == "RIGHT"
            style = (CELL_HR if right else CELL_H) if r == 0 else \
                    (CELL_R if right else CELL)
            out_row.append(Paragraph(str(cell), style))
        wrapped.append(out_row)
    data = wrapped
    t = Table(data, colWidths=widths, hAlign="LEFT")
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, ACCENT),
        ("LINEBELOW", (0, -1), (-1, -1), 0.4, RULE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f5f1")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    if aligns:
        for col, a in enumerate(aligns):
            style.append(("ALIGN", (col, 0), (col, -1), a))
    t.setStyle(TableStyle(style))
    return t

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(0.9 * inch, 0.55 * inch,
                      "Intraday residual reversion in US large-cap equities")
    canvas.drawRightString(letter[0] - 0.9 * inch, 0.55 * inch, f"{doc.page}")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(0.9 * inch, 0.72 * inch, letter[0] - 0.9 * inch, 0.72 * inch)
    canvas.restoreState()

doc = BaseDocTemplate(OUT, pagesize=letter, leftMargin=0.9 * inch,
                      rightMargin=0.9 * inch, topMargin=0.85 * inch,
                      bottomMargin=0.95 * inch,
                      title="Intraday Residual Reversion in US Large-Cap Equities",
                      author="Nishant Neupane")
frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=footer)])

E = []  # the story
P = lambda text, style="body": E.append(Paragraph(text, S[style]))
SP = lambda h=6: E.append(Spacer(1, h))

# ---------------------------------------------------------------- title page
SP(40)
P("Intraday Residual Reversion in US Large-Cap Equities", "title")
P("Signal extraction with a Carhart factor overlay, execution-cost decomposition, "
  "and the limits of liquidity-taking strategies", "subtitle")
E.append(Table([[""]], colWidths=[doc.width], style=TableStyle(
    [("LINEBELOW", (0, 0), (-1, -1), 1, ACCENT)])))
SP(14)
P("Nishant Neupane &nbsp;&nbsp;·&nbsp;&nbsp; August 2026", "meta")
P("Research infrastructure: kdb+/q (KDB-X) · C++20/Eigen · Python", "meta")
P("Data: Alpaca Market Data (IEX feed) · Yahoo Finance · Ken French Data Library", "meta")
SP(26)

P("Abstract", "h1")
P("We test whether idiosyncratic — factor-stripped — intraday price moves in S&amp;P 100 "
  "stocks mean-revert, and whether that reversion is monetizable. Using six years of "
  "one-minute bars (45.6M observations) stored in a date-partitioned kdb+ database, we "
  "estimate rolling Carhart four-factor betas (250-day window, 60-day exponential "
  "half-life; 210,475 weighted regressions) and decompose each stock's 5-minute return "
  "into a market-explained component and a residual. Residual returns exhibit "
  "autocorrelation of −0.038 at the 5-minute lag versus −0.008 for raw returns: factor "
  "stripping deepens measurable reversion roughly five-fold. A linear model on seven "
  "features predicts forward 10-minute residuals with a mean cross-sectional rank IC of "
  "0.022, positive in every purged walk-forward year 2021–2026; a regularized MLP on "
  "identical inputs fails to beat it. Simulated with fills at decision prices, the signal "
  "earns a gross Sharpe of 2.6 and a Carhart alpha of +23.6%/yr (Newey–West t = 4.9) "
  "with market beta 0.02 — genuine, factor-neutral alpha. Simulated with realistic "
  "market-order fills at the next bar's open, gross P&amp;L collapses to approximately zero: "
  "the entire edge is forfeited to bid–ask bounce, and no rebalancing frequency "
  "rescues it. We conclude that short-horizon residual reversion is real but constitutes "
  "the compensation earned by liquidity providers; harvesting it requires passive "
  "execution, which bar-level data cannot credibly simulate. The result is a precise, "
  "reproducible measurement of why an apparent alpha is not free money.", "abstract")
E.append(PageBreak())

# ------------------------------------------------------------ 1 introduction
P("1&nbsp;&nbsp;Introduction and hypothesis", "h1")
P("Short-horizon reversal is one of the oldest regularities in equity microstructure: "
  "stocks that just moved sharply tend to move back. The economic question is <i>which "
  "part</i> of a move reverts. A stock that fell because the entire market fell is not "
  "stretched — betting on its bounce is simply a long market position in disguise. A "
  "stock that fell idiosyncratically — in excess of what its factor exposures explain — "
  "plausibly overshot, and the overshoot is the candidate for reversion.")
P("The project therefore tests a two-part hypothesis: <b>(H1)</b> residual (factor-"
  "stripped) intraday returns mean-revert more strongly than raw returns; <b>(H2)</b> the "
  "reversion survives realistic transaction costs. The design commits, before any "
  "backtest, to reporting negative results with the same prominence as positive ones, and "
  "pre-registers the principal threat to H2: measured short-lag reversion in trade prices "
  "partly reflects bid–ask bounce, which is mechanical and unharvestable by "
  "liquidity takers.")

P("1.1&nbsp;&nbsp;Related work", "h2")
P("This study replicates, at the intraday horizon and on freely available data, a chain "
  "of established results. Short-horizon reversal dates to Lehmann (1990) and Jegadeesh "
  "(1990); Jegadeesh and Titman (1995) and Conrad, Gultekin and Kaul (1997) showed that "
  "much of the measured effect is bid–ask bounce and does not survive trading costs — "
  "the intraday analogue of which is our §4.3 decomposition. Blitz, Huij, Lansdorp and "
  "Verbeek (2013) demonstrated at the monthly horizon that reversal is stronger and more "
  "stable in factor-model <i>residuals</i> than in raw returns, which our Figure 3 "
  "reproduces at five-minute frequency. Nagel (2012) established the now-standard "
  "interpretation that short-term reversal profits are compensation for liquidity "
  "provision; most directly, Brogaard, Han and Kim (2024) document intraday residual "
  "reversal in US equities and reach the same conclusion. Our contribution is not the "
  "anomaly but the independent, fully open replication: a self-built pipeline from raw "
  "public data through factor estimation, leakage-controlled prediction, and an "
  "execution-cost decomposition that agrees with the literature's verdict. Agreement "
  "here is the point — a homegrown pipeline that had instead found a large net-of-costs "
  "alpha would more likely signal a defect in the pipeline than a gap in the market.")

P("2&nbsp;&nbsp;Data", "h1")
E.append(tbl(
    [["Dataset", "Source", "Span", "Size / notes"],
     ["1-min OHLCV bars, 104 stocks + SPY", "Alpaca Market Data API (IEX feed)",
      "Aug 2020 – Aug 2026", "45.6M rows; free tier is a rolling ~6-year window"],
     ["Daily OHLCV (beta run-up)", "Yahoo Finance (yfinance)",
      "2018 – present", "dividend- and split-adjusted (total-return)"],
     ["Carhart factors MKT, SMB, HML, WML, RF", "Ken French Data Library",
      "1926 – present", "daily; monthly refresh cadence"]],
    [1.85 * inch, 1.95 * inch, 1.30 * inch, 1.60 * inch]))
SP(6)
P("The IEX feed represents ~2.5% of US consolidated volume. Prices track the tape "
  "closely for large caps (arbitrage keeps venues aligned); volume levels are "
  "unrepresentative, so volume enters the models only as a <i>relative</i> quantity "
  "(each stock versus its own same-time-of-day history). Universe: current S&amp;P 100 "
  "membership, implying survivorship bias that is disclosed rather than corrected. Data "
  "quality checks caught, among others, a ticker rename (BK→BNY) and a pre-IPO gap "
  "(PLTR); cleaning removed 90,943 extended-hours rows (0.2%) and found zero duplicates. "
  "Cross-source validation: SPY daily returns correlate 0.9948 with the Ken French "
  "market factor over 2,133 shared days, and daily aggregates of the intraday bars "
  "correlate 0.997 with Yahoo's independent series.")
E.extend(fig(os.path.join(FIG, "01_coverage.png"), 5.4 * inch,
             "Figure 1 — Minute-bar coverage by symbol and month. Pale rows are thinly-"
             "traded names on IEX (e.g., BLK); the gray strip is PLTR before its Sept 2020 "
             "IPO; GOOG/GOOGL visibly densify after their July 2022 20-for-1 split."))
E.append(PageBreak())

# ------------------------------------------------------------- 3 methodology
P("3&nbsp;&nbsp;Methodology", "h1")
P("3.1&nbsp;&nbsp;Infrastructure", "h2")
P("All series live in a date-partitioned kdb+ database (one directory per trading day, "
  "one memory-mapped binary file per column, symbols enumerated and parted). The store "
  "holds the raw bars, derived 5-minute bars, the feature/signal table (11.7M rows), "
  "factor and beta tables, and model predictions. Heavy numerics run in C++20: a "
  "rolling-regression engine and an event-driven backtester communicate with the "
  "database over kdb+'s binary IPC protocol via the KX C API, wrapped in RAII. Research "
  "iteration (models, validation, figures) is Python. Every figure and table in this "
  "report regenerates from raw data with documented one-line commands.")
P("3.2&nbsp;&nbsp;Factor model and residual construction", "h2")
P("For each stock <i>i</i> and day <i>t</i>, Carhart four-factor loadings are estimated "
  "by weighted least squares over the trailing 250 trading days with exponentially "
  "decaying weights (half-life 60 days) and ridge damping λ = 10<super>−4</super>:")
P("r<sub>i,τ</sub> − r<sub>f,τ</sub> = α<sub>i</sub> + β<super>MKT</super>MKT<sub>τ</sub> "
  "+ β<super>SMB</super>SMB<sub>τ</sub> + β<super>HML</super>HML<sub>τ</sub> "
  "+ β<super>WML</super>WML<sub>τ</sub> + ε<sub>τ</sub>,"
  "&nbsp;&nbsp;&nbsp;&nbsp;β̂ = (XᵀWX + λI)<super>−1</super>XᵀWy", "eq")
P("Estimates were verified three ways: SPY recovers β<super>MKT</super> = 0.957 with "
  "R² = 0.985 and near-zero style loadings; an independent numpy implementation matches "
  "the C++ output to six decimals; and the cross-sectional R² distribution (median 0.43) "
  "sits where daily single-name factor regressions belong. Intraday, only the market "
  "factor is observable (via SPY's minute bars), so the 5-minute residual is "
  "resid<sub>i,b</sub> = r<sub>i,b</sub> − β̂<super>MKT</super><sub>i</sub>·r<sub>SPY,b</sub>, "
  "using the newest beta dated strictly before the bar's day (an as-of join; no look-ahead). "
  "Style factors are neutralized at the portfolio level instead.")
E.extend(fig(os.path.join(FIG, "03_rolling_betas.png"), 5.9 * inch,
             "Figure 2 — Rolling Carhart betas. The model rediscovers priors from prices "
             "alone: JPM loads persistently positive on value, AAPL negative (growth), XOM's "
             "value loading surges in the 2021–22 energy regime, TSLA's market beta reaches 3."))
P("3.3&nbsp;&nbsp;Features, labels, and leakage control", "h2")
P("Seven features per (stock, 5-minute bucket): trailing 30- and 60-minute residual sums "
  "scaled by the stock's own realized volatility (z30, z60); log realized volatility; log "
  "relative volume surprise versus the same bucket's trailing 20-day mean (excluding the "
  "current day); the clipped overnight gap; and open-hour/close-hour dummies. Labels are "
  "forward residual sums over 10/15/30 minutes, nulled where the window would cross the "
  "close, and never used as features. Validation is a yearly expanding walk-forward with "
  "a 5-trading-day embargo between train and test; features are standardized on training "
  "statistics only. Random K-fold would leak forward-looking labels into training and "
  "silently inflate every metric.")
P("3.4&nbsp;&nbsp;Backtest design", "h2")
P("An event-driven simulator holds a ~$1M gross, dollar-balanced, market-beta-neutral "
  "book: at each decision (every 10 minutes) stocks are ranked by predicted forward "
  "residual; the top and bottom 10 are held long/short (~$50k per name) with hysteresis "
  "exit bands (enter at rank ≤10, exit past rank 25) to damp churn; the short leg is "
  "scaled so summed market betas offset. Orders fill at the <i>next</i> bar's open — "
  "never the decision price. All positions liquidate before the close. Costs: SEC fee "
  "(27.8 per $1M sold), FINRA TAF ($0.000166/share sold, capped), and slippage swept over "
  "0–5 bp per side; because targets do not depend on fills, net P&amp;L is exactly linear "
  "in the slippage rate. A <b>paper-fill mode</b> (fills at the decision price itself — "
  "unattainable, since that print contains the bounce) provides the benchmark that makes "
  "the execution-cost decomposition in §4.3 possible.")
E.append(PageBreak())

# ----------------------------------------------------------------- 4 results
P("4&nbsp;&nbsp;Results", "h1")
P("4.1&nbsp;&nbsp;The reversion signal (H1: supported)", "h2")
E.extend(fig(os.path.join(FIG, "04_residual_autocorr.png"), 5.6 * inch,
             "Figure 3 — Pooled autocorrelation of 5-minute returns by lag, within-day "
             "only. Market-stripping deepens 5-minute-lag reversion from −0.008 to −0.038; "
             "the effect decays to noise within ~15 minutes."))
P("The decay profile drove a design revision: the originally planned 30-minute "
  "prediction horizon was replaced by 10 minutes, where the signal actually lives.")
P("4.2&nbsp;&nbsp;Predictability and the model comparison", "h2")
E.append(tbl(
    [["Label horizon", "Mean OOS R²", "Mean rank IC", "Mean IC t-stat"],
     ["10 minutes", "0.00017", "0.0223", "9.8"],
     ["15 minutes", "0.00012", "0.0213", "8.4"],
     ["30 minutes", "0.00004", "0.0193", "6.3"]],
    [1.5 * inch, 1.4 * inch, 1.4 * inch, 1.5 * inch],
    aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"]))
SP(4)
P("OLS results across six out-of-sample years (2021–2026). The z30 coefficient is "
  "negative in all 18 label-fold fits; rank IC is positive in every fold with visible "
  "attenuation after 2023 (2021–23 ICs of 0.024–0.030 versus 0.011–0.022 in 2024–26) — "
  "alpha decay, disclosed. An IC of 0.022 per rebalance is economically meaningful "
  "through breadth: ~78 cross-sections per day over ~100 names compound a faint edge "
  "(Grinold's fundamental law).")
P("A deliberately small MLP (two hidden layers of 32, dropout, early stopping on a "
  "validation slice of training years) was fit on <i>identical</i> features and folds: "
  "mean rank IC 0.0209 versus 0.0223 for OLS — marginally worse everywhere. At this "
  "signal-to-noise ratio with seven engineered features, the predictive relationship is "
  "essentially linear; additional capacity buys variance, not insight. The linear model "
  "was therefore promoted to production.")
P("4.3&nbsp;&nbsp;Execution: the decomposition (H2: rejected, precisely)", "h2")
E.append(tbl(
    [["Configuration", "Turnover/day", "Gross P&amp;L/day", "Gross Sharpe"],
     ["Paper fills (decision price), 10-min", "$43M", "+$904", "+2.58"],
     ["Market fills (next open), 10-min", "$43M", "−$45", "−0.14"],
     ["Market fills, 30-min rebalance", "$21M", "−$159", "−0.57"],
     ["Market fills, 60-min rebalance", "$11M", "−$69", "−0.29"]],
    [2.5 * inch, 1.3 * inch, 1.35 * inch, 1.3 * inch],
    aligns=["LEFT", "RIGHT", "RIGHT", "RIGHT"]))
SP(4)
P("The ~$950/day gap between paper and market fills is the bid–ask bounce measured "
  "directly: a stock ranked “stretched down” typically printed its last trade at the "
  "bid; the next bar's first trade sits back near mid, and that bounce <i>was</i> most "
  "of the predicted reversion. Slower rebalancing cuts turnover four-fold but leaves "
  "gross P&amp;L at zero — consistent with Figure 3: past ~15 minutes there is nothing "
  "left to collect, while the toll is still paid at entry.")
E.extend(fig(os.path.join(FIG, "07_equity_curves.png"), 5.9 * inch,
             "Figure 4 — Cumulative P&amp;L under three fill assumptions, 2021–2026, on a $1M "
             "gross book. The signal exists (blue), market-order execution forfeits it "
             "(gray), and explicit slippage buries it (orange)."))
E.append(PageBreak())
E.extend(fig(os.path.join(FIG, "09_cost_sensitivity.png"), 5.5 * inch,
             "Figure 5 — Net annualized Sharpe versus assumed per-side slippage, by "
             "rebalance frequency. No liquidity-taking configuration survives."))
P("4.4&nbsp;&nbsp;Attribution: is the paper alpha real alpha?", "h2")
E.append(tbl(
    [["Series", "Alpha (ann.)", "t(α)", "β MKT", "β SMB", "β HML", "β WML", "R²"],
     ["Paper fills, 10-min", "+23.6%", "+4.93", "0.019", "0.014", "−0.015", "0.065", "0.018"],
     ["Market fills, 10-min", "−0.8%", "−0.19", "0.031", "0.016", "−0.012", "0.057", "0.018"]],
    [1.7 * inch, 0.85 * inch, 0.65 * inch, 0.65 * inch, 0.65 * inch, 0.65 * inch, 0.65 * inch, 0.55 * inch],
    aligns=["LEFT"] + ["RIGHT"] * 7))
SP(4)
P("Daily strategy returns regressed on the Carhart factors (Newey–West standard "
  "errors, 5 lags, 1,347 days). The paper series exhibits statistically significant "
  "alpha with economically negligible factor loadings — the neutralization machinery "
  "demonstrably worked, and 98% of P&amp;L variance is idiosyncratic. The measured edge is "
  "genuine alpha; execution, not factor exposure, is what removes it.")

# -------------------------------------------------------------- 5 discussion
P("5&nbsp;&nbsp;Discussion and conclusion", "h1")
P("Short-horizon residual reversion in US large caps is real, statistically robust, and "
  "factor-clean — and it is <b>the fee charged by liquidity providers</b>, not an "
  "inefficiency awaiting a taker. Anyone with bar data can see it; only those resting "
  "passive orders in the queue, bearing adverse-selection risk as quasi-market-makers, "
  "can collect it. A bar-level simulator cannot honestly model queue position, so the "
  "natural sequel is an order-book-level study: IEX publishes full-depth tick data "
  "(DEEP/TOPS) freely, and a C++ feed handler parsing it into this same kdb+ schema "
  "would enable a maker-style backtest with real queue dynamics.")
P("Methodologically, the project's value lies in its verification discipline: every "
  "layer was checked against an independent source (raw files, an alternative data "
  "vendor, a reference implementation, a known-answer instrument) before the next layer "
  "was built, and both pre-registered adverse outcomes — the MLP failing to beat OLS, "
  "and the bounce consuming the edge — were found and reported rather than tuned away. "
  "The strategy verdict is negative; the measurement is the contribution.")

P("6&nbsp;&nbsp;Limitations", "h1")
for item in [
    "Survivorship bias: the universe is current S&amp;P 100 membership; fallen members are absent.",
    "IEX-only feed: prices proxy the consolidated tape well for large caps; volumes are used only relatively.",
    "Six-year sample (free-tier history floor), one market regime family; visible alpha decay after 2023.",
    "Daily betas applied intraday; only the market factor is stripped in real time.",
    "Bar-level fills: no partial fills, queue modeling, or market impact beyond the slippage rate.",
    "No short-borrow costs (second-order for large-cap general collateral at this book size).",
]:
    E.append(Paragraph(f"•&nbsp;&nbsp;{item}", S["bullet"]))
SP(6)
P("<b>Reproducibility.</b> All code, documentation chapters, and figure-generation "
  "scripts live in the project repository; the full pipeline rebuilds from public data "
  "with one-line commands per stage (see README). Data sources: Alpaca Market Data; "
  "Yahoo Finance via yfinance; Kenneth R. French Data Library, Dartmouth.")
P("References", "h1")
for ref in [
    "Blitz, D., J. Huij, S. Lansdorp and M. Verbeek (2013), “Short-Term Residual "
    "Reversal,” <i>Journal of Financial Markets</i> 16(3).",
    "Brogaard, J., J. Han and H. Kim (2024), “Intraday Residual Reversal in the U.S. "
    "Stock Market,” SSRN working paper 4731947.",
    "Carhart, M. (1997), “On Persistence in Mutual Fund Performance,” <i>Journal of "
    "Finance</i> 52(1).",
    "Conrad, J., M. Gultekin and G. Kaul (1997), “Profitability of Short-Term "
    "Contrarian Strategies: Implications for Market Efficiency,” <i>Journal of Business "
    "&amp; Economic Statistics</i> 15(3).",
    "Fama, E. and K. French (1993), “Common Risk Factors in the Returns on Stocks and "
    "Bonds,” <i>Journal of Financial Economics</i> 33(1).",
    "Grinold, R. and R. Kahn (2000), <i>Active Portfolio Management</i>, 2nd ed., "
    "McGraw-Hill.",
    "Jegadeesh, N. (1990), “Evidence of Predictable Behavior of Security Returns,” "
    "<i>Journal of Finance</i> 45(3).",
    "Jegadeesh, N. and S. Titman (1995), “Short-Horizon Return Reversals and the "
    "Bid-Ask Spread,” <i>Journal of Financial Intermediation</i> 4(2).",
    "Lehmann, B. (1990), “Fads, Martingales, and Market Efficiency,” <i>Quarterly "
    "Journal of Economics</i> 105(1).",
    "López de Prado, M. (2018), <i>Advances in Financial Machine Learning</i>, Wiley.",
    "Nagel, S. (2012), “Evaporating Liquidity,” <i>Review of Financial Studies</i> 25(7).",
]:
    E.append(Paragraph(ref, S["bullet"]))

doc.build(E)
print("wrote", OUT)

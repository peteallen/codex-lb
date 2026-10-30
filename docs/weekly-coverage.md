# Weekly coverage

The Dashboard's **Weekly coverage** card estimates whether your eligible accounts
can keep serving work until their weekly allowances reset. It answers a pool-wide
question: if the current pace continues, is there a period when every included
account is empty?

The owning requirements are in the [weekly coverage specification](https://github.com/peteallen/codex-lb/blob/main/openspec/specs/weekly-coverage/spec.md).

## Reading the card

The headline reports the first projected interruption, or that no interruption
is projected within fourteen days. One shared time axis aligns the pool and its
included accounts. The timeline initially shows seven days; select **14d** to see
the full forecast. A gap beyond the initial seven days still appears in the headline.

Blue spans show available quota, brown pool spans mark gaps, and gray account
spans show time empty. Diamonds mark resets; patterned spans mean unknown.
The bars show time, not summed percentages.
Open **Details** for reset dates, calibration evidence, excluded accounts and
forecast limitations. The minimum reserve there translates the pool's lowest
projected remaining allowance into hours at the modeled demand.

**Learning** means there is not enough comparable usage history yet. **Limited**
means an account's evidence or the routing approximation prevents a complete
forecast. Neither state means the pool is safe.

Even in these states, each account with a fresh weekly observation shows its own
percentage-based pace: whether it is on course to last until reset, its expected
remaining allowance then, or when it would run out first. These account projections
include usage outside the proxy because they use the provider's quota counter.
They do not include extra traffic transferred from another exhausted account, so
they are not a substitute for the pooled forecast.

When the pool forecast is uncertain, its row stays gray. Individual account rows
show only the current window; time after each reset stays unknown because those
rows do not model transferred demand or future cycles. Stale account projections
also remain gray. Excluded accounts appear only in **Details**.

Open **Details** for calibration evidence and the specific reason the pool
is uncertain. Complete token counts contribute even for models without published
prices. Missing token measurements remain uncertain. Complete usable
intervals can recover calibration after an incomplete interval; discarded evidence
does not permanently block the whole week. Ordinary scheduled resets can reuse
recent calibration when new-window evidence corroborates the same capacity scale.

## What the estimate assumes

- Enabled Pro-family accounts with a weekly window contribute to the forecast.
  Paused, reauthentication-required, deactivated and non-Pro accounts are excluded.
  An empty weekly account remains included because its quota returns at reset.
- Demand is the average across each account's current weekly window. It includes
  idle time; a recent burst does not silently replace that average.
- Each account's effective allowance is learned from its own percentage drawdown
  and measured input plus output tokens, without counting cached input twice.
  Five million tokens consuming 5% estimates a full allowance of 100 million tokens.
  This local estimate assumes a similar model, speed and cache mix continues;
  it is not an OpenAI credit balance or fixed token entitlement. Unknown models
  can contribute measured work without a price. Missing token records can still
  limit calibration, while independent account projections remain visible.
- When an account empties, its demand moves to the remaining accounts. At reset,
  its balance is replaced by a full allowance; unused quota does not accumulate.
- Current reset schedules repeat weekly over the forecast. Purchased or promotional
  credits, optional early resets and five-hour limits are outside this view.

For example, an account can empty tomorrow without causing an interruption if
another account carries the workload until the first resets. The forecast follows
that transferred workload, so the second account may empty earlier than its own
isolated trend would suggest.

The forecast does not control routing. Sticky sessions, model access, account
health, outside usage and future workload changes can all differ from the modeled
allocation. It is an estimate of included weekly quota, not an uptime guarantee.

See the [implementation context](https://github.com/peteallen/codex-lb/blob/main/openspec/specs/weekly-coverage/context.md)
for calibration safeguards and historical validation limits.

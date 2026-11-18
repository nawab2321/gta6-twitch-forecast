# GTA VI Twitch viewer forecast

`main.py` is a deterministic, standard-library-only Python 3.13 forecaster. It reads every `*.in` file from `MAKEFUN_INPUT_DIR` (default `/input`) and writes one `<id>.out` JSON file per case in `MAKEFUN_OUTPUT_DIR` (default `/output`).

## Model

For each comparable launch, the model takes its 24 hourly viewer counts on the UTC release day and converts hours 2–24 to log ratios against that launch's hour-one count. GTA VI's own pre-release category history is excluded as a launch curve because it is not a release-day launch. Curves with missing release-day hours are not filled in or interpolated.

The forecast distribution is the weighted empirical distribution of those ratios. Weights decay exponentially with the absolute log difference between a comparable's hour-one audience and the case's observed hour-one audience. A bandwidth of 0.85 was selected in leave-one-launch-out validation. Hour-one channel density and the target category's recent history provide small context adjustments; recent momentum is capped so an isolated pre-launch spike cannot dominate. If there are no usable launch curves, the program falls back to the official persistence baseline's log spread.

This avoids fitting a high-dimensional curve to only the four practice launches. The model uses the comparables supplied in each case, so the practice cases leave their own held-out launch answers out and the final case can use the full comparable set. It makes no network calls and uses no external packages.

## Validation

The kit's four practice inputs are cut at the end of hour one. They contain each case's history and known hour-one count, but not its answer for hours 2–24. The kit also omits `reference/answer.json`, which the rules identify as the source of those scored answers. Therefore exact per-practice-case scores and a direct four-case comparison to the starter cannot be reproduced from the supplied files without the hidden answer data. The rules publish the starter's aggregate practice score as loss **0.387**, typical miss **82.8%**, and 90% coverage **0.783**.

I evaluated the model on every complete launch curve in the 38-launch comparable set using leave-one-launch-out validation (37 scored launches, with each held-out curve removed from its own predictors). On that validation set:

| Forecast | Log pinball loss | Typical miss | 90% coverage |
|---|---:|---:|---:|
| Weighted comparable curves | 0.4159 | 87.5% | 0.8519 |
| Starter persistence formula | 0.9297 | 213.3% | 0.6240 |

These are scores on the comparable-launch leave-one-out set, **not** the official four-case practice score. The measured advantage applies only to that validation set; it is not evidence of improvement on the four hidden practice answers or the final GTA VI day. The kit provides no per-case answer data with which to report those scores.

A later nested audit selected bandwidth and history-feature settings inside each outer fold and reported loss 0.4142, typical miss 86.57%, and 90% coverage 0.8566 against the same starter score of 0.9297. That is a score for an inner-selected candidate model, not this fixed `main.py`: the nested search selected no momentum adjustment, while this implementation retains its fixed momentum adjustment. The candidate search was also designed after the earlier all-launch results had been seen, so it is retrospective evidence rather than a blind final estimate.

## Run

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=../gta6-twitch-ccu-forecast-01-kit/input \
MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The grader runs the same entry point with one case file in the input directory and the default `/input` and `/output` paths.

---

## make.fun Bounty

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/nawab2321/gta6-twitch-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/nawab2321/gta6-twitch-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

Competition: https://make.fun/bounty/gta6-twitch-ccu-forecast-01
